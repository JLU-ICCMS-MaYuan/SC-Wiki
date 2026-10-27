import { useEffect, useRef, useState } from 'react'
import { checkZeroFrequency, confirmCurrentZeroBoundary, confirmExistingZeroPoint } from './zeroCheck'
import ImageOpacityControl from './ImageOpacityControl'
import SourceCanvas, { type Tool } from './SourceCanvas'
import './styles.css'
import { DRAG_INFLUENCE } from './dragInfluence'
import { pointReadout, zeroReadout, recognizedAxes } from './axisGeometry'
import { amplitude, axisValid, clone, commit, frequency, move, restoreManualMarkers, reconnectManualPoints, ordered, pixelAt, record, redo, removePoints, undo, validateDocument, type Document, type History, type Point } from './engine'

const number = (n: number) => Number.isFinite(n) ? Number(n.toFixed(4)).toString() : '—'

function PointForm({ doc, point, onApply }: { doc: Document; point: Point; onApply: (f: number, a: number) => void }) {
  const reading = pointReadout(doc, point)
  const initialF = String(Number(frequency(doc, point).toFixed(6))), initialA = String(Number(amplitude(doc, point).toFixed(6)))
  const [f, setF] = useState(initialF), [a, setA] = useState(initialA)
  return <form onSubmit={e => { e.preventDefault(); onApply(f === initialF ? frequency(doc, point) : Number(f), a === initialA ? amplitude(doc, point) : Number(a)) }} className="coordinate-form">
    <label>频率 / {doc.calibration.frequency.unit}<input aria-label="选中点频率" type="number" step="any" required value={f} onChange={e => setF(e.target.value)} /></label>
    <label>幅值 / {doc.calibration.amplitude.unit === 'pixel' ? '相对像素' : doc.calibration.amplitude.unit}<input aria-label="选中点幅值" type="number" step="any" required value={a} onChange={e => setA(e.target.value)} /></label>
    <div className="point-readout" data-testid="point-readout">
      <div><span>原图像素 X</span><output data-testid="point-x">{number(reading.x)}</output></div>
      <div><span>原图像素 Y</span><output data-testid="point-y">{number(reading.y)}</output></div>
      <div className="full"><span>距当前标定零频线</span><output data-testid="point-zero-distance">{number(reading.distanceToZeroPx)} px</output></div>
    </div>
    <p className="muted">{point.status} · 频率与幅值按当前标定换算</p>
    <button className="secondary" type="submit">应用坐标到此点</button>
  </form>
}
function PointTable({ doc, active, selected, onSelect, compact = false }: { doc: Document; active: string; selected: string[]; onSelect: (ids: string[]) => void; compact?: boolean }) {
  const curve = doc.curves.find(c => c.id === active)!
  return <div className={'point-table ' + (compact ? 'compact' : '')}><table><thead><tr><th>点</th><th>频率 / {doc.calibration.frequency.unit}</th><th>幅值{doc.calibration.amplitude.unit === 'pixel' ? ' / px' : ''}</th><th>来源</th></tr></thead><tbody>
    {ordered(doc, curve.points).map((p, i) => <tr key={p.id} id={'row-' + p.id} data-row={p.id} aria-selected={selected.includes(p.id)} onClick={() => onSelect([p.id])} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect([p.id]) } }}>
      <td>{String(i + 1).padStart(3, '0')}</td><td>{number(frequency(doc, p))}</td><td>{number(amplitude(doc, p))}</td><td><span className={p.status.startsWith('人工') ? 'manual-status' : ''}>{p.status}</span></td>
    </tr>)}
  </tbody></table>{!curve.points.length && <p className="empty">当前曲线没有点，可以在原图上补选。</p>}</div>
}

