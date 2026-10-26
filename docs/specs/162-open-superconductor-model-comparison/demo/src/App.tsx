import { useEffect, useId, useRef, useState } from 'react'

type Dataset = { id: string; filename: string; name: string; description: string; license: string; version: string; source_url: string; original_url: string; rows: number | null; kind: string; size: number; sha256: string | null; available: boolean; error: string | null; download_url: string | null; download_label?: string }
type Model = { id: string; name: string; family: string; group: string; year: string; tagline: string; description: string; input: string; mode: string; datasets: string[]; paper: string | null; code: string | null; code_label?: string; license: string; boundary: string }
type Result = { model_id: string; tc: number | null; parameters: Record<string, number>; method: string; warning: string; elapsed_seconds: number; ensemble_size?: number; formula?: string; input_format?: 'cif' | 'vasp'; spectrum?: { frequency: number[]; a2f: number[]; unit: string }; label: string; run: number }

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  let data
  try { data = await response.json() }
  catch { throw new Error('计算服务暂时不可用，请检查本地服务后重试') }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败，请重试')
  return data
}
const size = (n: number) => n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${(n / 1024).toFixed(1)} KB`
// 同一个作者仓库的代码与数据共用入口，避免重复网址。
function sameWebsite(a: string | null, b: string) {
  if (!a) return false
  const first = new URL(a), second = new URL(b)
  const location = (url: URL) => url.hostname + (url.hostname === 'github.com' ? url.pathname.split('/').slice(0, 3).join('/') : url.pathname.replace(/\/$/, ''))
  return location(first) === location(second)
}
const value = (n: number) => n.toLocaleString('zh-CN', { maximumFractionDigits: 4 })

function Atom({ small = false }: { small?: boolean }) {
  return <svg className={small ? 'atom small' : 'atom'} viewBox="0 0 100 100" aria-hidden="true"><ellipse cx="50" cy="50" rx="40" ry="16"/><ellipse cx="50" cy="50" rx="40" ry="16" transform="rotate(60 50 50)"/><ellipse cx="50" cy="50" rx="40" ry="16" transform="rotate(120 50 50)"/><circle cx="50" cy="50" r="7"/><circle cx="78" cy="72" r="4"/></svg>
}
function Spectrum({ result }: { result: Result }) {
  const s = result.spectrum!
  const peak = Math.max(...s.a2f, .001)
  const points = s.a2f.map((y, i) => `${35 + s.frequency[i] / 100.25 * 600},${115 - y / peak * 88}`).join(' ')
  return <figure className="spectrum"><figcaption>预测 α²F(ω) <span>100 个网络的平均谱</span></figcaption><svg viewBox="0 0 660 155" role="img" aria-label="BETE-NET 真实预测的电子声子谱"><line x1="35" y1="115" x2="635" y2="115"/><line x1="35" y1="20" x2="35" y2="115"/><polyline points={points}/><text x="32" y="137">0</text><text x="320" y="137">50</text><text x="590" y="137">100 meV</text><text x="7" y="20">{peak.toFixed(2)}</text></svg></figure>
}

const parameterLabels: Record<string, string> = {
  lambda: 'λ', omega_log: 'ωlog / K', omega_2: 'ω₂ / K', mu_star: 'μ*',
  f2_value: 'E_couple（f₂）', dos_h_ratio: 'H DOS 占比', dos_h_atom_bond: '每原子／键 H PDOS',
  bonds_mean: 'H–H 均值 / Å', bonds_var: 'H–H 方差 / Å²',
}

function ResultRow({ result, name, onReuse }: { result: Result; name: string; onReuse: (result: Result) => void }) {
  const [expanded, setExpanded] = useState(false)
  const detailsId = useId()
  const parameters = Object.entries(result.parameters)
  const comparisonParameters = parameters.filter(([key]) => ['lambda', 'omega_log', 'mu_star'].includes(key))
  const summaryParameters = comparisonParameters.length ? comparisonParameters : parameters.slice(0, 3)
  const hasDetails = !!(parameters.length || result.spectrum || result.warning || result.method)
  return <article className="result-card" data-result={result.model_id} data-expanded={expanded}>
    <div className="result-summary">
      <div className="result-identity"><h3 title={name}>{name}</h3><p title={result.label}>{result.label}</p></div>
      <div className="result-inline-parameters">{summaryParameters.map(([key, val]) => <span key={key}>{parameterLabels[key] || key}<b>{value(val)}</b></span>)}</div>
      <div className="tc">{result.tc === null ? '不适用' : value(result.tc)}{result.tc !== null && <small>K</small>}<span>预测 T<sub>c</sub></span></div>
      <div className="result-actions">
        {hasDetails && <button className="result-toggle" aria-expanded={expanded} aria-controls={detailsId} onClick={() => setExpanded(open => !open)}>{expanded ? '折叠' : '展开'}</button>}
        {result.spectrum && <button className="result-compare" onClick={() => onReuse(result)}>用此参数对比 SISSO →</button>}
      </div>
    </div>
    {hasDetails && <div id={detailsId} className="result-details" role="region" aria-label={`${name}详细结果`} hidden={!expanded}>
      <p className="result-input">{result.label}</p>
      <div className="result-parameters">{parameters.map(([key, val]) => <span key={key}>{parameterLabels[key] || key}<b>{value(val)}</b></span>)}</div>
      {result.spectrum && <Spectrum result={result}/>}
      <p className="hint">{result.warning}</p>
      <div className="result-footer"><small>{result.input_format && `输入：${result.input_format === 'cif' ? 'CIF' : 'POSCAR / CONTCAR'} · `}{result.elapsed_seconds}s · {result.ensemble_size ? `${result.ensemble_size} 个网络 · ` : ''}{result.method}</small></div>
    </div>}
  </article>
}

function PredictionGroups({ group, onChange }: { group: string; onChange: (group: string) => void }) {
  return <nav className="prediction-groups" aria-label="预测分类">
    <button aria-pressed={group === 'ambient'} onClick={() => onChange('ambient')}>常压 BCS 超导体</button>
    <button aria-pressed={group === 'hydride'} onClick={() => onChange('hydride')}>高压氢化物</button>
  </nav>
}

export default function App() {
  const [catalog, setCatalog] = useState<{ models: Model[]; datasets: Dataset[] } | null>(null)
  const [group, setGroup] = useState('ambient')
  const [selected, setSelected] = useState('bete-cso')
  const [structure, setStructure] = useState('')
  const [format, setFormat] = useState('auto')
  const [label, setLabel] = useState('自定义结构')
  const [parameters, setParameters] = useState({ lambda: '1.55', omega_log: '56', omega_2: '80', mu_star: '0.105' })
  const [parameterLabel, setParameterLabel] = useState('Pb · 作者训练参数')
  const [contcarFile, setContcarFile] = useState<File | null>(null)
  const [pdosFiles, setPdosFiles] = useState<File[]>([])
  const [running, setRunning] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [notice, setNotice] = useState('')
  const resultSection = useRef<HTMLElement>(null)
  const categoryDialog = useRef<HTMLDialogElement>(null)
  const groupLabel = group === 'ambient' ? '常压 BCS 超导体' : '高压氢化物'
  const model = catalog?.models.find(m => m.id === selected)
  const sharedWebsite = !!model?.code && !!model.datasets.length && model.datasets.every(id => sameWebsite(model.code, catalog!.datasets.find(d => d.id === id)!.source_url))

  const load = () => { setError(''); api<{ models: Model[]; datasets: Dataset[] }>('/demo-api/catalog').then(setCatalog).catch(e => setError(`目录加载失败：${e.message}`)) }
  useEffect(load, [])
  useEffect(() => { if (!running) return; setSeconds(0); const timer = setInterval(() => setSeconds(s => s + 1), 1000); return () => clearInterval(timer) }, [running])
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 3000); return () => clearTimeout(timer) }, [notice])

  function changeGroup(next: string) {
    if (next !== group) { setGroup(next); setSelected(next === 'ambient' ? 'bete-cso' : 'sisso-2022'); setError('') }
    categoryDialog.current?.close()
  }
  async function sample(id: string) {
    try { const data = await api<{ structure: string; format: string; note: string }>(`/demo-api/examples/${id}`); setStructure(data.structure); setFormat('auto'); setLabel(`${id.toUpperCase()} · 作者结构样本`); setNotice(data.note); setError('') }
    catch (e) { setError((e as Error).message) }
  }
  async function upload(file?: File) {
    if (!file) return
    if (file.size > 256 * 1024) { setError('结构文件不能超过 256 KiB'); return }
    setStructure(await file.text()); setFormat('auto'); setLabel(file.name); setError('')
  }
  async function run() {
    if (!model || running) return
    setRunning(model.id); setError('')
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 180000)
    const started = performance.now()
    const currentLabel = model.mode === 'legacy' ? `${contcarFile?.name} · ${pdosFiles.length} 个 PDOS 文件` : model.mode === 'structure' ? label : parameterLabel
    try {
      let data: Omit<Result, 'label' | 'run'>
      if (model.mode === 'legacy') {
        if (!contcarFile || !pdosFiles.length) throw new Error('请上传结构和 PDOS 文件')
        const form = new FormData()
        form.append('contcar', contcarFile)
        pdosFiles.forEach(file => form.append('pdos_files', file))
        // 直接复用主站原接口及原字段，不复制或修改原预测公式。
        const raw = await api<{ predicted_tc: number; f2_value: number; dos_h_ratio: number; dos_h_atom_bond: number; bonds_mean: number; bonds_var: number }>('/api/tc-predict/', { method: 'POST', body: form, signal: controller.signal })
        data = { model_id: model.id, tc: raw.predicted_tc, parameters: { f2_value: raw.f2_value, dos_h_ratio: raw.dos_h_ratio, dos_h_atom_bond: raw.dos_h_atom_bond, bonds_mean: raw.bonds_mean, bonds_var: raw.bonds_var }, method: 'Tc assessment model · E_couple', warning: model.boundary, elapsed_seconds: Math.round((performance.now() - started)) / 1000 }
      } else {
        data = await api<Omit<Result, 'label' | 'run'>>('/demo-api/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: model.id, structure, format, parameters }), signal: controller.signal })
      }
      setResults(previous => [{ ...data, label: currentLabel, run: Date.now() }, ...previous].slice(0, 8))
      setTimeout(() => resultSection.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    } catch (e) { setError((e as Error).name === 'AbortError' ? '等待超过 180 秒；服务器可能仍在计算，请稍后重试。' : (e as Error).message) }
    finally { clearTimeout(timer); setRunning(null) }
  }
  function reuse(result: Result) {
    const p = result.parameters
    setParameters({ lambda: String(p.lambda), omega_log: String(p.omega_log), omega_2: String(p.omega_2 || p.omega_log), mu_star: String(p.mu_star) })
    setParameterLabel(`${result.formula || result.label} · 来自 BETE-NET 的预测参数`); setGroup('ambient'); setSelected('sisso-2019'); window.scrollTo({ top: 260, behavior: 'smooth' })
  }

  return <div className="app">
    <aside className="rail"><a className="brand" href="http://127.0.0.1:5173" aria-label="返回 SC-Wiki"><span className="brand-mark">SC</span><b>SC-Wiki</b></a><div className="rail-label">研究工作台</div><a href="http://127.0.0.1:5173/search"><span>⌕</span> 探索</a><a href="http://127.0.0.1:5173/share"><span>◌</span> 社区</a><a className="active" href="#prediction"><span>✧</span> 预测</a><PredictionGroups group={group} onChange={changeGroup}/><div className="rail-bottom"><span className="live-dot"/> 本地 Demo<br/><small>原生实时开发环境</small></div></aside>
    <main>
      <header className="topbar"><span>预测 <i>/</i> {groupLabel}</span><button className="mobile-category-trigger" aria-haspopup="dialog" onClick={() => categoryDialog.current?.showModal()}>选择分类</button></header>
      <section className="hero" id="prediction"><div><div className="eyebrow"><span/> OPEN MODELS · OPEN DATA</div><h1>预测<span>Beta</span></h1><p>让预测有对照，让数据可追溯。<br className="mobile-break"/>选择模型，运行真实计算，查看它从哪些数据中学习。</p></div><div className="hero-art"><Atom/><div className="orbit-label">α²F → T<sub>c</sub></div></div></section>
      {error && <div className="error" role="alert">{error}{!catalog && <button onClick={load}>重新加载</button>}</div>}
      {!catalog ? <div className="loading">正在读取模型与数据文件状态…</div> : <>
        <nav className="model-picker" aria-label="选择模型">{catalog.models.filter(m => m.group === group).map(m => <button key={m.id} aria-pressed={selected === m.id} className={selected === m.id ? 'selected' : ''} onClick={() => { setSelected(m.id); setError('') }}><span className="picker-icon">{m.mode === 'structure' ? '◈' : 'ƒ'}</span><span><b>{m.name}</b><small>{m.mode === 'pending' ? '资料候选' : m.family}</small></span>{selected === m.id && <span className="selected-dot"/>}</button>)}</nav>
        {model && <section className="workspace" key={model.id}>
          <div className="model-panel"><div className="model-heading"><span className="pill">{model.family}</span><span className="subtle">{model.year}</span><h2>{model.name}</h2><h3>{model.tagline}</h3><p>{model.description}</p></div>
            <div className="runner"><div className="section-title"><span className="step">1</span><h3>准备模型输入</h3><span className="subtle">{model.input}</span></div>
              {model.mode === 'structure' && <><div className="input-toolbar"><label className="upload">＋ 上传结构<input type="file" accept=".cif,.vasp,.poscar,CONTCAR,POSCAR" onChange={e => upload(e.target.files?.[0])}/></label><select aria-label="结构格式" value={format} onChange={e => setFormat(e.target.value)}><option value="auto">自动识别</option><option value="cif">CIF</option><option value="vasp">POSCAR / CONTCAR</option></select></div><div className="samples">试用作者样本 <button onClick={() => sample('nb')}>Nb 铌</button><button onClick={() => sample('pb')}>Pb 铅</button><button onClick={() => sample('al')}>Al 铝</button></div><label className="field-label" htmlFor="structure">{label}</label><textarea id="structure" className="structure" spellCheck={false} placeholder="上传文件，或在这里粘贴完整的晶体结构…" value={structure} onPaste={() => { setFormat('auto'); setError('') }} onChange={e => { setStructure(e.target.value); setLabel('自定义结构'); setError('') }}/><p className="hint">上传或粘贴后自动识别 CIF / POSCAR，也可手动指定。无需电子 PDOS，最多 80 个原子。</p></>}
              {model.mode === 'parameters' && <><div className="parameter-caption">{parameterLabel} <button className="text-button" onClick={() => { setParameters(model.id === 'sisso-2019' ? { lambda: '1.55', omega_log: '56', omega_2: '80', mu_star: '0.105' } : { lambda: '2', omega_log: '1000', omega_2: '1500', mu_star: '0.1' }); setParameterLabel(model.id === 'sisso-2019' ? 'Pb · 作者训练参数' : '示例参数 · 不对应特定材料') }}>加载示例</button></div><div className="parameter-grid">{(['lambda', 'omega_log', ...(model.id === 'sisso-2022' ? ['omega_2'] : []), 'mu_star'] as (keyof typeof parameters)[]).map(key => <label key={key}><span>{{ lambda: 'λ', omega_log: 'ωlog', omega_2: 'ω₂', mu_star: 'μ*' }[key]}<small>{key.startsWith('omega') ? 'K' : '无量纲'}</small></span><input aria-label={key} inputMode="decimal" value={parameters[key]} onChange={e => { setParameters(p => ({ ...p, [key]: e.target.value })); setParameterLabel('自定义 EPC 参数') }}/></label>)}</div><div className="formula">{model.id === 'sisso-2019' ? <>T<sub>c</sub> = 0.09525 λ⁴ ω<sub>log</sub> / (λ³ + √μ*)</> : <>T<sub>c</sub> = f<sub>ω</sub> · f<sub>μ</sub> · T<sub>McMillan</sub><small>采用原论文式 (6)–(8)，不是重新拟合的模型。</small></>}</div><p className="hint">请使用同一材料、同一计算条件下的参数。频率统一以 K 输入。</p></>}
              {model.mode === 'legacy' && <>
                <div className="legacy-files">
                  <label className="file-upload"><b>CONTCAR / POSCAR</b><span>{contcarFile?.name || '选择晶体结构文件'}</span><input aria-label="CONTCAR / POSCAR 文件" type="file" onChange={e => { setContcarFile(e.target.files?.[0] || null); setError('') }}/></label>
                  <label className="file-upload"><b>电子 PDOS</b><span>{pdosFiles.length ? `已选择 ${pdosFiles.length} 个文件` : '选择 PDOS_H.dat 和金属 PDOS 文件'}</span><input aria-label="电子 PDOS 文件" type="file" multiple onChange={e => { setPdosFiles(Array.from(e.target.files || [])); setError('') }}/></label>
                </div>
                {pdosFiles.length > 0 && <ul className="selected-files">{pdosFiles.map((file, i) => <li key={`${file.name}-${i}`}>{file.name}</li>)}</ul>}
                <div className="formula">T<sub>c</sub> = 16370.6 E<sub>couple</sub> + 24.7</div>
                <p className="hint">包含 PDOS_H.dat，最多使用前 4 个金属 PDOS 文件。沿用原接口的费米能级和 H–H 距离处理约定。</p>
              </>}
              {model.mode === 'pending' && <div className="empty-state"><span>◌</span><h3>先查看数据，推理尚未接入</h3><p>右侧可以下载作者原始数据，并访问模型来源。</p></div>}
              {['structure', 'parameters', 'legacy'].includes(model.mode) && <button className="primary run" onClick={run} disabled={!!running || (model.mode === 'structure' && !structure.trim()) || (model.mode === 'legacy' && (!contcarFile || !pdosFiles.length))}>{running === model.id ? <><span className="spinner"/> 正在真实计算 · {seconds}s</> : running ? '另一模型正在计算…' : <>运行模型 <span>→</span></>}</button>}
              <div className="boundary"><span>i</span><p>{model.boundary}</p></div>
            </div>
          </div>
          <aside className="data-panel">
            <section className="model-sources"><h3>模型来源</h3><div className="model-links">{model.paper && <a href={model.paper} target="_blank" rel="noreferrer">论文链接</a>}{model.code && <a href={model.code} target="_blank" rel="noreferrer" title={sharedWebsite ? '作者代码和数据所在网站' : undefined}>{model.code_label || (sharedWebsite ? '原始网站' : '模型代码')}</a>}</div></section>
            {model.datasets.map(id => catalog.datasets.find(d => d.id === id)!).map(file => <article className="dataset" key={file.id} data-dataset={file.id}>
              <div className="dataset-top"><span className="file-icon">{file.filename.split('.').pop()?.toUpperCase()}</span><span className={file.available ? 'status ready' : 'status unavailable'}>{file.available ? '可下载' : '暂不可用'}</span></div>
              <h4>{file.name}</h4><div className="data-facts"><span>{file.rows ? `${file.rows} 条` : '作者发布归档'}</span><span>{size(file.size)}</span></div><p>{file.description}</p>
              <div className="data-actions">{file.download_url ? <a className="download" href={file.download_url} download>↓ {file.download_label || '下载原文件'}</a> : <button disabled className="download">暂不可下载</button>}</div>
              {!sameWebsite(model.code, file.source_url) && <a className="source-link" href={file.source_url} target="_blank" rel="noreferrer">原始网站</a>}
            </article>)}
            {!model.datasets.length && <div className="dataset unavailable-dataset"><h4>训练／校准数据待核实</h4><p>已核对论文模型名称和公式；原始训练文件及其下载授权仍待核实。请通过上方论文查看方法和数据说明。</p></div>}
          </aside>
        </section>}
        <section className="results" ref={resultSection}><div className="results-heading"><div><div className="eyebrow">RESULTS</div><h2>本次运行结果 <span>{results.length}</span></h2></div>{results.length > 0 && <button className="text-button" onClick={() => setResults([])}>清空结果</button>}</div>{!results.length ? <div className="results-empty"><span>↗</span><p>运行一个模型，真实结果会显示在这里。<small>你可以继续运行其他模型，对照输入条件与预测结果。</small></p></div> : <><p className="hint">按次保留原始结果，不自动平均。不同输入条件的数值不能直接当作模型精度比较。</p><div className="result-list">{results.map(result => <ResultRow key={result.run} result={result} name={catalog.models.find(m => m.id === result.model_id)?.name || result.model_id} onReuse={reuse}/>)}</div></>}</section>
      </>}
      <footer className="footer"><span>SC-Wiki · 开放模型与可追溯训练数据</span><span>本地 Demo · 预测结果不写入材料数据库</span></footer>
    </main>
    <dialog ref={categoryDialog} className="category-dialog" aria-label="预测分类菜单"><div className="category-dialog-heading"><h2>预测</h2><button aria-label="关闭分类菜单" onClick={() => categoryDialog.current?.close()}>×</button></div><PredictionGroups group={group} onChange={changeGroup}/></dialog>
    {notice && <div role="status" className="toast">{notice}</div>}
  </div>
}
