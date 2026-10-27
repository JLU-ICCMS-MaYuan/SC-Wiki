import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { alpha, useTheme } from '@mui/material/styles'
import ImageOpacityControl from './ImageOpacityControl'
import SourceCanvas, { type Tool } from './SourceCanvas'
import './styles.css'
import { latestFrequencyRepair, undoFrequencyRepair } from './frequencyRepairs'
import { DRAG_INFLUENCE } from './dragInfluence'
import { pointReadout, recognizedAxes } from './axisGeometry'
import { amplitude, axisValid, automaticConnections, undoAutomaticConnections, clone, commit, frequency, move, restoreManualMarkers, reconnectManualPoints, ordered, pixelAt, record, redo, removePoints, undo, validateDocument, type Document, type History, type Point } from './engine'

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

type LeaveIntent = { kind: 'close' } | { kind: 'switch'; id: string }

export default function SpectrumManualEditor({documents:initialDocuments,onSave,onClose,kind,imageOpacity,onOpacityChange:setImageOpacity,initialPointId,focusPointId}: {imageOpacity:number;onOpacityChange:(value:number)=>void;initialPointId?:string;focusPointId?:string;documents:Document[];onSave:(doc:Document)=>Promise<Document[]|void>;onClose:()=>void;kind:'alpha2f'|'phonon_dos'}) {
  const theme = useTheme()
  const toolColors = { '--tool-active': theme.palette.primary.main, '--tool-active-hover': theme.palette.primary.dark, '--tool-active-text': theme.palette.primary.contrastText, '--tool-light': alpha(theme.palette.primary.main, .08), '--tool-light-hover': alpha(theme.palette.primary.main, .14), '--tool-border': alpha(theme.palette.primary.main, .25) } as CSSProperties
  const [saving,setSaving]=useState(false), saveLock=useRef(false)
  const [samples,setSamples] = useState(initialDocuments)
  const [sampleId, setSampleId] = useState(samples[0].id), initial = samples.find(s => s.id === sampleId)!
  const [loaded] = useState(() => ({doc:clone(samples[0]),error:'',blocked:false}))
  const [saved, setSaved] = useState<Document>(loaded.doc), [history, setHistory] = useState<History>({ past: [], present: loaded.doc, future: [] })
  const doc = history.present
  const frequencyRepair = useMemo(() => latestFrequencyRepair(doc), [doc])
  const [active, setActive] = useState(doc.curves[0].id), [selected, setSelected] = useState<string[]>(initialPointId?[initialPointId]:[])
  const [tool, setTool] = useState<Tool>('idle'), [dragMode, setDragMode] = useState<'amplitude' | 'free'>('free')
  const [display, setDisplay] = useState('overlay'), [all, setAll] = useState(true)
  const [error, setError] = useState(loaded.error), [notice, setNotice] = useState('')
  const [exitIntent, setExitIntent] = useState<LeaveIntent|null>(null)
  const [calibration, setCalibration] = useState(clone(doc.calibration)), [pick, setPick] = useState<{ axis: 'frequency' | 'amplitude'; index: 0 | 1 } | null>(null)
  const exitTool = () => { setTool('idle'); setPick(null) }
  const chooseTool = (next: Tool, target: typeof pick = null) => {
    const same = tool === next && (next !== 'calibrate' || pick?.axis === target?.axis && pick?.index === target?.index)
    setTool(same ? 'idle' : next); setPick(!same && next === 'calibrate' ? target : null)
    setError(''); setNotice('')
  }
  const curve = doc.curves.find(c => c.id === active)!, point = curve.points.find(p => p.id === selected[0])
  const reference = recognizedAxes(doc)
  const focusCoordinates = () => requestAnimationFrame(() => document.querySelector('.inspector')?.scrollTo({ top: 0, behavior: 'instant' }))
  const calibrationDirty = JSON.stringify(calibration) !== JSON.stringify(doc.calibration)
  const dirty = JSON.stringify(doc) !== JSON.stringify(saved) || calibrationDirty
  useEffect(() => { setCalibration(clone(doc.calibration)); exitTool() }, [doc.calibration])
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
      if (saving) return
      if (exitIntent) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setExitIntent(null) }
        return
      }
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); exitTool(); setSelected([]); return }
      if ((e.target as HTMLElement).closest('input,select,textarea')) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); setHistory(h => e.shiftKey ? redo(h) : undo(h)) }
      if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); remove() }
    }
    // 全屏 Dialog 会在冒泡阶段截获 Esc；先处理编辑器的工具退出。
    window.addEventListener('keydown', key, true); return () => window.removeEventListener('keydown', key, true)
  }, [doc, selected, active, saving, exitIntent])
  const selectCurve = (id: string) => { setActive(id); setSelected([]);exitTool() }
  const save = async (nextId?: string): Promise<boolean> => {
    if(saveLock.current)return false
    saveLock.current=true;setSaving(true);setError('')
    try {
      if (calibrationDirty) throw new Error('标定表单还有未应用的修改，请先应用标定，再保存。')
      validateDocument(doc, initial)
      const updated = await onSave(doc)
      const nextSamples = updated || samples.map(s => s.id === doc.id ? clone(doc) : s)
      const savedDoc = nextSamples.find(s => s.id === doc.id) || doc
      setSamples(nextSamples);setExitIntent(null)
      if (nextId) { switchSample(nextId, nextSamples); return true }
      setSaved(clone(savedDoc)); setHistory({ past: [], present: clone(savedDoc), future: [] }); setError(''); setSelected([])
      setNotice('人工修订已保存到数据库，并生成新的历史版本。')
      onClose();return true
    } catch (e) { setError('保存失败：' + (e as Error).message); return false } finally {saveLock.current=false;setSaving(false)}
  }
  const leave = (intent: LeaveIntent) => {
    if(saveLock.current || intent.kind === 'switch' && intent.id === sampleId)return
    if (!dirty) { if(intent.kind === 'switch')switchSample(intent.id);else onClose();return }
    setExitIntent(intent)
  }
  const switchSample = (id: string, documents = samples) => {
    const next = documents.find(s => s.id === id)!, state = {doc:clone(next),error:'',blocked:false}
    setSampleId(id); setSaved(state.doc); setHistory({ past: [], present: state.doc, future: [] }); setActive(next.curves[0].id)
    setSelected([]); setError(state.error); setNotice(''); setAll(true); exitTool()
  }
  const restore = () => {
    change(record({ ...clone(initial), operations: doc.operations }, 'restore', '恢复本次打开时的曲线数据'))
    setSelected([]); exitTool(); setError('')
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
    const next = record({ ...restoreManualMarkers(doc, initial), calibration: clone(calibration) }, 'calibration', '修改线性标定，保留全部源像素位置')
    try { validateDocument(next, initial); change(next); exitTool() } catch (e) { setError((e as Error).message) }
  }
  const displayedRange = curve.points.length ? (() => { const ps = ordered(doc, curve.points); return number(frequency(doc, ps[0])) + '–' + number(frequency(doc, ps.at(-1)!)) + ' ' + doc.calibration.frequency.unit })() : '尚无数据点'
  const curvePicker = <div className="curve-picker">{doc.curves.map(c => <button key={c.id} className={active === c.id ? 'active' : ''} onClick={() => selectCurve(c.id)}><i style={{ background: c.color }}/>{c.name}<span>{c.points.length}</span></button>)}</div>
  const selectedPanel = <section className="panel-section" data-testid="coordinate-panel"><div className="section-heading"><h3>坐标调整</h3><span className="badge">{selected.length} 个</span></div>
    {selected.length === 1 && point ? <PointForm key={point.id + ':' + point.x + ':' + point.y + ':' + JSON.stringify(doc.calibration)} doc={doc} point={point} onApply={applyCoordinates} /> : <p className="muted">在图上点选或框选，也可在下方数据表中选择。</p>}
    <button className="secondary" disabled={!curve.points.some(p => p.manual)} onClick={() => { const next = reconnectManualPoints(doc, active); change(next); setSelected([]); setNotice(next === doc ? '未发现需要修正的局部回折，点坐标保持不变。' : '已调整局部连线，点坐标保持不变；可撤销，保存后才写入数据库新版本。') }}>重新连接人工补点</button>
    <p className="muted">已有折返可重新连线；坐标不变，操作可撤销。</p>
    <button className="danger" disabled={!selected.length} onClick={remove}>删除选中点{selected.length > 1 ? `（${selected.length}）` : ''}</button>
  </section>
  return <div className="spectrum-manual-editor app editor-app" style={toolColors}><main>