export default function SpectrumManualEditor({documents:samples,onSave,onClose,kind,imageOpacity,onOpacityChange:setImageOpacity,initialPointId,focusPointId}: {imageOpacity:number;onOpacityChange:(value:number)=>void;initialPointId?:string;focusPointId?:string;documents:Document[];onSave:(doc:Document)=>Promise<void>;onClose:()=>void;kind:'alpha2f'|'phonon_dos'}) {
  const [saving,setSaving]=useState(false), saveLock=useRef(false)
  const [sampleId, setSampleId] = useState(samples[0].id), initial = samples.find(s => s.id === sampleId)!
  const [loaded] = useState(() => ({doc:clone(samples[0]),error:'',blocked:false}))
  const [saved, setSaved] = useState<Document>(loaded.doc), [history, setHistory] = useState<History>({ past: [], present: loaded.doc, future: [] })
  const doc = history.present
  const [active, setActive] = useState(doc.curves[0].id), [selected, setSelected] = useState<string[]>(initialPointId?[initialPointId]:[])
  const [tool, setTool] = useState<Tool>('select'), [linked, setLinked] = useState(true), [dragMode, setDragMode] = useState<'amplitude' | 'free'>('free')
  const [display, setDisplay] = useState('overlay'), [all, setAll] = useState(true)
  const [error, setError] = useState(loaded.error), [notice, setNotice] = useState('')
  const [exitModal, setExitModal] = useState(false), exitAction = useRef<() => void>(() => {})
  const [calibration, setCalibration] = useState(clone(doc.calibration)), [pick, setPick] = useState<{ axis: 'frequency' | 'amplitude'; index: 0 | 1 } | null>(null)
  const curve = doc.curves.find(c => c.id === active)!, point = curve.points.find(p => p.id === selected[0])
  const zeroInfo = zeroReadout(doc), reference = recognizedAxes(doc)
  const focusCoordinates = () => requestAnimationFrame(() => document.querySelector('.inspector')?.scrollTo({ top: 0, behavior: 'instant' }))
  const calibrationDirty = JSON.stringify(calibration) !== JSON.stringify(doc.calibration)
  const dirty = JSON.stringify(doc) !== JSON.stringify(saved) || calibrationDirty
  const currentCheck = checkZeroFrequency(doc), activeCheck = currentCheck.curves.find(c => c.id === active)!, covered = activeCheck.status === 'complete'
  useEffect(() => { setCalibration(clone(doc.calibration)); setPick(null) }, [doc.calibration])
  useEffect(() => {
    if (selected.length !== 1) return
    const row = document.getElementById('row-' + selected[0]), table = row?.closest('.point-table')
    if (row && table) {
      const r = row.getBoundingClientRect(), t = table.getBoundingClientRect()
      if (r.top < t.top + 35) table.scrollTop += r.top - t.top - 35
      else if (r.bottom > t.bottom) table.scrollTop += r.bottom - t.bottom
    }
  }, [selected])
  useEffect(() => {
    const handle = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', handle); return () => window.removeEventListener('beforeunload', handle)
  }, [dirty])
  const change = (next: Document, detail?: string) => {
    setError(''); setNotice('')
    if (next === doc) return
    setHistory(h => commit(h, detail ? record(next, 'move', detail) : next))
  }
  const remove = () => { change(removePoints(doc, active, selected)); setSelected([]) }
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (saving || (e.target as HTMLElement).closest('input,select,textarea')) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); setHistory(h => e.shiftKey ? redo(h) : undo(h)) }
      if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); remove() }
      if (e.key === 'Escape') { setTool('select'); setPick(null); setSelected([]) }
    }
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key)
  }, [doc, selected, active, saving])
  const selectCurve = (id: string) => { setActive(id); setSelected([]);setTool('select') }
  const save = async (): Promise<boolean> => {
    if(saveLock.current)return false
    saveLock.current=true;setSaving(true)
    try {
      if (calibrationDirty) throw new Error('标定表单还有未应用的修改，请先应用标定，再保存。')
      validateDocument(doc, initial)
      await onSave(doc)
      setSaved(clone(doc)); setHistory({ past: [], present: clone(doc), future: [] }); setError(''); setSelected([])
      setNotice('人工修订已保存到数据库，并生成新的历史版本。')
      onClose();return true
    } catch (e) { setError('保存失败：' + (e as Error).message); return false } finally {saveLock.current=false;setSaving(false)}
  }
  const leave = (action: () => void) => {
    if(saving)return
    if (!dirty) return action()
    exitAction.current = action; setExitModal(true)
  }
  const switchSample = (id: string) => {
    const next = samples.find(s => s.id === id)!, state = {doc:clone(next),error:'',blocked:false}
    setSampleId(id); setSaved(state.doc); setHistory({ past: [], present: state.doc, future: [] }); setActive(next.curves[0].id)
    setSelected([]); setError(state.error); setNotice(''); setAll(true); setTool('select')
  }
  const confirmZero = (action: () => Document) => {
    try { change(action()); setNotice('零频核对依据已记录，点击保存调整后会检查保存结果。') }
    catch (e) { setError((e as Error).message) }
  }
  const restore = () => {
    change(record({ ...clone(initial), operations: doc.operations }, 'restore', '恢复本次打开时的曲线数据'))
    setSelected([]); setTool('select'); setError('')
  }
  const applyCoordinates = (f: number, a: number) => {
    if (!point || ![f, a].every(Number.isFinite)) { setError('坐标必须是有限数值'); return }
    const fp = pixelAt(doc.calibration.frequency, f), ap = pixelAt(doc.calibration.amplitude, a)
    const next = move(doc, active, point.id, (doc.calibration.direction === 'x' ? fp : ap) - point.x, (doc.calibration.direction === 'y' ? fp : ap) - point.y, false, 'free')
    change(next, '输入坐标修改单点（越出图框时限制到有效位置）')
  }
  const axisEdit = (axis: 'frequency' | 'amplitude', field: 'pixels' | 'values', index: 0 | 1, value: number) => setCalibration(c => {
    const next = clone(c); next[axis][field][index] = value; return next
  })
  const applyCalibration = () => {
    if (!axisValid(calibration.frequency) || !axisValid(calibration.amplitude)) { setError('每根轴的两个位置和数值必须有限、互不重合'); return }
    if (calibration.amplitude.unit !== 'pixel' && !calibration.amplitudeEvidence.trim()) { setError('填写物理幅值刻度前，请注明来自原图何处的幅值依据；不能借用累计 λ'); return }
    const next = record({ ...restoreManualMarkers(doc, initial), calibration: clone(calibration), zero: null }, 'calibration', '修改线性标定，保留全部源像素位置；零频选点需重新核对')
    try { validateDocument(next, initial); change(next); setTool('select'); setPick(null) } catch (e) { setError((e as Error).message) }
  }
  const displayedRange = curve.points.length ? (() => { const ps = ordered(doc, curve.points); return number(frequency(doc, ps[0])) + '–' + number(frequency(doc, ps.at(-1)!)) + ' ' + doc.calibration.frequency.unit })() : '尚无数据点'
  const zeroWarning = <div className={'callout ' + (covered ? 'info' : 'warning')} data-testid="zero-status">{covered ? '已记录原图零频位置与当前曲线的人工选点；科学依据仍待核对。' : doc.zero ? '零频提取不完整：零频线已标记，当前曲线还没有确认的零频点。可在右侧核对位置后补选。' : '零频位置尚待核对：蓝色虚线是当前标定的 0 频率，可对照灰色已有识别刻度和右侧像素坐标。'}</div>
  const curvePicker = <div className="curve-picker">{doc.curves.map(c => <button key={c.id} className={active === c.id ? 'active' : ''} onClick={() => selectCurve(c.id)}><i style={{ background: c.color }}/>{c.name}<span>{c.points.length}</span></button>)}</div>
  const selectedPanel = <section className="panel-section" data-testid="coordinate-panel"><div className="section-heading"><h3>坐标与零频核对</h3><span className="badge">{selected.length} 个</span></div>
    {selected.length === 1 && point ? <PointForm key={point.id + ':' + point.x + ':' + point.y + ':' + JSON.stringify(doc.calibration)} doc={doc} point={point} onApply={applyCoordinates} /> : <p className="muted">在图上点选或框选，也可在下方数据表中选择。</p>}
    <div className="zero-readout" data-testid="zero-readout">
      <strong>零频线位置 / 原图像素 {doc.calibration.direction.toUpperCase()}</strong>
      <div><span>当前标定 0 频率</span><output data-testid="calibrated-zero-pixel">{number(zeroInfo.zeroPixel)} px</output></div>
      {zeroInfo.originalZero !== null && <><div><span>已有识别 0 刻度</span><output>{number(zeroInfo.originalZero)} px</output></div><div><span>与已有识别位置之差</span><output>{number(zeroInfo.differencePx!)} px</output></div></>}
      <div><span>人工标记</span><output data-testid="marked-zero-pixel">{zeroInfo.markedPixel === null ? '尚未标记' : number(zeroInfo.markedPixel) + ' px'}</output></div>
      {zeroInfo.markedValue !== null && <div><span>标记处换算频率</span><output>{number(zeroInfo.markedValue)} {doc.calibration.frequency.unit}</output></div>}
      <p className="muted">数字相符表示标定一致；真实零边界仍需与原图核对。</p>
      <button className="secondary" disabled={currentCheck.boundary === 'confirmed'} onClick={() => confirmZero(() => confirmCurrentZeroBoundary(doc))}>确认蓝色零频线与原图一致</button>
      <button className="secondary" disabled={selected.length !== 1 || !point || currentCheck.boundary !== 'confirmed'} onClick={() => confirmZero(() => confirmExistingZeroPoint(doc, active, point!.id))}>确认选中点为零频点</button>
      {activeCheck.status === 'needs_confirmation' && <p className="muted">已有零频候选点，可确认它，无需删除重画。</p>}
    </div>
    <button className="secondary" disabled={!curve.points.some(p => p.manual)} onClick={() => { const next = reconnectManualPoints(doc, active); change(next); setSelected([]); setNotice(next === doc ? '未发现需要修正的局部回折，点坐标保持不变。' : '已调整局部连线，点坐标保持不变；可撤销，保存后才写入数据库新版本。') }}>重新连接人工补点</button>
    <p className="muted">已有折返可重新连线；坐标不变，操作可撤销。</p>
    <button className="danger" disabled={!selected.length} onClick={remove}>删除选中点{selected.length > 1 ? `（${selected.length}）` : ''}</button>
  </section>
  return <div className="spectrum-manual-editor app editor-app"><main>
