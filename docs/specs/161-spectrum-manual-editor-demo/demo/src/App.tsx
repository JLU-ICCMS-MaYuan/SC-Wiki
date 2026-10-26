import { useEffect, useRef, useState } from 'react'
import SourceCanvas, { type Tool } from './SourceCanvas'
import fixtures from './fixtures.json'
import { amplitude, amplitudePixel, axisValid, clone, commit, frequency, frequencyPixel, move, restoreManualMarkers, ordered, pixelAt, record, redo, removePoints, undo, validateDocument, zeroCovered, type Axis, type Document, type History, type Point } from './engine'

const samples = fixtures as unknown as Document[]
samples.forEach(sample => validateDocument(sample, sample))
const storageKey = (id: string) => 'scwiki-spectrum-manual-v1:' + id
const number = (n: number) => Number.isFinite(n) ? Number(n.toFixed(4)).toString() : '—'
function load(initial: Document) {
  try {
    const value = localStorage.getItem(storageKey(initial.id))
    if (!value) return { doc: clone(initial), error: '', blocked: false }
    const doc: unknown = JSON.parse(value); validateDocument(doc, initial)
    return { doc: restoreManualMarkers(doc, initial), error: '', blocked: false }
  } catch { return { doc: clone(initial), error: '本机草稿不可读取或校验失败，未覆盖原草稿。请检查浏览器存储，或显式恢复原始提取后重新保存。', blocked: true } }
}

