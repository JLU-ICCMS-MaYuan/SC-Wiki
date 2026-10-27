import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, Select, TextField, Typography, Accordion, AccordionSummary, AccordionDetails, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { api } from '../lib/api'
import { newStableKey } from '../lib/propertyModules'

export type SpectrumTarget = { target: 'upload' | 'paper' | 'revision'; target_id: string }
type Point = { frequency_thz: number; frequency_pixel: number; observed_amplitude: number | null; reconstructed_amplitude: number | null; status: string; detection_mode?: string; amplitude_pixel?: number }
type Curve = { id: string; kind: string; projection: string | null; points: Point[]; unit: string; clipped_frequencies_thz: number[]; frequency_direction: string; axis_calibration: { amplitude: { slope: number; intercept: number } } }
type Item = { id: string; version: number; state_key: string | null; stale: boolean; source: { size_px: number[]; pdf_page: number; source_name: string }; run: { status: string; error_message?: string }; review: Record<string, any>; result: { curves: Curve[]; quality: any; candidates: any; calibration: any; failures: any[] } }
type Listing = { items: Item[]; jobs: any[]; version: string; can_edit: boolean; can_review: boolean }
type Workspace = { target: SpectrumTarget; listing: Listing | null; reload: () => Promise<void>; beforeEdit?: () => Promise<boolean>; states: Array<{ state_key?: string; material?: string; material_name?: string | null }>; readOnly: boolean; error: string }
const Context = createContext<Workspace | null>(null)
const base = '/api/rag/spectra'
const query = (target: SpectrumTarget) => new URLSearchParams(target).toString()
const num = (v: unknown, digits = 3) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '无法计算'
const names: Record<string,string> = { phonon_dos: '声子 DOS', alpha2f: 'α²F', cumulative_lambda: '累计 λ', observed: '原图观测', interpolated: '短缺口插值', baseline_inferred: '近轴推断', boundary_assumption: '边界假设', edge_continuation: '平台延续', missing: '缺失', needs_review: '待核对', accepted: '已采纳', accepted_limited: '限定频段采纳', excluded: '已排除', queued: '排队中', running: '提取中', succeeded: '已完成', failed: '失败' }

export function SpectrumProvider({ target, states = [], beforeEdit, readOnly = false, children }: React.PropsWithChildren<{ target?: SpectrumTarget; states?: Workspace['states']; beforeEdit?: Workspace['beforeEdit']; readOnly?: boolean }>) {
  const [listing, setListing] = useState<Listing | null>(null), [error, setError] = useState('')
  const key = target ? query(target) : ''
  const reload = useCallback(async () => {
    if (!key) return
    try {
      const result=await api.get<Listing>(`${base}?${key}`)
      if(!Array.isArray(result?.items)||!Array.isArray(result?.jobs))throw new Error('谱服务返回结构无效')
      setListing(result);setError('')
    }
    catch (e) { setError((e as Error).message) }
  }, [key])
  useEffect(() => { setListing(null); setError(''); void reload() }, [reload])
  const busy = Boolean(listing?.jobs.some(j => ['queued', 'running'].includes(j.status)) || listing?.items.some(i => ['queued', 'running'].includes(i.run.status)))
  useEffect(() => { if (!busy) return; const timer = window.setInterval(() => void reload(), 3000); return () => window.clearInterval(timer) }, [busy, reload])
  if (!target) return <>{children}</>
  return <Context.Provider value={{target, listing, reload, beforeEdit, states, readOnly, error}}>{children}{readOnly&&error&&<Alert severity="warning">谱数据暂不可读取：{error}</Alert>}</Context.Provider>
}