<header className="editor-header"><button onClick={() => leave({kind:'close'})}>← 返回详情</button><div><strong>{doc.title} · 人工调整</strong><span className="badge">{dirty ? '未保存' : '数据库版本'}</span></div><div className="header-actions"><button disabled={saving || !history.past.length} onClick={() => setHistory(undo)}>↶ 撤销</button><button disabled={saving || !history.future.length} onClick={() => setHistory(redo)}>↷ 重做</button><button disabled={saving} onClick={restore}>恢复打开时数据</button><button className="primary" disabled={saving} onClick={() => void save()}>{saving?'正在保存…':'保存调整'}</button></div></header>
    {samples.length>1 && <div className="production-curve-tabs" aria-label="选择编辑分波">{samples.map(s=><button key={s.id} disabled={saving} className={s.id===sampleId?'active':''} onClick={()=>leave({kind:'switch',id:s.id})}>{s.title}</button>)}</div>}
    {error && !exitIntent && <div role="alert" className="callout error">{error}</div>}{notice && <div role="status" className="callout success">{notice}</div>}
    <fieldset className="production-editor-fields" disabled={saving}>
<div className="editor-layout"><section className="workbench">
        <div className="tool-strip">{([['dragLinked','联动选点／拖动'],['dragSingle','单点选点／拖动'],['pan','✥ 平移'],['add','＋ 增加点'],['box','▣ 框选']] as [Tool,string][]).map(([value,label]) => <button key={value} className="editor-tool" aria-pressed={tool === value} onClick={() => chooseTool(value)}>{label}</button>)}<div className="tool-strip-end"><label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)}/>显示其他分波</label><button onClick={() => setDisplay(display === 'overlay' ? 'data' : 'overlay')}>{display === 'overlay' ? '隐藏原图' : '显示原图'}</button></div></div>
        {!['dragLinked','dragSingle','pan'].includes(tool) && <div className="tool-hint">{tool === 'idle' ? '请选择工具；当前可选点查看坐标，不会拖动或增加点。' : tool === 'calibrate' ? `在原图上点选${pick?.axis === 'frequency' ? '频率' : '幅值'}轴的第 ${(pick?.index || 0) + 1} 个刻度位置，然后输入对应值。` : tool === 'add' ? (selected.length===1 && point ? '从选中点继续单击加点；点原直连另一端可插入，未连接点可补接。双击或再次点击“增加点”退出。' : '靠近当前曲线已有点可吸附，点击它作为起点；再次点击“增加点”退出。') : tool === 'box' ? '拖出选区后点击“删除选中点”，误识别区域将保留为空缺。' : ''}</div>}
        <div className="editor-canvas-row"><ImageOpacityControl value={imageOpacity} onChange={setImageOpacity} disabled={display === 'data'}/>
        <SourceCanvas focusPointId={sampleId===samples[0].id?focusPointId:undefined} doc={doc} active={active} selected={selected} referenceCurves={samples.filter(s=>s.id!==sampleId).flatMap(s=>s.curves)} imageOpacity={imageOpacity} editing tool={tool} dragMode={dragMode} display={display} all={all} onSelect={setSelected} onFinishAdd={message => {exitTool();setError('');setNotice(message||'连续加点已结束，已加点保留在当前编辑中。请点击保存调整提交。')}} onAdded={focusCoordinates} onChange={change} onError={setError} onPick={(x,y) => {
          if (!pick) return
          const direction = pick.axis === 'frequency' ? calibration.direction : calibration.direction === 'x' ? 'y' : 'x'
          axisEdit(pick.axis, 'pixels', pick.index, direction === 'x' ? x : y); exitTool()
        }}/></div>
        <footer className="workbench-footer"><span><i style={{ background: curve.color }}/>{curve.name} · {curve.points.length} 个点</span><span>{displayedRange}</span><span>{doc.operations.length} 次人工操作</span></footer>
      </section><aside className="inspector">
        {selectedPanel}
        {frequencyRepair&&<section className="panel-section" data-testid="frequency-repair-controls"><h3>自动频率微调</h3>
          <p className="muted">最近一批修正 {frequencyRepair.pointCount} 个点，最大移动 {number(frequencyRepair.maxShiftPx)} 原图像素。撤销仅恢复频率方向，保留幅值。</p>
          <button className="secondary" disabled={!frequencyRepair.canUndo} onClick={()=>{change(undoFrequencyRepair(doc));setSelected([]);exitTool();setNotice('已撤销自动频率微调；保存后生效。未继续人工编辑时，重新计算不会立即重做。')}}>撤销自动频率微调</button>
          {!frequencyRepair.canUndo&&<p className="muted">这些点的频率、标定或点身份已改变，不能直接撤销覆盖后续修改。</p>}
        </section>}
        {automaticConnections(doc).length>0&&<section className="panel-section"><h3>自动连接记录</h3><button className="secondary" onClick={()=>change(undoAutomaticConnections(doc))}>撤销已记录的自动连接</button></section>}
        <section className="panel-section"><div className="section-heading"><h3>编辑曲线</h3><span className="tag">单条编辑</span></div>{curvePicker}<p className="muted">{kind === 'phonon_dos' ? '其他分波只作参照，不随当前曲线移动。' : '累计 λ 只在原图中参照，不作为 α²F 幅值刻度。'}</p></section>
        <section className="panel-section"><div className="section-heading"><h3>拖动方向与联动范围</h3></div>
          <div className="segmented"><button className={dragMode === 'amplitude' ? 'active' : ''} onClick={() => setDragMode('amplitude')}>只改幅值</button><button className={dragMode === 'free' ? 'active' : ''} onClick={() => setDragMode('free')}>自由移动（X / Y）</button></div>
          <p className="range-label">主要影响区 <strong>两侧各 {DRAG_INFLUENCE.coreNeighbors} 个点</strong></p>
          <p className="muted">按描线顺序计数。前 {DRAG_INFLUENCE.coreNeighbors} 个邻点明显跟随，之后指数衰减；很远的点不动。未连接的断口和其他分波不受影响。{dragMode === 'amplitude' && `当前频率沿${doc.calibration.direction === 'y' ? '竖轴，左右' : '横轴，上下'}拖动改变幅值。`}</p>
        </section>
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
            <button className="pick-button editor-tool" aria-pressed={tool === 'calibrate' && pick?.axis === axis && pick?.index === i} onClick={() => chooseTool('calibrate', {axis,index:i})} aria-label={`点选${axis === 'frequency' ? '频率' : '幅值'}刻度${i+1}`}>⌖ {i+1}</button>
            <label>源像素<input type="number" step="any" aria-label={`${axis}-${i}-pixel`} value={Number.isNaN(calibration[axis].pixels[i]) ? '' : calibration[axis].pixels[i]} onChange={e => axisEdit(axis,'pixels',i,e.target.value === '' ? NaN : Number(e.target.value))}/></label>
            <label>对应值<input type="number" step="any" aria-label={`${axis}-${i}-value`} value={Number.isNaN(calibration[axis].values[i]) ? '' : calibration[axis].values[i]} onChange={e => axisEdit(axis,'values',i,e.target.value === '' ? NaN : Number(e.target.value))}/></label>
          </div>)}</fieldset>)}
          <label>幅值单位<select aria-label="幅值单位" value={calibration.amplitude.unit} onChange={e => setCalibration(c => ({...c, amplitude:{...c.amplitude,unit:e.target.value}}))}><option value="pixel">相对像素</option><option value="dimensionless">无量纲</option><option value="modes/THz">modes/THz</option><option value="unknown">其他 / 待核对</option>{!['pixel','dimensionless','modes/THz','unknown'].includes(calibration.amplitude.unit)&&<option value={calibration.amplitude.unit}>{calibration.amplitude.unit}</option>}</select></label>
          {kind==='alpha2f' && <p className="muted">ωlog直接使用相对谱形；论文已有λ用于确定幅值倍率。保存后点击重新计算，无需填写说明。</p>}
          <button className="secondary" onClick={applyCalibration}>应用标定</button><p className="muted">保留原图像素位置，只重新换算数值。</p>
        </div></details></section>
        <section className="panel-section"><h3>逐点数据</h3><PointTable doc={doc} active={active} selected={selected} onSelect={setSelected} compact/></section>
      </aside></div>
    </fieldset></main>
    {exitIntent && <div className="modal-backdrop"><div role="dialog" aria-modal="true" aria-labelledby="leave-title" className="modal">
      <span className="eyebrow">UNSAVED CHANGES</span><h2 id="leave-title">保留这次调整吗？</h2>
      <p>{exitIntent.kind==='switch'?'当前修改尚未保存到数据库。保存后将继续编辑 '+samples.find(s=>s.id===exitIntent.id)?.curves[0].name+'。':'当前修改尚未保存到数据库。'}</p>
      {error&&<div role="alert" className="callout error">{error}</div>}
      <div className="modal-actions">
        <button disabled={saving} onClick={() => setExitIntent(null)}>{exitIntent.kind==='switch'?'留在当前元素':'继续编辑'}</button>
        <button disabled={saving} className="danger" onClick={() => {
          const intent=exitIntent;setExitIntent(null)
          if(intent.kind==='switch')switchSample(intent.id)
          else onClose()
        }}>放弃修改</button>
        <button disabled={saving} className="primary" onClick={() => void save(exitIntent.kind==='switch'?exitIntent.id:undefined)}>
          {saving?'正在保存…':exitIntent.kind==='switch'?'保存并继续编辑':'保存并返回'}
        </button>
      </div>
    </div></div>}
  </div>
}