<header className="editor-header"><button onClick={() => leave(onClose)}>← 返回详情</button><div><strong>{doc.title} · 人工调整</strong><span className="badge">{dirty ? '未保存' : '数据库版本'}</span></div><div className="header-actions"><button disabled={saving || !history.past.length} onClick={() => setHistory(undo)}>↶ 撤销</button><button disabled={saving || !history.future.length} onClick={() => setHistory(redo)}>↷ 重做</button><button disabled={saving} onClick={restore}>恢复打开时数据</button><button className="primary" disabled={saving} onClick={() => void save()}>{saving?'正在保存…':'保存调整'}</button></div></header>
    {samples.length>1 && <div className="production-curve-tabs" aria-label="选择编辑分波">{samples.map(s=><button key={s.id} disabled={saving} className={s.id===sampleId?'active':''} onClick={()=>leave(()=>switchSample(s.id))}>{s.title}</button>)}</div>}
    {error && <div role="alert" className="callout error">{error}</div>}{notice && <div role="status" className="callout success">{notice}</div>}
    <fieldset className="production-editor-fields" disabled={saving}>
<div className="editor-layout"><section className="workbench">
        <div className="tool-strip">{([['select','↖ 选点 / 拖动'],['pan','✥ 平移'],['add','＋ 增加点'],['box','▣ 框选']] as [Tool,string][]).map(([value,label]) => <button key={value} className={tool === value ? 'active' : ''} onClick={() => { if(value==='add' && (selected.length!==1 || !point)){setError('请先选中当前曲线的一个已有点，再点击增加点。');return} setTool(value); setPick(null);setError('');setNotice('') }}>{label}</button>)}<div className="tool-strip-end"><label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)}/>显示其他分波</label><button onClick={() => setDisplay(display === 'overlay' ? 'data' : 'overlay')}>{display === 'overlay' ? '隐藏原图' : '显示原图'}</button></div></div>
        {!['select','pan'].includes(tool) && <div className="tool-hint">{tool === 'zero' ? '在原图 0 刻度对应的图框内位置点击，橙色线只表示标定位置。' : tool === 'zeroPoint' ? '在橙色零频线上的真实曲线位置点击，幅值取自你的点击。' : tool === 'calibrate' ? `在原图上点选${pick?.axis === 'frequency' ? '频率' : '幅值'}轴的第 ${(pick?.index || 0) + 1} 个刻度位置，然后输入对应值。` : tool === 'add' ? '单击连续描线；靠近已有点会高亮吸附，不重复建点。双击结束，保存调整后提交。' : tool === 'box' ? '拖出选区后点击“删除选中点”，误识别区域将保留为空缺。' : ''}</div>}
        <div className="editor-canvas-row"><ImageOpacityControl value={imageOpacity} onChange={setImageOpacity} disabled={display === 'data'}/>
        <SourceCanvas focusPointId={sampleId===samples[0].id?focusPointId:undefined} doc={doc} active={active} selected={selected} referenceCurves={samples.filter(s=>s.id!==sampleId).flatMap(s=>s.curves)} imageOpacity={imageOpacity} editing tool={tool} linked={linked} dragMode={dragMode} display={display} all={all} onSelect={setSelected} onFinishAdd={() => {setTool('select');setError('');setNotice('连续加点已结束，已加点保留在当前编辑中。请点击保存调整提交。')}} onAdded={focusCoordinates} onZeroMarked={focusCoordinates} onChange={change} onError={setError} onPick={(x,y) => {
          if (!pick) return
          const direction = pick.axis === 'frequency' ? calibration.direction : calibration.direction === 'x' ? 'y' : 'x'
          axisEdit(pick.axis, 'pixels', pick.index, direction === 'x' ? x : y); setTool('select'); setPick(null)
        }}/></div>
        <footer className="workbench-footer"><span><i style={{ background: curve.color }}/>{curve.name} · {curve.points.length} 个点</span><span>{displayedRange}</span><span>{doc.operations.length} 次人工操作</span></footer>
      </section><aside className="inspector">
        {selectedPanel}
        <section className="panel-section"><div className="section-heading"><h3>编辑曲线</h3><span className="tag">单条编辑</span></div>{curvePicker}<p className="muted">{kind === 'phonon_dos' ? '其他分波只作参照，不随当前曲线移动。' : '累计 λ 只在原图中参照，不作为 α²F 幅值刻度。'}</p></section>
        <section className="panel-section"><div className="section-heading"><h3>局部形状调整</h3><label className="switch"><input aria-label="附近点联动" type="checkbox" checked={linked} onChange={e => setLinked(e.target.checked)}/><span>附近点联动</span></label></div>
          <div className="segmented"><button className={dragMode === 'amplitude' ? 'active' : ''} onClick={() => setDragMode('amplitude')}>只改幅值</button><button className={dragMode === 'free' ? 'active' : ''} onClick={() => setDragMode('free')}>自由移动（X / Y）</button></div>
          <p className="range-label">主要影响区 <strong>两侧各 {DRAG_INFLUENCE.coreNeighbors} 个点</strong></p>
          <p className="muted">按描线顺序计数。前 {DRAG_INFLUENCE.coreNeighbors} 个邻点明显跟随，之后指数衰减；很远的点不动。未连接的断口和其他分波不受影响。{dragMode === 'amplitude' && `当前频率沿${doc.calibration.direction === 'y' ? '竖轴，左右' : '横轴，上下'}拖动改变幅值。`}</p>
        </section>
        <section className="panel-section"><h3>零频边界</h3>
          <ol className="zero-steps" data-testid="zero-steps"><li>先选要核对的曲线；PhDOS 的 La、Sc、H 分别处理。</li><li>在原图频率轴找到 0 刻度。蓝线正确时，在上方确认蓝色零频线；不正确时，点下方第 1 步并在 0 刻度对应的图框内位置点击。</li><li>在零频线上找当前曲线的点。已有点就选中，并在上方确认选中点；缺点则点下方第 2 步，在原图曲线上补选。</li><li>检查右侧频率为 0、距零线为 0 px，然后保存调整。回到详情查看结果；PhDOS 要全部分波完成。</li></ol>
          {zeroWarning}<div className="stack"><button className={tool === 'zero' ? 'active' : ''} onClick={() => setTool('zero')}>1 · 标记原图 0 频率位置</button><button disabled={!doc.zero} className={tool === 'zeroPoint' ? 'active' : ''} onClick={() => setTool('zeroPoint')}>2 · 补选曲线零频点</button></div><p className="muted">零频率不代表零幅值。看不清时保留待核对。</p></section>
        <section className="panel-section"><details><summary>坐标标定 <span>线性 · 两点</span></summary><div className="calibration-form">
          <p className="muted">{reference ? '灰色刻度来自该运行的原识别记录；蓝色为当前标定，二者独立显示。' : '没有可匹配的识别记录，当前只显示两点标定。'}{kind === 'alpha2f' ? ' 未经证实的刻度不能用作α²F幅值。' : ' 原图没有DOS数字幅值刻度，当前使用相对像素。'}</p>
          <label>频率轴方向<select aria-label="频率轴方向" value={calibration.direction} onChange={e => {
            const direction = e.target.value as 'x' | 'y', [x0,y0,x1,y1] = doc.source.plot
            setCalibration(c => ({ ...c, direction, frequency: { ...c.frequency, pixels: direction === 'x' ? [x0,x1] : [y1,y0] }, amplitude: { ...c.amplitude, pixels: direction === 'x' ? [y1,y0] : [x0,x1] } }))
          }}><option value="y">竖轴为频率</option><option value="x">横轴为频率</option></select></label>
          <label>频率单位<select aria-label="频率单位" value={calibration.frequency.unit} onChange={e => {
            const factors: Record<string,number> = { THz: 1, 'cm-1': .0299792458, meV: .2417989242084918 }, unit = e.target.value
            setCalibration(c => ({ ...c, frequency: { ...c.frequency, unit, values: c.frequency.values.map(v => v * factors[c.frequency.unit] / factors[unit]) as [number,number] } }))
          }}>{['THz','cm-1','meV'].map(u => <option key={u}>{u}</option>)}</select></label>
          {(['frequency','amplitude'] as const).map(axis => <fieldset key={axis}><legend>{axis === 'frequency' ? '频率轴' : '幅值轴'}</legend>{([0,1] as const).map(i => <div className="axis-row" key={i}>
            <button className="pick-button" onClick={() => { setPick({axis,index:i}); setTool('calibrate') }} aria-label={`点选${axis === 'frequency' ? '频率' : '幅值'}刻度${i+1}`}>⌖ {i+1}</button>
            <label>源像素<input type="number" step="any" aria-label={`${axis}-${i}-pixel`} value={Number.isNaN(calibration[axis].pixels[i]) ? '' : calibration[axis].pixels[i]} onChange={e => axisEdit(axis,'pixels',i,e.target.value === '' ? NaN : Number(e.target.value))}/></label>
            <label>对应值<input type="number" step="any" aria-label={`${axis}-${i}-value`} value={Number.isNaN(calibration[axis].values[i]) ? '' : calibration[axis].values[i]} onChange={e => axisEdit(axis,'values',i,e.target.value === '' ? NaN : Number(e.target.value))}/></label>
          </div>)}</fieldset>)}
          <label>幅值单位<select aria-label="幅值单位" value={calibration.amplitude.unit} onChange={e => setCalibration(c => ({...c, amplitude:{...c.amplitude,unit:e.target.value}}))}><option value="pixel">相对像素（刻度待核对）</option><option value="dimensionless">无量纲</option><option value="modes/THz">modes/THz</option><option value="unknown">其他 / 待核对</option>{!['pixel','dimensionless','modes/THz','unknown'].includes(calibration.amplitude.unit)&&<option value={calibration.amplitude.unit}>{calibration.amplitude.unit}</option>}</select></label>
          <label>幅值标定依据<textarea aria-label="幅值标定依据" value={calibration.amplitudeEvidence} placeholder="绝对幅值：注明α²F刻度/单位来源；相对幅值用于ωlog时：注明零基线位置和全曲线统一倍率的依据，不填λ刻度" onChange={e => setCalibration(c => ({...c,amplitudeEvidence:e.target.value}))}/></label>
          {kind==='alpha2f' && <p className="muted">幅值核对要有论文明确给出的 α²F 刻度或倍率。像素宽度不等于 α²F 数值，填依据也不会自动重算积分。</p>}
          <button className="secondary" onClick={applyCalibration}>应用标定</button><p className="muted">保留原图像素位置，只重新换算数值。修改后需重新核对零频选点。</p>
        </div></details></section>
        <section className="panel-section"><h3>逐点数据</h3><PointTable doc={doc} active={active} selected={selected} onSelect={setSelected} compact/></section>
      </aside></div>
    </fieldset></main>
    {exitModal && <div className="modal-backdrop"><div role="dialog" aria-modal="true" aria-labelledby="leave-title" className="modal"><span className="eyebrow">UNSAVED CHANGES</span><h2 id="leave-title">保留这次调整吗？</h2><p>当前修改尚未保存到数据库。</p><div className="modal-actions"><button onClick={() => setExitModal(false)}>继续编辑</button><button className="danger" onClick={() => { setHistory({past:[],present:clone(saved),future:[]}); setCalibration(clone(saved.calibration)); setExitModal(false); exitAction.current() }}>放弃修改</button><button className="primary" onClick={async () => { if (await save()) { setExitModal(false); exitAction.current() } }}>保存并返回</button></div></div></div>}
  </div>
}
