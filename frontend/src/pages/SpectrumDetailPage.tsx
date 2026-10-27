import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, Dialog, MenuItem, TextField, Typography } from '@mui/material'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { DetailSection, SpectrumResult, SpectrumMetrics } from '../components/SpectrumDetailView'
import SpectrumManualEditor from '../components/spectrumEditor/SpectrumManualEditor'
import type { Document as EditorDocument } from '../components/spectrumEditor/engine'
import type { PropertySpectrumListing } from '../lib/propertySpectra'
import { materialStateSummary } from '../lib/materialStateSummary'
import { api } from '../lib/api'
import { hasSpectrumData, SPECTRUM_API, safeSpectrumReturn, spectrumNames, spectrumQuery, spectrumGroups, spectrumDetailPath, usePropertySpectra, type PropertySpectrumItem, type PropertySpectrumTarget } from '../lib/propertySpectra'

type HistoryRun = { id: string; status: string; current: boolean; created_at: string; state_key?: string; caption?: string }
export default function SpectrumDetailPage() {
  const { collectionId } = useParams(), [params] = useSearchParams(), navigate = useNavigate()
  const targetKind = params.get('target'), targetId = params.get('target_id')
  const target = ['upload', 'paper', 'revision'].includes(targetKind || '') && targetId ? { target: targetKind, target_id: targetId } as PropertySpectrumTarget : undefined
  const { listing, loading, error, reload, replaceListing } = usePropertySpectra(target)
  const [editorInput,setEditorInput]=useState<{documents:EditorDocument[];base_run_id:string;collection_version:number;version:string;initialPointId?:string;focusPointId?:string}|null>(null)
  const savedEditorResult=useRef<{listing:PropertySpectrumListing;item:PropertySpectrumItem;curveId:string;context:string}|null>(null)
  const [imageOpacity,setImageOpacity]=useState(100)
  const [openingEditor,setOpeningEditor]=useState(false)
  const [recalculating,setRecalculating]=useState(false)
  const calculationLock=useRef(false)
  const calculationTarget=useRef('')
  calculationTarget.current=(collectionId||'')+params.toString()
  const [materialStates, setMaterialStates] = useState<any[]>([]), [statesLoaded, setStatesLoaded] = useState(false)
  const [material, setMaterial] = useState(''), [materialError, setMaterialError] = useState('')
  const [assignedState, setAssignedState] = useState(''), [assigning, setAssigning] = useState(false)
  const [imageRun,setImageRun]=useState('')
  const [revalidationInput,setRevalidationInput]=useState<{version:string;collectionVersion:number;runId:string;stateKey:string;material:string;caption:string}|null>(null)
  const [revalidating,setRevalidating]=useState(false), revalidationLock=useRef(false)
  const [resumeEditing,setResumeEditing]=useState<string|null>(null)
  const [image, setImage] = useState(''), [imageError, setImageError] = useState(''), [imageRetry, setImageRetry] = useState(0)
  const [actionError, setActionError] = useState(''), [historyItem, setHistoryItem] = useState<PropertySpectrumItem | null>(null)
  const [historyRuns, setHistoryRuns] = useState<Array<{ item: PropertySpectrumItem; run: HistoryRun }>>([])
  const [historyOpen, setHistoryOpen] = useState(false), [historyLoading, setHistoryLoading] = useState(false)
  const historyRequest = useRef(0)
  const item = listing?.items.find(value => value.id === collectionId)
  const curveId = params.get('curve'), routeCurve = item?.result.curves.find(value => value.id === curveId)
  const query = target ? spectrumQuery(target) : ''
  const mismatch = !target ? '谱详情地址缺少有效目标。'
    : listing && (!item || (curveId ? !routeCurve : Boolean(item.result.curves.length)) || (item.state_key || 'unassigned') !== params.get('state_key'))
      ? '该目标或材料状态下的谱曲线不可访问，可能已删除或没有查看权限。'
      : ''
  const validItem = !mismatch ? item : undefined
  const selected = historyItem || validItem
  const kind = routeCurve?.kind === 'phonon_dos' || !routeCurve && params.get('kind') === 'phonon_dos' ? 'phonon_dos' : 'alpha2f'
  const curves = (selected?.result.curves || []).filter(value => value.kind === kind)
  const fallback = kind === 'alpha2f' && !curves.length ? selected?.result.curves.filter(value => value.kind === 'cumulative_lambda') || [] : curves
  const primary = fallback
  const group = validItem?.state_key ? spectrumGroups(listing?.items || [], validItem.state_key).find(value => value.kind === kind) : undefined
  const historical = Boolean(historyItem || group && group.item.id !== validItem?.id)
  const versionChanged = Boolean(validItem && (String(validItem.version) !== params.get('collection_version') || (params.get('run') && validItem.run.id !== params.get('run'))))
  const latestPath = versionChanged && target && validItem
    ? spectrumDetailPath(target, validItem, safeSpectrumReturn(params.get('return')), routeCurve, kind) : ''
  useEffect(() => {
    // 普通查看跟随当前可访问结果；编辑快照和主动历史查看仍独立保护。
    if (!latestPath || loading || editorInput || openingEditor || historyOpen || historyItem || recalculating || revalidating || revalidationInput || assigning) return
    navigate(latestPath, { replace: true })
  }, [latestPath, loading, editorInput, openingEditor, historyOpen, historyItem, recalculating, revalidating, revalidationInput, assigning, navigate])
  const attempt = Boolean(validItem && !hasSpectrumData(validItem))
  const unassigned = Boolean(validItem && (!validItem.state_key || statesLoaded && !material))
  const calibration = validItem?.result.calibration
  const canAssign = listing?.can_edit && !historical && statesLoaded && materialStates.length > 0 && Array.isArray(calibration?.curves) && calibration.curves.length > 0
  const canEdit=Boolean(listing?.can_edit && validItem && !historical && !validItem.stale && !unassigned && !attempt && statesLoaded && image && imageRun===validItem.run.id && !imageError && !loading && primary.some(c=>c.kind===kind))
  const canCalculate=Boolean(listing?.can_edit && validItem && !historical && !validItem.stale && !unassigned && !attempt && statesLoaded && !loading && primary.some(c=>c.kind===kind))
  const staleReasons=validItem?.stale_reasons||[]
  const canRevalidate=Boolean(listing?.can_edit && validItem?.stale && !historical && !unassigned && !attempt && statesLoaded && staleReasons.length===1 && staleReasons[0]==='state_changed')
  const disabledReason=!listing?.can_edit?'当前没有谱数据编辑权限。'
    : historical?'正在查看历史谱，请打开当前版本后编辑。'
    : staleReasons.includes('source_changed')?'来源文件已变化，请返回原模块核对来源后重新提取。'
    : staleReasons.includes('state_missing')||unassigned?'材料归属已不存在或尚未确认，请先核对材料归属。'
    : validItem?.stale?canRevalidate?'材料条件待重新核对，请点击“核对材料条件并继续编辑”。':'材料条件或来源已变化，请先核对材料与来源。'
    : materialError||!statesLoaded?materialError||'正在读取材料条件…'
    : attempt?'当前尚无可编辑的数值曲线。'
    : loading?'正在读取谱数据…':''
  const editDisabledReason=disabledReason || (imageError?imageError:!image||imageRun!==validItem?.run.id?'正在读取本版本原图…':recalculating?'正在计算，请稍候。':openingEditor?'正在打开编辑器…':'')
  const revalidateMaterial=async()=>{
    if(!canRevalidate||!target||!validItem||!revalidationInput||revalidationLock.current)return
    revalidationLock.current=true;setRevalidating(true);setActionError('')
    const input=revalidationInput,context=calculationTarget.current
    try{
      const updated=await api.post<PropertySpectrumListing>(SPECTRUM_API+'/'+encodeURIComponent(validItem.id)+'/revalidate',{
        ...target,expected_version:input.version,expected_collection_version:input.collectionVersion,base_run_id:input.runId,
        state_key:input.stateKey,kind,confirmed:true})
      if(calculationTarget.current!==context)return
      const fresh=updated.items.find(i=>i.id===validItem.id)
      if(!fresh)throw new Error('核对响应缺少新版本，请刷新后确认。')
      setRevalidationInput(null);replaceListing(updated)
      const curve=fresh.result.curves.find(c=>c.id===curveId)||fresh.result.curves.find(c=>c.kind===kind)
      setResumeEditing(curve?.id||null)
      navigate(spectrumDetailPath(target,fresh,safeSpectrumReturn(params.get('return')),curve),{replace:true})
    }catch(error:any){if(calculationTarget.current===context)setActionError(error.message||'材料核对失败，已保存曲线保持不变。')}
    finally{revalidationLock.current=false;setRevalidating(false)}
  }
  const recalculate=async()=>{
    if(!canCalculate || !target || !validItem || !listing || calculationLock.current)return
    calculationLock.current=true;setRecalculating(true);setActionError('')
    const context=calculationTarget.current
    try {
      const updated=await api.post<PropertySpectrumListing>(SPECTRUM_API+'/'+encodeURIComponent(validItem.id)+'/recalculate',{
        ...target,expected_version:listing.version,expected_collection_version:validItem.version,base_run_id:validItem.run.id,kind})
      if(calculationTarget.current!==context)return
      const fresh=updated.items.find(i=>i.id===validItem.id)
      if(!fresh)throw new Error('计算响应缺少新版本，请刷新核对。')
      replaceListing(updated)
      navigate(spectrumDetailPath(target,fresh,safeSpectrumReturn(params.get('return')),fresh.result.curves.find(c=>c.id===curveId)||fresh.result.curves.find(c=>c.kind===kind)),{replace:true})
    }catch(error:any){if(calculationTarget.current===context)setActionError(error.message||'重新计算失败，已保存数据保持不变。')}
    finally{calculationLock.current=false;setRecalculating(false)}
  }
  const openEditor=async(selectedCurve?:string,pointId?:string)=>{
    if(!canEdit || !validItem || editorInput || openingEditor || calculationLock.current)return
    savedEditorResult.current=null
    setOpeningEditor(true);setActionError('')
    try {
      const input=await api.get<{documents:EditorDocument[];base_run_id:string;collection_version:number;version:string}>(SPECTRUM_API+'/'+encodeURIComponent(validItem.id)+'/manual?'+query+'&kind='+kind+'&collection_version='+validItem.version+'&run_id='+encodeURIComponent(validItem.run.id||''))
      const documents=input.documents.map(doc=>({...doc,source:{...doc.source,image}}))
      documents.sort((a,b)=>Number(b.curves[0].id===selectedCurve)-Number(a.curves[0].id===selectedCurve))
      if(pointId && (documents[0]?.curves[0]?.id!==selectedCurve || !documents[0].curves[0].points.some(p=>p.id===pointId)))
        throw new Error('该问题点已变化或缺少有效原图位置，请重新计算后定位。')
      setEditorInput({...input,documents,initialPointId:pointId,focusPointId:pointId})
    }catch(error:any){setActionError(error.message||'无法打开人工编辑器')}
    finally{setOpeningEditor(false)}
  }
  const saveEditor=async(document:EditorDocument)=>{
    if(!target || !validItem || !editorInput)throw new Error('编辑目标已变化，请重新打开。')
    const context=calculationTarget.current
    const updated=await api.post<PropertySpectrumListing>(SPECTRUM_API+'/'+encodeURIComponent(validItem.id)+'/manual',{
      ...target,expected_version:editorInput.version,expected_collection_version:editorInput.collection_version,base_run_id:editorInput.base_run_id,document})
    if(calculationTarget.current!==context)throw new Error('保存已提交，但页面目标发生变化，请重新打开原谱核对。')
    const fresh=updated.items.find(i=>i.id===validItem.id)
    if(!fresh)throw new Error('保存响应缺少新版本，请刷新详情核对；编辑内容仍保留。')
    const curveId=document.curves[0].id,stored=fresh.result.manual_documents?.[curveId]
    if(!stored || !fresh.run.id)throw new Error('保存响应缺少规范编辑文档，请重新打开核对；当前编辑内容仍保留。')
    // 其他分波未被此次POST修改，保留GET/manual已校验、已重绑定身份的文档。
    const documents=editorInput.documents.map(doc=>doc.curves[0].id===curveId?{...stored,source:{...stored.source,image:doc.source.image}}:doc)
    setEditorInput({documents,version:updated.version,collection_version:fresh.version,base_run_id:fresh.run.id})
    savedEditorResult.current={listing:updated,item:fresh,curveId,context}
    return documents
  }
  const closeEditor=()=>{
    const saved=savedEditorResult.current;savedEditorResult.current=null
    setEditorInput(null)
    // 连续编辑时保留原图blob，真正退出时才更新背后的只读详情和URL。
    if(saved && target && saved.context===calculationTarget.current){
      replaceListing(saved.listing)
      navigate(spectrumDetailPath(target,saved.item,safeSpectrumReturn(params.get('return')),saved.item.result.curves.find(c=>c.id===saved.curveId)||saved.item.result.curves[0]),{replace:true})
    }
  }
  useEffect(() => { historyRequest.current++; setHistoryItem(null); setHistoryRuns([]); setHistoryOpen(false); setHistoryLoading(false); return () => { historyRequest.current++ } }, [collectionId, query])
  useEffect(() => {
    let active = true, url = ''
    setImage(''); setImageRun(''); setImageError('')
    if (selected) void api.download(SPECTRUM_API + '/' + encodeURIComponent(selected.id) + '/image?' + query).then(blob => {
      url = URL.createObjectURL(blob)
      if (active) {setImage(url);setImageRun(selected.run.id||'')} else URL.revokeObjectURL(url)
    }).catch(error => { if (active) setImageError('原图暂不可读取：' + error.message) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [selected?.id, selected?.version, query, imageRetry])
  useEffect(() => {
    const controller = new AbortController()
    setMaterial(''); setMaterialError(''); setMaterialStates([]); setStatesLoaded(false)
    if (!validItem || !target) return () => controller.abort()
    const revisionPaper = safeSpectrumReturn(params.get('return')).match(/^\/papers\/(\d+)\/revise(?:[?#]|$)/)?.[1]
    const endpoint = target.target === 'upload' ? '/api/rag/upload-tasks/' + encodeURIComponent(target.target_id) + '/draft'
      : target.target === 'paper' ? '/api/papers/' + encodeURIComponent(target.target_id)
        : revisionPaper ? '/api/rag/papers/' + revisionPaper + '/revision-draft' : ''
    if (!endpoint) { setMaterialError('材料条件尚未定位，请返回原模块查看。'); return () => controller.abort() }
    void api.get<any>(endpoint, { signal: controller.signal }).then(response => {
      if (controller.signal.aborted) return
      if (target.target === 'revision' && response.revision_id !== target.target_id) throw new Error('返修草稿版本不匹配')
      const states = (response.data || response).material_states || []
      setMaterialStates(states); setStatesLoaded(true)
      const state = states.find((value: any, index: number) => (value.state_key || 'state-' + (index + 1)) === validItem.state_key)
      if (state) setMaterial(materialStateSummary(state))
      else if (validItem.state_key) setMaterialError('原材料状态已不存在，请重新核对归属。')
    }).catch(error => { if (!controller.signal.aborted) setMaterialError('当前材料条件暂不可读取：' + error.message) })
    return () => controller.abort()
  }, [validItem?.id, validItem?.state_key, query, params.get('return')])
  useEffect(()=>{
    if(resumeEditing && canEdit && !revalidating && !editorInput){
      setResumeEditing(null);void openEditor(resumeEditing)
    }
  },[resumeEditing,canEdit,revalidating,editorInput,imageRun])
  useEffect(()=>{setRevalidationInput(null);setResumeEditing(null)},[collectionId,query])
  const confirmAssignment = async () => {
    if (!target || !validItem || !assignedState || !canAssign || assigning) return
    setAssigning(true); setActionError('')
    try {
      const fresh = await api.get<any>(SPECTRUM_API + '?' + query)
      const current = fresh.items.find((value: any) => value.id === validItem.id)
      if (fresh.version !== listing?.version || !current || current.version !== validItem.version || current.run.id !== validItem.run.id || current.state_key !== validItem.state_key)
        throw new Error('谱版本或归属已变化，请返回原模块刷新后重试。')
      await api.put(SPECTRUM_API + '/' + encodeURIComponent(validItem.id) + '/calibration', {
        ...target, expected_version: fresh.version, expected_collection_version: validItem.version,
        calibration: { ...calibration, state_key: assignedState },
      })
      const returnTo = safeSpectrumReturn(params.get('return')).split('#')[0] + '#material-state-' + encodeURIComponent(assignedState)
      navigate(returnTo, { state: { spectrumAssignment: '已确认材料归属，谱数据与质量将重新计算；请查看提取状态。' } })
    } catch (error: any) { setActionError(error.message || '归属保存失败，当前选择已保留。') }
    finally { setAssigning(false) }
  }
  const download = async (format: 'csv' | 'json') => {
    if (!selected) return
    try {
      const runQuery = historyItem ? '&run_id=' + encodeURIComponent(historyItem.run.id || '') : ''
      const blob = await api.download(SPECTRUM_API + '/' + encodeURIComponent(selected.id) + '/export?' + query + '&format=' + format + runQuery)
      const url = URL.createObjectURL(blob), anchor = document.createElement('a')
      anchor.href = url; anchor.download = 'spectrum-' + selected.id + '.' + format; anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error: any) { setActionError('导出失败：' + error.message) }
  }
  const openHistory = async () => {
    if (!validItem || historyLoading) return
    const request = ++historyRequest.current
    setHistoryOpen(true); setHistoryLoading(true); setActionError('')
    const collections = (listing?.items || []).filter(value => value.state_key === validItem.state_key && (value.state_key || value.id === validItem.id)
      && value.result.curves.some(curve => curve.kind === kind || kind === 'alpha2f' && curve.kind === 'cumulative_lambda'))
    try {
      const results = await Promise.all(collections.map(async value => {
        const result = await api.get<{ items: HistoryRun[] }>(SPECTRUM_API + '/' + encodeURIComponent(value.id) + '/history?' + query)
        return result.items.map(run => ({ item: value, run }))
      }))
      if (request === historyRequest.current) setHistoryRuns(results.flat().sort((a, b) => b.run.created_at.localeCompare(a.run.created_at)))
    } catch (error: any) { if (request === historyRequest.current) setActionError('历史记录读取失败：' + error.message) }
    finally { if (request === historyRequest.current) setHistoryLoading(false) }
  }
  const readHistory = async (value: { item: PropertySpectrumItem; run: HistoryRun }) => {
    const request = ++historyRequest.current
    setActionError('')
    try {
      const result = await api.get<PropertySpectrumItem>(SPECTRUM_API + '/' + encodeURIComponent(value.item.id) + '/runs/' + encodeURIComponent(value.run.id) + '?' + query)
      if (request === historyRequest.current) setHistoryItem(result)
    } catch (error: any) { if (request === historyRequest.current) setActionError('历史结果读取失败：' + error.message) }
  }
  const title = routeCurve ? spectrumNames[kind] + '解析详情' : attempt ? '谱提取记录' : '谱图候选 · 核对归属'
  return <Box sx={{ minWidth: 0, pb: 4 }}>
    <Button component="a" href={safeSpectrumReturn(params.get('return'))}>返回原模块</Button>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', my: 2 }}>
      <Box><Typography variant="overline" color="primary">谱数据 · 独立详情页</Typography><Typography variant="h5" fontWeight={700}>{title}</Typography></Box>
      {selected && <Box><Button onClick={() => void download('json')}>导出 JSON</Button><Button onClick={() => void download('csv')}>导出 CSV</Button></Box>}
    </Box>
    {loading && <Typography role="status">正在读取谱结果…</Typography>}
    {(error || mismatch) && <Alert severity="error">{mismatch || '谱数据暂不可读取：' + error}<Button onClick={reload}>重新读取</Button></Alert>}
    {selected && <>
      <DetailSection title="01 · 材料与来源">
        <Typography fontWeight={700}>{historical ? selected.recorded_caption || '历史提取 · 材料条件以该次标定为准' : attempt ? '尚未生成可分配的谱数据' : unassigned ? '归属待确认' : material || '正在读取材料状态…'}</Typography>
        <Typography variant="body2" color="text.secondary">{selected.source.source_name || '来源未命名'} · 第 {selected.source.pdf_page ?? '未知'} 页</Typography>
        <Typography variant="caption" color="text.secondary" display="block">当前材料信息来自已保存记录，原标签页未保存的输入不会在此覆盖谱归属。</Typography>
        <Box sx={{ display: 'flex', gap: 1, my: 1, flexWrap: 'wrap' }}><Chip size="small" label={historical ? '历史提取' : '当前展示版本'} /><Chip size="small" label={spectrumNames[selected.run.status] || selected.run.status} /></Box>
        {selected.result.calibration?.caption && <Typography variant="body2">{selected.result.calibration.caption}</Typography>}
        {materialError && <Alert severity="info">{materialError}</Alert>}
        {(selected.stale || historical) && <Alert severity="warning">材料条件或版本已变化，旧采纳与参考比较不可当作当前结论。</Alert>}
        {(listing?.can_edit || listing?.can_review) && <Button onClick={() => void openHistory()} disabled={historyLoading}>{historyLoading ? '正在读取历史…' : '查看提取历史'}</Button>}
        {historyOpen && <Box sx={{ maxHeight: 240, overflow: 'auto' }}><Button onClick={() => { historyRequest.current++; setHistoryItem(null); setHistoryOpen(false); setHistoryLoading(false) }}>返回打开时的版本</Button>
          {group && target && <Button component="a" href={spectrumDetailPath(target, group.item, safeSpectrumReturn(params.get('return')), group.curves.find(c => c.kind === kind) || group.curves[0])}>打开当前版本</Button>}
          {historyRuns.map(value => <Box key={value.run.id}><Button size="small" onClick={() => void readHistory(value)}>{value.run.created_at || '时间未记录'} · {value.run.caption || value.item.source.source_name} · {spectrumNames[value.run.status] || value.run.status}</Button></Box>)}
        </Box>}
      </DetailSection>
      {canRevalidate && <Alert severity="warning" sx={{mb:2}} data-testid="material-revalidation-entry">
        当前材料条件与这条谱保存时的校验记录不一致。请对照原图核对后继续编辑。
        <Button disabled={revalidating} onClick={()=>{setActionError('');if(listing&&validItem)setRevalidationInput({version:listing.version,collectionVersion:validItem.version,runId:validItem.run.id||'',stateKey:validItem.state_key||'',material,caption:validItem.result.calibration?.caption||''})}}>核对材料条件并继续编辑</Button>
      </Alert>}
      {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}
      {selected.run.error_message && <Alert severity="warning" sx={{ mb: 2 }}>{selected.run.error_message}</Alert>}
      {unassigned && !attempt && !historical && <DetailSection title="材料归属待确认">
        {canAssign ? <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}><TextField select size="small" label="选择归属材料状态" value={assignedState} disabled={assigning} onChange={event => setAssignedState(event.target.value)} sx={{ minWidth: 240 }}>
          {materialStates.map((state, index) => <MenuItem key={state.state_key || index} value={state.state_key || 'state-' + (index + 1)}>{materialStateSummary(state)}</MenuItem>)}
        </TextField><Button disabled={!assignedState || assigning} onClick={() => void confirmAssignment()}>确认归属并重新计算</Button></Box> : <Typography>当前为只读或缺少有效标定，不能凭图片猜测材料归属。</Typography>}
      </DetailSection>}
      {imageError && <Alert severity="warning" sx={{ mb: 2 }}>{imageError}<Button onClick={() => setImageRetry(value => value + 1)}>重新读取原图</Button></Alert>}
      {!primary.length && <Alert severity="info" sx={{ mb: 2 }}>尚未得到数值曲线。{(selected.result.failures || selected.result.quality?.limitations || []).map((value: unknown) => typeof value === 'string' ? value : JSON.stringify(value)).join('；')}</Alert>}
      <Box data-testid="spectrum-analysis-grid" sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0,1fr)', lg: primary.length ? 'minmax(0,.85fr) minmax(0,1.15fr)' : 'minmax(0,1fr)' }, gap: 2, alignItems: 'start', mb: 2, '& > .MuiPaper-root': { mb: 0 } }}>
        <SpectrumResult history={historical} key={selected.id + selected.run.id + kind} item={selected} curves={primary} image={image} retryImage={() => setImageRetry(value => value + 1)} onEdit={listing?.can_edit && !historical ? openEditor : undefined} editingDisabled={!canEdit || openingEditor || recalculating} editingDisabledReason={editDisabledReason} imageOpacity={imageOpacity} onOpacityChange={setImageOpacity} />
        {!!primary.length && <SpectrumMetrics item={selected} curves={primary} history={historical} onLocate={canEdit?(curve,point)=>openEditor(curve,point):undefined} onRecalculate={listing?.can_edit?recalculate:undefined} recalculating={recalculating} calculationDisabled={!canCalculate||openingEditor||Boolean(editorInput)} calculationDisabledReason={disabledReason||undefined}/>}
      </Box>
    </>}
    <Dialog open={Boolean(revalidationInput)} onClose={()=>{if(!revalidating)setRevalidationInput(null)}} maxWidth="sm" fullWidth aria-labelledby="revalidate-material-title">
      <Box sx={{p:3}}>
        <Typography id="revalidate-material-title" variant="h6">核对这条谱的材料条件</Typography>
        <Typography sx={{mt:2}} fontWeight={600}>当前已保存材料：{revalidationInput?.material}</Typography>
        <Typography sx={{mt:1}}>原图说明：{revalidationInput?.caption||'原记录没有图注，请对照来源原图核对。'}</Typography>
        <Typography variant="body2" sx={{mt:2}}>请确认这条谱仍属于以上材料条件。确认后保留全部点、连线、坐标标定和人工记录，并打开编辑器；旧积分和采纳状态失效。此次确认不代表幅值刻度已核对或科学采纳。</Typography>
        {actionError && <Alert severity="error" sx={{mt:1}}>{actionError}</Alert>}
        <Box sx={{display:'flex',gap:1,justifyContent:'flex-end',mt:3}}>
          <Button disabled={revalidating} onClick={()=>setRevalidationInput(null)}>取消</Button>
          <Button variant="contained" disabled={revalidating} onClick={revalidateMaterial}>{revalidating?'正在确认…':'确认属于当前材料并继续编辑'}</Button>
        </Box>
      </Box>
    </Dialog>
    <Dialog fullScreen transitionDuration={0} open={Boolean(editorInput)} onClose={()=>{}}>{editorInput && <SpectrumManualEditor documents={editorInput.documents} initialPointId={editorInput.initialPointId} focusPointId={editorInput.focusPointId} imageOpacity={imageOpacity} onOpacityChange={setImageOpacity} kind={kind} onSave={saveEditor} onClose={closeEditor}/>}</Dialog>
  </Box>
}