function PointForm({ doc, point, onApply }: { doc: Document; point: Point; onApply: (f: number, a: number) => void }) {
  const initialF = String(Number(frequency(doc, point).toFixed(6))), initialA = String(Number(amplitude(doc, point).toFixed(6)))
  const [f, setF] = useState(initialF), [a, setA] = useState(initialA)
  return <form onSubmit={e => { e.preventDefault(); onApply(f === initialF ? frequency(doc, point) : Number(f), a === initialA ? amplitude(doc, point) : Number(a)) }} className="coordinate-form">
    <label>频率 / {doc.calibration.frequency.unit}<input aria-label="选中点频率" type="number" step="any" required value={f} onChange={e => setF(e.target.value)} /></label>
    <label>幅值 / {doc.calibration.amplitude.unit === 'pixel' ? '相对像素' : doc.calibration.amplitude.unit}<input aria-label="选中点幅值" type="number" step="any" required value={a} onChange={e => setA(e.target.value)} /></label>
    <p className="muted">源像素 x {number(point.x)} · y {number(point.y)}<br/>{point.status}</p>
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

export default function App() {
  const [sampleId, setSampleId] = useState('alpha2f'), initial = samples.find(s => s.id === sampleId)!
  const [loaded] = useState(() => load(samples[0]))
  const [saved, setSaved] = useState<Document>(loaded.doc), [history, setHistory] = useState<History>({ past: [], present: loaded.doc, future: [] })
  const doc = history.present
  const [editor, setEditor] = useState(false), [active, setActive] = useState(doc.curves[0].id), [selected, setSelected] = useState<string[]>([])
  const [tool, setTool] = useState<Tool>('select'), [linked, setLinked] = useState(true), [dragMode, setDragMode] = useState<'amplitude' | 'free'>('amplitude')
  const [display, setDisplay] = useState('overlay'), [all, setAll] = useState(true)
  const [error, setError] = useState(loaded.error), [blocked, setBlocked] = useState(loaded.blocked), [notice, setNotice] = useState('')
  const [exitModal, setExitModal] = useState(false), exitAction = useRef<() => void>(() => {})
  const [calibration, setCalibration] = useState(clone(doc.calibration)), [pick, setPick] = useState<{ axis: 'frequency' | 'amplitude'; index: 0 | 1 } | null>(null)
  const curve = doc.curves.find(c => c.id === active)!, point = curve.points.find(p => p.id === selected[0])
  const calibrationDirty = JSON.stringify(calibration) !== JSON.stringify(doc.calibration)
  const dirty = JSON.stringify(doc) !== JSON.stringify(saved) || calibrationDirty, covered = zeroCovered(doc, active)
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
      if (!editor || (e.target as HTMLElement).closest('input,select,textarea')) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); setHistory(h => e.shiftKey ? redo(h) : undo(h)) }
      if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); remove() }
      if (e.key === 'Escape') { setTool('select'); setPick(null); setSelected([]) }
    }
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key)
  }, [doc, selected, active, editor])
  const selectCurve = (id: string) => { setActive(id); setSelected([]) }
  const save = (): boolean => {
    try {
      if (calibrationDirty) throw new Error('标定表单还有未应用的修改，请先应用标定，再保存。')
      if (blocked) throw new Error('旧草稿不可读取，需先显式恢复原始提取，才能替换本机草稿。')
      validateDocument(doc, initial)
      localStorage.setItem(storageKey(sampleId), JSON.stringify(doc))
      setSaved(clone(doc)); setHistory({ past: [], present: clone(doc), future: [] }); setEditor(false); setError(''); setSelected([])
      setNotice('调整已保存在此浏览器的 Demo 草稿中，刷新后可恢复。尚未写入 SC-Wiki 数据库。')
      return true
    } catch (e) { setError('保存失败：' + (e as Error).message); return false }
  }
  const leave = (action: () => void) => {
    if (!dirty) return action()
    exitAction.current = action; setExitModal(true)
  }
  const switchSample = (id: string) => {
    const next = samples.find(s => s.id === id)!, state = load(next)
    setSampleId(id); setSaved(state.doc); setHistory({ past: [], present: state.doc, future: [] }); setActive(next.curves[0].id)
    setSelected([]); setEditor(false); setError(state.error); setBlocked(state.blocked); setNotice(''); setAll(true); setTool('select')
  }
  const restore = () => {
    change(record({ ...clone(initial), operations: doc.operations }, 'restore', '恢复不可变初始提取样本'))
    setBlocked(false); setSelected([]); setTool('select'); setError('')
  }
  const applyCoordinates = (f: number, a: number) => {
    if (!point || ![f, a].every(Number.isFinite)) { setError('坐标必须是有限数值'); return }
    const fp = pixelAt(doc.calibration.frequency, f), ap = pixelAt(doc.calibration.amplitude, a)
    const next = move(doc, active, point.id, (doc.calibration.direction === 'x' ? fp : ap) - point.x, (doc.calibration.direction === 'y' ? fp : ap) - point.y, false, 'free')
    change(next, '输入坐标修改单点（越界或交叉时限制到有效位置）')
  }
  const axisEdit = (axis: 'frequency' | 'amplitude', field: 'pixels' | 'values', index: 0 | 1, value: number) => setCalibration(c => {
    const next = clone(c); next[axis][field][index] = value; return next
  })
  const applyCalibration = () => {
    if (!axisValid(calibration.frequency) || !axisValid(calibration.amplitude)) { setError('每根轴的两个位置和数值必须有限、互不重合'); return }
    if (calibration.amplitude.unit !== 'pixel' && !calibration.amplitudeEvidence.trim()) { setError('填写物理幅值刻度前，请注明来自原图何处的幅值依据；不能借用累计 λ'); return }
    const next = record({ ...doc, calibration: clone(calibration), zero: null }, 'calibration', '修改线性标定，保留全部源像素位置；零频选点需重新核对')
    try { validateDocument(next, initial); change(next); setTool('select'); setPick(null) } catch (e) { setError((e as Error).message) }
  }
  const displayedRange = curve.points.length ? (() => { const ps = ordered(doc, curve.points); return number(frequency(doc, ps[0])) + '–' + number(frequency(doc, ps.at(-1)!)) + ' ' + doc.calibration.frequency.unit })() : '尚无数据点'
  const zeroWarning = <div className={'callout ' + (covered ? 'info' : 'warning')} data-testid="zero-status">{covered ? '已记录原图零频位置与当前曲线的人工选点；科学依据仍待核对。' : '零频提取不完整：先标记原图真实 0 频率位置，再在曲线上补选零频数据点。'}</div>
  const curvePicker = <div className="curve-picker">{doc.curves.map(c => <button key={c.id} className={active === c.id ? 'active' : ''} onClick={() => selectCurve(c.id)}><i style={{ background: c.color }}/>{c.name}<span>{c.points.length}</span></button>)}</div>
  const selectedPanel = <section className="panel-section"><div className="section-heading"><h3>选中点</h3><span className="badge">{selected.length} 个</span></div>
    {selected.length === 1 && point ? <PointForm key={point.id + ':' + point.x + ':' + point.y + ':' + JSON.stringify(doc.calibration)} doc={doc} point={point} onApply={applyCoordinates} /> : <p className="muted">在图上点选或框选，也可在下方数据表中选择。</p>}
    <button className="danger" disabled={!selected.length} onClick={remove}>删除选中点{selected.length > 1 ? `（${selected.length}）` : ''}</button>
  </section>
  return <div className={editor ? 'app editor-app' : 'app'}>
    {!editor && <aside className="site-sidebar"><a className="brand" href="#"><b>SC</b><strong>SC-Wiki</strong></a><nav><span>⌂　热点</span><span>⌕　探索</span><span>◇　脉络</span><span>♧　社区</span><span className="nav-active">↑　上传</span><span>▤　对话</span></nav><div className="sidebar-foot"><span className="avatar">M</span><div>谱线编辑体验<small>本机交互 Demo</small></div></div></aside>}
    <main>
      {editor ? <header className="editor-header"><button onClick={() => leave(() => { setEditor(false); setSelected([]) })}>← 返回详情</button><div><strong>{doc.title} · 人工调整</strong><span className="badge">{dirty ? '未保存' : '本机草稿'}</span></div><div className="header-actions"><button disabled={!history.past.length} onClick={() => setHistory(undo)}>↶ 撤销</button><button disabled={!history.future.length} onClick={() => setHistory(redo)}>↷ 重做</button><button onClick={restore}>恢复原始提取</button><button className="primary" onClick={() => save()}>保存调整</button></div></header>
        : <><div className="breadcrumbs">上传 / 材料状态 / 谱数据详情</div><header className="page-header"><div><p className="eyebrow">SPECTRUM WORKSPACE</p><h1>{doc.title}解析详情</h1><p className="muted">从原图出发，让每一个数据点都可核对。</p></div><div className="tabs">{samples.map(s => <button key={s.id} className={s.id === sampleId ? 'active' : ''} onClick={() => leave(() => switchSample(s.id))}>{s.title}</button>)}</div></header><div className="demo-banner"><span>交互 Demo</span>固定原图与演示点 · 保存仅在此浏览器 · 尚未连接数据库</div></>}
      {error && <div role="alert" className="callout error">{error}</div>}{notice && <div role="status" className="callout success">{notice}</div>}
      {editor ? <div className="editor-layout"><section className="workbench">
        <div className="tool-strip">{([['select','↖ 选点 / 拖动'],['pan','✥ 平移'],['add','＋ 增加点'],['box','▣ 框选']] as [Tool,string][]).map(([value,label]) => <button key={value} className={tool === value ? 'active' : ''} onClick={() => { setTool(value); setPick(null) }}>{label}</button>)}<div className="tool-strip-end"><label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)}/>显示其他分波</label><button onClick={() => setDisplay(display === 'overlay' ? 'data' : 'overlay')}>{display === 'overlay' ? '隐藏原图' : '显示原图'}</button></div></div>
        <div className="tool-hint">{tool === 'zero' ? '在原图真实零频刻度处点击，橙色线只表示标定位置。' : tool === 'zeroPoint' ? '在橙色零频线上的真实曲线位置点击，幅值取自你的点击。' : tool === 'calibrate' ? `在原图上点选${pick?.axis === 'frequency' ? '频率' : '幅值'}轴的第 ${(pick?.index || 0) + 1} 个刻度位置，然后输入对应值。` : tool === 'add' ? '点击补点，自动连到当前曲线前后相邻点；只画连线，不插值补点。' : tool === 'box' ? '拖出选区后点击“删除选中点”，误识别区域将保留为空缺。' : '选择一个点，拖动修正局部形状。两侧各 5 个邻点明显跟随，更远点指数衰减。'}</div>
        <SourceCanvas doc={doc} active={active} selected={selected} editing tool={tool} linked={linked} dragMode={dragMode} display={display} all={all} onSelect={setSelected} onChange={change} onError={setError} onPick={(x,y) => {
          if (!pick) return
          const direction = pick.axis === 'frequency' ? calibration.direction : calibration.direction === 'x' ? 'y' : 'x'
          axisEdit(pick.axis, 'pixels', pick.index, direction === 'x' ? x : y); setTool('select'); setPick(null)
        }}/>
        <footer className="workbench-footer"><span><i style={{ background: curve.color }}/>{curve.name} · {curve.points.length} 个点</span><span>{displayedRange}</span><span>{doc.operations.length} 次人工操作</span></footer>
      </section><aside className="inspector">
        <section className="panel-section"><div className="section-heading"><h3>编辑曲线</h3><span className="tag">单条编辑</span></div>{curvePicker}<p className="muted">{sampleId === 'phdos' ? '其他分波只作参照，不随当前曲线移动。' : '累计 λ 只在原图中参照，不作为 α²F 幅值刻度。'}</p></section>
        <section className="panel-section"><div className="section-heading"><h3>局部形状调整</h3><label className="switch"><input aria-label="附近点联动" type="checkbox" checked={linked} onChange={e => setLinked(e.target.checked)}/><span>附近点联动</span></label></div>
          <div className="segmented"><button className={dragMode === 'amplitude' ? 'active' : ''} onClick={() => setDragMode('amplitude')}>只改幅值</button><button className={dragMode === 'free' ? 'active' : ''} onClick={() => setDragMode('free')}>自由移动</button></div>
          <p className="range-label">主要影响区 <strong>两侧各 5 个点</strong></p>
          <p className="muted">按频率顺序计数。前 5 个邻点明显跟随，之后指数衰减；很远的点不动。未连接的断口和其他分波不受影响。{dragMode === 'amplitude' && `当前频率沿${doc.calibration.direction === 'y' ? '竖轴，左右' : '横轴，上下'}拖动改变幅值。`}</p>
        </section>
        {selectedPanel}
        <section className="panel-section"><h3>零频边界</h3>{zeroWarning}<div className="stack"><button className={tool === 'zero' ? 'active' : ''} onClick={() => setTool('zero')}>1 · 标记原图 0 频率位置</button><button disabled={!doc.zero} className={tool === 'zeroPoint' ? 'active' : ''} onClick={() => setTool('zeroPoint')}>2 · 补选曲线零频点</button></div><p className="muted">零频率不代表零幅值。看不清时保留待核对。</p></section>
        <section className="panel-section"><details><summary>坐标标定 <span>线性 · 两点</span></summary><div className="calibration-form">
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
          <label>幅值单位<select aria-label="幅值单位" value={calibration.amplitude.unit} onChange={e => setCalibration(c => ({...c, amplitude:{...c.amplitude,unit:e.target.value}}))}><option value="pixel">相对像素（刻度待核对）</option><option value="dimensionless">无量纲</option><option value="modes/THz">modes/THz</option><option value="unknown">其他 / 待核对</option></select></label>
          <label>幅值标定依据<textarea aria-label="幅值标定依据" value={calibration.amplitudeEvidence} placeholder="来自原图哪条轴、哪组刻度；不要填写累计 λ 的刻度" onChange={e => setCalibration(c => ({...c,amplitudeEvidence:e.target.value}))}/></label>
          <button className="secondary" onClick={applyCalibration}>应用标定</button><p className="muted">保留原图像素位置，只重新换算数值。修改后需重新核对零频选点。</p>
        </div></details></section>
        <section className="panel-section"><h3>逐点数据</h3><PointTable doc={doc} active={active} selected={selected} onSelect={setSelected} compact/></section>
      </aside></div> : <>
        <section className="card material-card"><div><span className="section-number">01</span><h2>材料与来源</h2></div><div className="material-body"><div><strong>LaSc₂H₂₄ <span className="muted">· 290 GPa</span></strong><p className="muted">来源图 A · {doc.title} · 固定图像与演示点</p></div><span className="status-pill">待人工核对</span></div></section>
        <div className="analysis-grid"><section className="card plot-card"><div className="card-title"><div><span className="section-number">02</span><h2>原图与提取结果</h2></div><button className="primary" onClick={() => { setEditor(true); setSelected([]); setTool('select'); setDisplay('overlay'); setNotice('') }}>✎ 编辑</button></div>
          <div className="segmented view-switch">{[['source','仅原图'],['data','仅提取数据'],['overlay','原图与数据叠加']].map(([v,label]) => <button key={v} className={display === v ? 'active' : ''} onClick={() => setDisplay(v)}>{label}</button>)}</div>
          {doc.curves.length > 1 && <div className="detail-curves">{curvePicker}<label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)}/>全部分波</label></div>}
          <SourceCanvas doc={doc} active={active} selected={[]} display={display} all={all}/><div className="plot-footnote"><span style={{color:curve.color}}>● {curve.name}</span><span>源图与提取点共用像素坐标</span></div>
        </section><div className="result-column"><section className="card"><div className="card-title"><div><span className="section-number">03</span><h2>{sampleId === 'phdos' ? '频段与数据完整性' : '积分结果与参考值对比'}</h2></div></div><div className="metric-pair"><div><small>实际数据频率范围</small><strong data-testid="frequency-range">{displayedRange}</strong></div><div><small>当前曲线数据点</small><strong>{curve.points.length} <small>个</small></strong></div></div>{zeroWarning}<div className="metric-placeholder"><span>{sampleId === 'phdos' ? '总振动模式数 / 3N 核验' : 'λ / ωlog 积分'}</span><strong>暂不可计算</strong></div><p className="muted">幅值刻度和科学依据待核对。人工选点或调整完成，不代表积分条件已满足。</p></section><section className="card guide-card"><span className="eyebrow">MANUAL CORRECTION</span><h2>把判断交还给你</h2><p>删掉图例误识别，补上漏掉的点，<br/>或揪住一个点，轻轻修正整段曲线。</p><ol><li>点击左侧“编辑”，放大原图。</li><li>选择曲线和数据点，调整局部形状。</li><li>保存后回到这里，查看修改结果。</li></ol><div className="callout info">本机 Demo 草稿 · 无下载与导出<br/>后续正式接入才会写入数据库。</div></section></div></div>
        <section className="card"><div className="card-title"><div><span className="section-number">04</span><h2>逐数据点核对</h2></div><span className="muted">{curve.name} · 幅值为{doc.calibration.amplitude.unit === 'pixel' ? '相对像素' : doc.calibration.amplitude.unit}</span></div><PointTable doc={doc} active={active} selected={selected} onSelect={setSelected}/></section>
      </>}
    </main>
    {exitModal && <div className="modal-backdrop"><div role="dialog" aria-modal="true" aria-labelledby="leave-title" className="modal"><span className="eyebrow">UNSAVED CHANGES</span><h2 id="leave-title">保留这次调整吗？</h2><p>当前修改尚未保存到本机草稿。</p><div className="modal-actions"><button onClick={() => setExitModal(false)}>继续编辑</button><button className="danger" onClick={() => { setHistory({past:[],present:clone(saved),future:[]}); setCalibration(clone(saved.calibration)); setExitModal(false); exitAction.current() }}>放弃修改</button><button className="primary" onClick={() => { if (save()) { setExitModal(false); exitAction.current() } }}>保存并返回</button></div></div></div>}
  </div>
}