export function SpectrumControls() {
  const ctx = useContext(Context), [busy, setBusy] = useState(false), [error, setError] = useState('')
  if (!ctx) return null
  const start = async () => {
    setBusy(true); setError('')
    try {
      if (ctx.beforeEdit && !(await ctx.beforeEdit())) return
      const current = await api.get<Listing>(`${base}?${query(ctx.target)}`)
      await api.post(`${base}/extract`, {...ctx.target, expected_version: current.version}); await ctx.reload()
    } catch(e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <Box sx={{mt:2, pointerEvents:'auto', '& .MuiButton-root': {display:'inline-flex !important'}}}>
    <Typography variant="subtitle1">动力学性质 · 谱提取与质量</Typography>
    {(ctx.error || error) && <Alert severity="warning">{error || ctx.error}</Alert>}
    {!ctx.readOnly && ctx.listing?.can_edit && <Button disabled={busy} onClick={() => void start()}>自动发现并提取谱图</Button>}
    <Button onClick={() => void ctx.reload()}>刷新谱状态</Button>
    {ctx.listing?.jobs.map(j => <Typography key={j.id} variant="body2">谱任务：{names[j.status] || j.status} {j.error_message || ''}{j.detail?.issues?.map((i:any) => i.reason).join('；')}</Typography>)}
    {ctx.listing?.items.filter(i=>!i.state_key).map(i => <SpectrumCard key={i.id} item={i} />)}
  </Box>
}

export function SpectrumStateSection({stateKey}: {stateKey:string}) {
  const ctx = useContext(Context)
  if (!ctx?.listing) return null
  const items = ctx.listing.items.filter(i=>i.state_key===stateKey)
  if (!items.length) return null
  return <Box sx={{mt:2, pointerEvents:'auto', '& .MuiButton-root': {display:'inline-flex !important'}}}><Typography variant="subtitle1">动力学性质 · 谱数据与提取质量</Typography>{items.map(i=><SpectrumCard key={i.id} item={i}/>)}</Box>
}

export function SpectrumQuality({quality:q}: {quality:any}) {
  const rows: Array<[string,string]> = []
  for (const [id, m] of Object.entries<any>(q.curves || {})) {
    rows.push([`${id} · 原图观测覆盖`, `${num(m.observed_fraction*100,1)}% · 缺失 ${num(m.missing_fraction*100,1)}%`],
      [`${id} · 重建与缺口`, `重建 ${num(m.reconstructed_fraction*100,1)}% · 暗色补读 ${m.chromatic_recovered_points} · 最大未观测间隔 ${m.largest_unobserved_gap_samples} 点`],
      [`${id} · 刻度残差`, `频率 ${num(m.frequency_tick_residual,5)} · 幅值 ${num(m.amplitude_tick_residual,5)}`],
      [`${id} · 抵框范围`, m.clipped_frequencies_thz?.length ? `${num(Math.min(...m.clipped_frequencies_thz))}–${num(Math.max(...m.clipped_frequencies_thz))} THz` : '未检测到抵框像素'])
    if(m.frequency_interval_thz)rows.push([`${id} · 提取频域`,m.frequency_interval_thz.map((f:number)=>num(f,4)).join('–')+' THz'])
    if(m.omitted_low_frequency_interval_thz)rows.push([`${id} · 未覆盖低频`,m.omitted_low_frequency_interval_thz.map((f:number)=>num(f,4)).join('–')+' THz；不冒充完整积分'])
    if(m.missing_frequency_intervals_thz?.length)rows.push([`${id} · 未知缺口`,m.missing_frequency_intervals_thz.map((r:number[])=>r.map(f=>num(f,3)).join('–')).join('；')+' THz'])
  }
  const variants:Record<string,string>={raw:'原始重建', zero_baseline:'零基线候选', joint:'联合候选'}
  for (const [variant, values] of Object.entries<any>(q.integrals || {})) {
    rows.push([`${variants[variant]} · λ / ωlog`, values.reason || `${num(values.lambda_integral)} / ${num(values.omega_log_k,1)} K`])
    for (const [name, c] of Object.entries<any>(q.comparisons?.[variant] || {})) {
      rows.push([`${variants[variant]} · ${name==='lambda'?'λ':'ωlog'} 对论文偏差`, c.status==='available' ? `正文 ${num(c.reference)} · 差 ${num(c.signed_difference)} · 绝对差 ${num(c.absolute_difference)} · ${c.relative_difference_pct==null?'参考为零，不计算百分比':num(c.relative_difference_pct,1)+'%'}` : c.reason])
      if(c.source) rows.push(['论文参考来源', `${c.source.source_name||c.source.file_id||''} · 第 ${c.source.page_start||c.source.page||'未知'} 页 · ${c.source.quote||''}`])
    }
  }
  if(q.cumulative_endpoint)rows.push(['累计 λ 终值',num(q.cumulative_endpoint.value)])
  if(q.cumulative_moment)rows.push(['累计谱独立 ωlog',q.cumulative_moment.reason || `${num(q.cumulative_moment.omega_log_k,1)} K · 覆盖 ${q.cumulative_moment.frequency_interval_thz?.map((f:number)=>num(f)).join('–')} THz`])
  const j=q.joint_validation
  if(j)rows.push(['累计谱留出验证',`${j.held_out_nodes} / ${j.observed_nodes} 点 · RMSE ${num(j.held_out_rmse_px,2)} · 最大 ${num(j.held_out_max_abs_px,2)} 像素`])
  if(q.dos_normalization)rows.push(['DOS 模式数归一化',q.dos_normalization.reason || `目标 ${q.dos_normalization.target_modes} · 积分 ${num(q.dos_normalization.total_mode_integral)} · 共同因子 ${num(q.dos_normalization.scale_factor,6)}`])
  for(const [species,m] of Object.entries<any>(q.projection_mode_check||{}))rows.push([`${species} 投影模式数`, `目标 ${m.expected} · 面积 ${num(m.measured)} · 偏差 ${num(m.relative_difference_pct,1)}%`])
  return <>
    {q.metric_domain_note&&<Alert severity="info">{q.metric_domain_note}</Alert>}
    <Table size="small" sx={{tableLayout:'fixed', '& td':{overflowWrap:'anywhere'}}}><TableBody>{rows.map(([label,v],i)=><TableRow key={i}><TableCell sx={{width:'40%'}}>{label}</TableCell><TableCell>{v}</TableCell></TableRow>)}</TableBody></Table>
    <Typography variant="caption">与论文值的偏差不等于整条谱真实误差；无参考不显示为零。图像范围不是统计置信区间。</Typography>
    {(q.frequency_bins||[]).map((b:any,i:number)=><Typography key={i} variant="body2">{b.reason || `${b.frequency_thz.map((f:number)=>num(f,1)).join('–')} THz：原候选 ${num(b.raw_candidate_contribution)}；联合 ${num(b.joint_contribution)}；原图范围 ${num(b.observed_envelope.lower)}–${num(b.observed_envelope.upper)} · ${b.raw_compatible?'原候选相容':'原候选超出范围'}`}</Typography>)}
    {(q.low_frequency_sensitivity||[]).map((s:any,i:number)=><Typography key={i} variant="body2">低频下限 {s.cutoff_thz} THz：{s.reason || `λ ${num(s.lambda_integral)} · ωlog ${num(s.omega_log_k,1)} K`}</Typography>)}
    {(q.one_pixel_sensitivity||[]).map((s:any)=><Typography key={s.amplitude_shift_px} variant="body2">幅值 {s.amplitude_shift_px} 像素扰动：λ {num(s.lambda_integral)} · ωlog {num(s.omega_log_k,1)} K</Typography>)}
    {(q.limitations||[]).map((s:string)=><Typography key={s} variant="caption" display="block">{s}</Typography>)}
  </>
}

export function SpectrumCollectionWorkspace({collectionId, curveId}: {collectionId:string; curveId?:string}) {
  const ctx=useContext(Context)
  const item=ctx?.listing?.items.find(item=>item.id===collectionId)
  return item ? <SpectrumCard key={item.id} item={item} initialCurveId={curveId}/> : ctx?.error ? <Alert severity="error">{ctx.error}</Alert> : <Typography>正在读取谱校对数据…</Typography>
}

function SpectrumCard({item, initialCurveId}: {item:Item; initialCurveId?:string}) {
  const ctx=useContext(Context)!, curves=item.result.curves||[]
  const [selected,setSelected]=useState(initialCurveId||curves[0]?.id||''), [variant,setVariant]=useState('raw'), [overlay,setOverlay]=useState(true), [zoom,setZoom]=useState(false), [image,setImage]=useState(''), [error,setError]=useState(''), [editing,setEditing]=useState(false)
  const [status,setStatus]=useState('needs_review'), [intervals,setIntervals]=useState(''), [reason,setReason]=useState('')
  const key=query(ctx.target), c=curves.find(c=>c.id===selected)||curves[0]
  useEffect(()=>{let active=true,url=''; void api.download(`${base}/${item.id}/image?${key}`).then(b=>{url=URL.createObjectURL(b);if(active)setImage(url)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false;if(url)URL.revokeObjectURL(url)}},[item.id,key])
  useEffect(()=>{const decision=item.review[c?.id]||{};setStatus(decision.status||'needs_review');setReason(decision.reason||'');setIntervals((decision.frequency_intervals_thz||[]).map((p:number[])=>p.join(',')).join(';'))},[item.review,c?.id])
  const candidate=c?.kind==='alpha2f'?(variant==='joint'?item.result.candidates?.joint:variant==='zero_baseline'?item.result.candidates?.zero_baseline:null):null
  const values=new Map<number,number>((candidate?.frequency_thz||[]).map((f:number,i:number)=>[f,(candidate.alpha2f||candidate.amplitude)[i]]))
  const normalization=item.result.candidates?.dos_normalization
  const normalizedComponent=normalization?.components?.[c?.projection||c?.id]
  const normalizedValues=new Map<number,number>((normalization?.frequency_thz||[]).map((f:number,i:number)=>[f,normalizedComponent?.[i]]))
  const points=(c?.points||[]).map(p=>({...p,value:(variant==='normalized'?normalizedValues:values).get(p.frequency_thz)??p.reconstructed_amplitude}))
  const fmax=Math.max(...points.map(p=>p.frequency_thz),1),amax=Math.max(...points.map(p=>p.value??0),.001)
  let line='',sourceLine='',open=false,sourceOpen=false
  for(const p of points){if(p.value==null){open=false;sourceOpen=false;continue}line+=`${open?'L':'M'}${40+p.frequency_thz/fmax*400},${200-p.value/amax*170} `;open=true
    const sourceValue=variant==='normalized'?p.reconstructed_amplitude:p.value
    const amp=((sourceValue??0)-c.axis_calibration.amplitude.intercept)/c.axis_calibration.amplitude.slope
    sourceLine+=`${sourceOpen?'L':'M'}${c.frequency_direction==='y'?amp:p.frequency_pixel},${c.frequency_direction==='y'?p.frequency_pixel:amp} `;sourceOpen=true}
  const download=async(format:string)=>{try{const blob=await api.download(`${base}/${item.id}/export?${key}&format=${format}`);const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`spectrum-${item.id}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){setError((e as Error).message)}}
  const review=async()=>{try{if(ctx.beforeEdit&&!(await ctx.beforeEdit()))return;const current=await api.get<Listing>(`${base}?${key}`);const latest=current.items.find(i=>i.id===item.id);if(!latest)throw Error('谱版本已变化');await api.post(`${base}/${item.id}/review`,{...ctx.target,expected_version:current.version,expected_collection_version:item.version,curve_id:c.id,status,frequency_intervals_thz:intervals.trim()?intervals.split(';').map(s=>s.split(',').map(Number)):[],reason});await ctx.reload()}catch(e){setError((e as Error).message)}}
  return <Accordion defaultExpanded sx={{mt:1,minWidth:0}}><AccordionSummary expandIcon={<ExpandMoreIcon/>}><Typography>{item.state_key||'待分配材料'} · 第 {item.source.pdf_page} 页 · {names[item.run.status]||item.run.status}</Typography></AccordionSummary><AccordionDetails sx={{minWidth:0}}>
    {(error||item.run.error_message) && <Alert severity="warning">{error||item.run.error_message}</Alert>}
    {item.stale&&<Alert severity="warning">来源或材料条件已变化，旧采纳和参考比较已失效，请核对并重提取。</Alert>}
    {!c&&<Alert severity="info">{item.result.quality.limitations?.join('；')||'未得到可提取曲线，请核对原图与标定'}</Alert>}
    <Box sx={{display:'flex',gap:1,flexWrap:'wrap',mb:1}}>
      {c&&<Select size="small" value={c.id} aria-label="选择谱曲线" onChange={e=>{setSelected(e.target.value);setVariant('raw')}}>{curves.map(c=><MenuItem key={c.id} value={c.id}>{c.projection||''} {names[c.kind]} · {names[item.review[c.id]?.status||'needs_review']}</MenuItem>)}</Select>}
      {c?.kind==='alpha2f'&&<Select size="small" value={variant} aria-label="选择谱候选" onChange={e=>setVariant(e.target.value)}><MenuItem value="raw">原始重建</MenuItem>{item.result.candidates?.zero_baseline?.amplitude&&<MenuItem value="zero_baseline">零基线候选</MenuItem>}{item.result.candidates?.joint?.alpha2f&&<MenuItem value="joint">联合候选</MenuItem>}</Select>}
      {c?.kind==='phonon_dos'&&normalizedComponent&&<Select size="small" value={variant} aria-label="选择 DOS 幅值" onChange={e=>setVariant(e.target.value)}><MenuItem value="raw">原图幅值</MenuItem><MenuItem value="normalized">共同尺度归一化候选</MenuItem></Select>}
      <Button onClick={()=>void download('json')}>JSON</Button><Button onClick={()=>void download('csv')}>CSV</Button>
      {!ctx.readOnly&&ctx.listing?.can_edit&&<Button onClick={()=>setEditing(v=>!v)}>修正标定并重提取</Button>}
    </Box>
    <Box sx={{display:'grid',gridTemplateColumns:{xs:'minmax(0,1fr)',md:'minmax(0,1fr) minmax(0,1fr)'},gap:2}}>
      <Box sx={{minWidth:0}}><FormControlLabel control={<Checkbox checked={overlay} onChange={e=>setOverlay(e.target.checked)}/>} label="原图叠加提取曲线"/><FormControlLabel control={<Checkbox checked={zoom} onChange={e=>setZoom(e.target.checked)}/>} label="原始像素尺寸"/>
        <Box sx={{overflow:'auto',maxHeight:480}}><svg role="img" aria-label="谱原图及提取叠加" viewBox={`0 0 ${item.source.size_px.join(' ')}`} style={{width:zoom?item.source.size_px[0]:'100%',display:'block'}}>{image&&<image href={image} width={item.source.size_px[0]} height={item.source.size_px[1]}/>} {overlay&&<path d={sourceLine} stroke="#e89d17" strokeWidth="2" fill="none" strokeDasharray="4 3"/>}</svg></Box>
        <Typography variant="caption">橙线为提取/候选回绘；原图保持不变。{item.source.source_name}</Typography>
      </Box>
      <Box sx={{minWidth:0}}>{c&&<svg role="img" aria-label="提取谱曲线" viewBox="0 0 470 250" width="100%"><path d="M40 25V200H450" fill="none" stroke="#aaa"/><path d={line} fill="none" stroke="#078284"/><text x="45" y="20">{names[c.kind]} / {variant==='normalized'?'modes/THz/primitive cell':c.unit}</text><text x="180" y="235">频率 / THz</text><text x="40" y="218">0</text><text x="400" y="218">{num(fmax,1)}</text></svg>}<SpectrumQuality quality={item.result.quality}/></Box>
    </Box>
    <Accordion><AccordionSummary expandIcon={<ExpandMoreIcon/>}>逐点数据 · 来源与遮挡掩膜</AccordionSummary><AccordionDetails><Box sx={{overflow:'auto',maxHeight:300}}><Table size="small"><TableHead><TableRow>{['THz','原图幅值','重建幅值','当前候选','来源','抵框'].map(s=><TableCell key={s}>{s}</TableCell>)}</TableRow></TableHead><TableBody>{points.map((p,i)=><TableRow key={i}><TableCell>{num(p.frequency_thz,4)}</TableCell><TableCell>{num(p.observed_amplitude,5)}</TableCell><TableCell>{num(p.reconstructed_amplitude,5)}</TableCell><TableCell>{num(p.value,5)}</TableCell><TableCell>{p.detection_mode==='chromatic_recovery'?'暗色像素观测':names[p.status]}</TableCell><TableCell>{c.clipped_frequencies_thz.includes(p.frequency_thz)?'是，峰顶不唯一':''}</TableCell></TableRow>)}</TableBody></Table></Box></AccordionDetails></Accordion>
    {editing&&<CalibrationEditor item={item} onClose={()=>setEditing(false)}/>}
    {!ctx.readOnly&&ctx.listing?.can_review&&c&&<Box sx={{mt:2,display:'flex',gap:1,flexWrap:'wrap'}}><Select size="small" value={status} aria-label="谱采纳状态" onChange={e=>setStatus(e.target.value)}>{['needs_review','accepted','accepted_limited','excluded'].map(v=><MenuItem key={v} value={v}>{names[v]}</MenuItem>)}</Select>{status==='accepted_limited'&&<TextField size="small" label="有效频段 / THz" helperText="如 0,20;30,50" value={intervals} onChange={e=>setIntervals(e.target.value)}/>}<TextField size="small" label="采纳范围与理由" value={reason} onChange={e=>setReason(e.target.value)}/><Button onClick={()=>void review()}>保存本条谱审核</Button></Box>}
  </AccordionDetails></Accordion>
}

function CalibrationEditor({item,onClose}: {item:Item;onClose:()=>void}) {
  const ctx=useContext(Context)!
  const emptyCurve=()=>({id:newStableKey('curve'),kind:'phonon_dos',projection:null,color:'blue',roi:[0,0,item.source.size_px[0]-1,item.source.size_px[1]-1],frequency_direction:'x',frequency_ticks:[],amplitude_ticks:[],frequency_unit:'THz',frequency_scale:'linear',amplitude_scale:'linear',unit:'pixel',physical_definition_confirmed:false,exclude:[],zero_boundaries_thz:[null,null],zero_reference_band_thz:null})
  const [value,setValue]=useState<any>(()=>structuredClone(item.result.calibration||{panel_id:'manual-correction',state_key:item.state_key,caption:'',projection_complete:false,projection_scale_confirmed:false,curves:[emptyCurve()]})),[error,setError]=useState('')
  const edit=(i:number,k:string,v:any)=>setValue((old:any)=>({...old,curves:old.curves.map((c:any,n:number)=>n===i?{...c,[k]:v}:c)}))
  const save=async()=>{try{if(ctx.beforeEdit&&!(await ctx.beforeEdit()))return;const fresh=await api.get<Listing>(`${base}?${query(ctx.target)}`);const current=fresh.items.find(i=>i.id===item.id);if(!current)throw Error('谱版本已变化');await api.put(`${base}/${item.id}/calibration`,{...ctx.target,expected_version:fresh.version,expected_collection_version:item.version,calibration:value});await ctx.reload();onClose()}catch(e){setError((e as Error).message)}}
  return <Box sx={{mt:2}}><Typography>修正原图标定；重新提取会撤回旧采纳</Typography>{error&&<Alert severity="error">{error}</Alert>}
    <Select value={value.state_key||''} aria-label="谱材料归属" onChange={e=>setValue({...value,state_key:e.target.value||null})}><MenuItem value="">待分配</MenuItem>{ctx.states.map((s,i)=><MenuItem key={i} value={s.state_key||`state-${i+1}`}>{s.material_name||s.material||s.state_key}</MenuItem>)}</Select>
    {value.curves.map((c:any,i:number)=><Box key={c.id} sx={{mt:2,display:'grid',gridTemplateColumns:{xs:'1fr',sm:'1fr 1fr'},gap:1}}><Typography sx={{gridColumn:'1/-1'}}>{c.id}</Typography>
      <Select size="small" value={c.kind} aria-label={`${c.id} 谱类型`} onChange={e=>edit(i,'kind',e.target.value)}>{['phonon_dos','alpha2f','cumulative_lambda'].map(v=><MenuItem key={v} value={v}>{names[v]}</MenuItem>)}</Select>
      <TextField size="small" label="图框像素 x0,y0,x1,y1" defaultValue={c.roi.join(',')} onBlur={e=>edit(i,'roi',e.target.value.split(',').map(Number))}/>
      <Select size="small" value={c.color} aria-label={`${c.id} 曲线颜色`} onChange={e=>edit(i,'color',e.target.value)}>{['red','blue','green','magenta','olive'].map((v,n)=><MenuItem key={v} value={v}>{['红','蓝','绿','粉紫','橄榄黄'][n]}</MenuItem>)}</Select>
      <Select size="small" value={c.frequency_direction} aria-label={`${c.id} 频率方向`} onChange={e=>edit(i,'frequency_direction',e.target.value)}><MenuItem value="x">频率横轴</MenuItem><MenuItem value="y">频率纵轴</MenuItem></Select>
      <Select size="small" value={c.frequency_unit} aria-label={`${c.id} 频率单位`} onChange={e=>edit(i,'frequency_unit',e.target.value)}>{['THz','cm-1','meV'].map(v=><MenuItem key={v} value={v}>{v}</MenuItem>)}</Select>
      {['frequency_ticks','amplitude_ticks','exclude'].map(k=><TextField key={k} size="small" label={{frequency_ticks:'频率刻度：像素,值',amplitude_ticks:'幅值刻度：像素,值',exclude:'图例排除框：x0,y0,x1,y1'}[k]} helperText="多项用分号分隔" defaultValue={c[k].map((p:number[])=>p.join(',')).join(';')} onBlur={e=>edit(i,k,e.target.value.trim()?e.target.value.split(';').map(s=>s.split(',').map(Number)):[])}/>)}
      <TextField size="small" label="零参考频段 / THz" defaultValue={c.zero_reference_band_thz?.join(',')||''} onBlur={e=>edit(i,'zero_reference_band_thz',e.target.value.trim()?e.target.value.split(',').map(Number):null)}/>
      <TextField size="small" label="端点零值假设 / THz" defaultValue={c.zero_boundaries_thz?.map((v:number|null)=>v??'').join(',')||','} onBlur={e=>edit(i,'zero_boundaries_thz',e.target.value.split(',').map(v=>v.trim()?Number(v):null))}/>
      <TextField size="small" label="元素投影" value={c.projection||''} onChange={e=>edit(i,'projection',e.target.value||null)}/>
      <Select size="small" value={c.unit} aria-label={`${c.id} 幅值单位`} onChange={e=>edit(i,'unit',e.target.value)}>{['pixel','dimensionless','modes_per_source_frequency','unknown'].map((v,n)=><MenuItem key={v} value={v}>{['相对像素幅值','无量纲规范','模式数/原频率单位','未知'][n]}</MenuItem>)}</Select>
      <FormControlLabel control={<Checkbox checked={c.physical_definition_confirmed} onChange={e=>edit(i,'physical_definition_confirmed',e.target.checked)}/>} label="普通频率与谱定义已核对"/>
      {c.kind==='phonon_dos'&&<FormControlLabel control={<Checkbox checked={Boolean(c.frequency_range_confirmed)} onChange={e=>edit(i,'frequency_range_confirmed',e.target.checked)}/>} label="已核对原图覆盖完整振动频段"/>}
    </Box>)}
    <FormControlLabel control={<Checkbox checked={value.projection_complete} onChange={e=>setValue({...value,projection_complete:e.target.checked})}/>} label="元素投影完整"/><FormControlLabel control={<Checkbox checked={value.projection_scale_confirmed} onChange={e=>setValue({...value,projection_scale_confirmed:e.target.checked})}/>} label="各分波共享幅值尺度"/>
    <Button onClick={()=>setValue({...value,curves:[...value.curves,emptyCurve()]})}>增加曲线标定</Button>
    <Button onClick={()=>void save()}>保存标定并重提取</Button><Button onClick={onClose}>取消</Button>
  </Box>
}
