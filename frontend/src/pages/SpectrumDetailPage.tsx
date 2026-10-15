import { useEffect, useState } from 'react'
import { Alert, Box, Button, MenuItem, Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Typography, Chip } from '@mui/material'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { SpectrumProvider, SpectrumQuality, SpectrumCollectionWorkspace } from '../components/SpectrumWorkspace'
import { materialStateSummary } from '../lib/materialStateSummary'
import { api } from '../lib/api'
import { SPECTRUM_API, safeSpectrumReturn, spectrumNames, spectrumQuery, usePropertySpectra, type PropertySpectrumCurve, type PropertySpectrumTarget } from '../lib/propertySpectra'

const show = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? Number(value.toPrecision(7)).toString() : '未知'
function SpectrumPlot({ curve, candidate, reconstructionLabel = '原始重建' }: { curve: PropertySpectrumCurve; candidate: Map<number, number>; reconstructionLabel?: string }) {
  const points = curve.points.filter(point => Number.isFinite(point.frequency_thz))
  const xs = points.map(point => point.frequency_thz)
  const ys = points.flatMap(point => [point.observed_amplitude, point.reconstructed_amplitude, candidate.get(point.frequency_thz)]).filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (!xs.length || !ys.length) return <Alert severity="info">当前曲线没有可绘制的有效点</Alert>
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(0, ...ys), maxY = Math.max(...ys)
  const x = (v: number) => 65 + 790 * (v - minX) / (maxX - minX || 1)
  const y = (v: number) => 280 - 245 * (v - minY) / (maxY - minY || 1)
  const line = (get: (p: typeof points[number]) => number | null | undefined) => {
    let path = '', open = false
    for (const p of points) {
      const v = get(p)
      if (v == null || !Number.isFinite(v)) { open = false; continue }
      path += `${open ? 'L' : 'M'}${x(p.frequency_thz)},${y(v)} `; open = true
    }
    return path
  }
  return <Box sx={{ overflowX: 'auto' }}>
    <Box component="svg" viewBox="0 0 900 330" role="img" aria-label="谱曲线：原图观测、原始重建与所选候选" sx={{ width: '100%', minWidth: 280 }}>
      <path d="M65 25V280H855" stroke="#94a3b8" fill="none" />
      <path d={line(p => p.reconstructed_amplitude)} stroke="#8b5cf6" strokeWidth="2" fill="none" />
      <path d={line(p => p.observed_amplitude)} stroke="#2563eb" strokeWidth="2" fill="none" />
      {points.filter(point => point.observed_amplitude != null && Number.isFinite(point.observed_amplitude)).map((point, index) => <circle key={index} cx={x(point.frequency_thz)} cy={y(point.observed_amplitude!)} r="2" fill="#2563eb" />)}
      {!!candidate.size && <path d={line(p => candidate.get(p.frequency_thz))} stroke="#d97706" strokeWidth="2" fill="none" />}
      <text x="65" y="302" fontSize="12">{show(minX)}</text><text x="820" y="302" fontSize="12">{show(maxX)}</text>
      <text x="8" y="38" fontSize="12">{show(maxY)}</text><text x="8" y="280" fontSize="12">{show(minY)}</text>
      <text x="390" y="325" fontSize="13">频率 (THz)</text><text x="65" y="17" fontSize="12">幅值 ({curve.unit || '单位未说明'})</text>
    </Box>
    <Typography variant="caption">蓝：原图观测　紫：{reconstructionLabel}　橙：所选候选。未知点保持缺口。</Typography>
  </Box>
}
export default function SpectrumDetailPage() {
  const { collectionId } = useParams(), [params, setParams] = useSearchParams(), location = useLocation(), navigate = useNavigate()
  const targetKind = params.get('target'), targetId = params.get('target_id')
  const target = ['upload', 'paper', 'revision'].includes(targetKind || '') && targetId ? { target: targetKind, target_id: targetId } as PropertySpectrumTarget : undefined
  const { listing, loading, error, reload } = usePropertySpectra(target)
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [materialStates, setMaterialStates] = useState<any[]>([]), [statesLoaded, setStatesLoaded] = useState(false)
  const [material, setMaterial] = useState(''), [materialError, setMaterialError] = useState('')
  const [assignedState, setAssignedState] = useState(''), [assigning, setAssigning] = useState(false)
  const [image, setImage] = useState(''), [actionError, setActionError] = useState(''), [variant, setVariant] = useState('raw'), [page, setPage] = useState(0)
  const item = listing?.items.find(value => value.id === collectionId)
  const curveId = params.get('curve')
  const curve = item?.result.curves.find(value => value.id === curveId)
  const query = target ? spectrumQuery(target) : ''
  const mismatch = !target ? '谱详情地址缺少有效目标。'
    : listing && (!item || (curveId ? !curve : Boolean(item.result.curves.length)) || (item.state_key || 'unassigned') !== params.get('state_key'))
      ? '该目标或材料状态下的谱曲线不可访问，可能已删除或没有查看权限。'
      : item && (String(item.version) !== params.get('collection_version') || (params.get('run') && item.run.id !== params.get('run')))
        ? '谱版本已变化，请返回原模块重新打开最新结果。' : ''
  const validItem = !mismatch ? item : undefined
  const unassigned = Boolean(validItem && (!validItem.state_key || statesLoaded && !material))
  const calibration = validItem?.result.calibration
  const canAssign = listing?.can_edit && statesLoaded && materialStates.length > 0 && Array.isArray(calibration?.curves) && calibration.curves.length > 0
  useEffect(() => {
    let active = true, url = ''
    setImage(''); setActionError(''); setAssignedState('')
    if (validItem) void api.download(SPECTRUM_API + '/' + encodeURIComponent(validItem.id) + '/image?' + query).then(blob => {
      url = URL.createObjectURL(blob)
      if (active) setImage(url)
      else URL.revokeObjectURL(url)
    }).catch(error => { if (active) setActionError('原图暂不可读取：' + error.message) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [validItem?.id, validItem?.version, query])
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
  useEffect(() => { setVariant('raw'); setPage(0); setWorkspaceOpen(false) }, [collectionId, curve?.id])
  const download = async (format: 'csv' | 'json') => {
    if (!validItem) return
    try {
      const blob = await api.download(SPECTRUM_API + '/' + encodeURIComponent(validItem.id) + '/export?' + query + '&format=' + format)
      const url = URL.createObjectURL(blob), anchor = document.createElement('a')
      anchor.href = url; anchor.download = 'spectrum-' + validItem.id + '.' + format; anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error: any) { setActionError('导出失败：' + error.message) }
  }
  const chooseCurve = (id: string) => {
    const next = new URLSearchParams(params); next.set('curve', id); setParams(next, { replace: true })
  }
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
  const candidates = validItem?.result.candidates || {}
  const choices: Array<{ key: string; label: string; frequencies: number[]; amplitudes: number[] }> = []
  if (curve?.kind === 'alpha2f') {
    if (candidates.zero_baseline?.amplitude) choices.push({ key: 'zero_baseline', label: '零基线候选', frequencies: candidates.zero_baseline.frequency_thz || [], amplitudes: candidates.zero_baseline.amplitude })
    if (candidates.joint?.alpha2f) choices.push({ key: 'joint', label: '联合候选', frequencies: candidates.joint.frequency_thz || [], amplitudes: candidates.joint.alpha2f })
  }
  const normalization = candidates.dos_normalization
  const norm = normalization?.components?.[curve?.projection || curve?.id || '']
  if (curve?.kind === 'phonon_dos' && Array.isArray(norm)) choices.push({ key: 'normalized', label: '共同尺度归一化候选', frequencies: normalization.frequency_thz || [], amplitudes: norm })
  const selected = choices.find(choice => choice.key === variant)
  const candidate = new Map<number, number>(selected?.frequencies.map((frequency, index) => [frequency, selected.amplitudes[index]]) || [])
  const relatedCurves = (validItem?.result.curves || []).filter(value => curve?.kind === 'phonon_dos' ? value.kind === 'phonon_dos' : ['alpha2f', 'cumulative_lambda'].includes(value.kind))
  const title = curve ? (spectrumNames[curve.kind] || '谱') + '解析详情' : '谱图候选 · 核对归属'
  const limitation = validItem?.result.quality?.limitations || validItem?.result.failures || []
  return <Box sx={{ minWidth: 0, pb: 4 }}>
    <Button onClick={() => navigate(safeSpectrumReturn(params.get('return')))}>返回原模块</Button>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap', my: 2 }}>
      <Box><Typography variant="overline" color="primary">谱数据 · 独立详情页</Typography><Typography variant="h5" fontWeight={700}>{title}</Typography></Box>
      {validItem && curve && <Box><Button onClick={() => void download('json')}>导出 JSON</Button><Button onClick={() => void download('csv')}>导出 CSV</Button></Box>}
    </Box>
    {loading && <Typography role="status">正在读取谱结果…</Typography>}
    {(error || mismatch) && <Alert severity="error">{mismatch || error}<Button onClick={reload}>重新读取</Button></Alert>}
    {validItem && <>
      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, mb: 2 }}>
        <Typography fontWeight={700}>{unassigned ? '归属待确认' : material || location.state?.materialSummary || '正在读取材料状态…'}</Typography>
        <Typography variant="body2" color="text.secondary">{validItem.source.source_name || '来源未命名'} · 第 {validItem.source.pdf_page ?? '未知'} 页 · {validItem.source.panel_id || ''}</Typography>
        {calibration?.caption && <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{calibration.caption}</Typography>}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}><Chip size="small" label={spectrumNames[validItem.run.status] || validItem.run.status} /><Typography variant="caption">数据版本 {validItem.version}{curve ? ' · ' + (spectrumNames[validItem.review[curve.id]?.status || 'needs_review']) : ''}</Typography></Box>
      </Box>
      {materialError && <Alert severity="info">{materialError}</Alert>}
      {validItem.stale && <Alert severity="warning">材料条件或来源已变化，旧采纳与参考比较已失效，请核对并重新提取。</Alert>}
      {validItem.run.error_message && <Alert severity="warning">{validItem.run.error_message}</Alert>}
      {actionError && <Alert severity="warning">{actionError}</Alert>}
      {unassigned && <Box sx={{ bgcolor: '#FFFCF5', border: '1px solid #ECE1C6', borderRadius: 2, p: 2, my: 2 }}>
        <Typography fontWeight={600}>这组谱尚未归属到当前材料状态</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>先对照原图与图注核对材料、物相和压力；确认后重新计算质量，旧采纳失效。</Typography>
        {listing?.can_edit ? canAssign ? <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <TextField select size="small" label="选择归属材料状态" value={assignedState} disabled={assigning} onChange={event => setAssignedState(event.target.value)} sx={{ minWidth: 240, maxWidth: '100%' }}>
            {materialStates.map((state, index) => <MenuItem key={state.state_key || index} value={state.state_key || 'state-' + (index + 1)}>{materialStateSummary(state)}</MenuItem>)}
          </TextField>
          <Button variant="contained" disabled={!assignedState || assigning} onClick={() => void confirmAssignment()}>{assigning ? '正在保存…' : '确认归属并重新计算'}</Button>
        </Box> : <Typography variant="body2">当前缺少可用标定或材料状态，请先在下方“原图叠加、标定校对与逐谱审核”中核对标定，不能仅凭图片生成数值。</Typography>
          : <Typography variant="body2">当前为只读查看，归属须由有编辑权限的用户确认。</Typography>}
      </Box>}
      {curve && <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', my: 2 }}>
        <TextField size="small" select label="谱曲线" value={curve.id} onChange={event => chooseCurve(event.target.value)} sx={{ minWidth: 180 }}>
          {relatedCurves.map(value => <MenuItem key={value.id} value={value.id}>{(value.projection ? value.projection + ' · ' : '') + spectrumNames[value.kind]}</MenuItem>)}
        </TextField>
        <TextField size="small" select label="谱候选" value={variant} onChange={event => setVariant(event.target.value)} sx={{ minWidth: 180 }}><MenuItem value="raw">原始重建</MenuItem>{choices.map(choice => <MenuItem key={choice.key} value={choice.key}>{choice.label}</MenuItem>)}</TextField>
      </Box>}
      {!curve && <Alert severity="info" sx={{ mb: 2 }}>尚未得到数值曲线。{Array.isArray(limitation) ? limitation.map(value => typeof value === 'string' ? value : JSON.stringify(value)).join('；') : ''}</Alert>}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0,1fr)', lg: 'minmax(0,1fr) minmax(0,1fr)' }, gap: 2, my: 2 }}>
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>论文原图</Typography>
          {image ? <Box component="img" src={image} alt="经权限校验读取的谱原图" sx={{ maxWidth: '100%', maxHeight: 600, objectFit: 'contain' }} /> : <Typography variant="caption">原图正在读取或暂不可用；数值结果不以示例替代。</Typography>}
        </Box>
        {curve && <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>提取结果</Typography>
          {variant === 'normalized' ? <><SpectrumPlot curve={curve} candidate={new Map()} /><Typography variant="body2">共同尺度归一化候选 · {normalization.unit || '单位未说明'}</Typography>
            <SpectrumPlot reconstructionLabel="共同尺度归一化候选" curve={{ ...curve, unit: normalization.unit || '', points: curve.points.map(point => ({ ...point, observed_amplitude: null, reconstructed_amplitude: candidate.get(point.frequency_thz) ?? null })) }} candidate={new Map()} />
          </> : <SpectrumPlot curve={curve} candidate={candidate} />}
        </Box>}
      </Box>
      {curve && <Box component="details" sx={{ my: 2 }}><Typography component="summary" sx={{ cursor: 'pointer' }}>提取质量与比较</Typography><SpectrumQuality quality={validItem.result.quality || {}} /></Box>}
      {curve && validItem.review[curve.id]?.reason && <Alert severity="info">采纳说明：{validItem.review[curve.id].reason} {validItem.review[curve.id].frequency_intervals_thz?.map(pair => pair.join('–') + ' THz').join('；')}</Alert>}
      {target && <Box component="details" open={workspaceOpen} onToggle={event => setWorkspaceOpen(event.currentTarget.open)} sx={{ my: 2 }}><Typography component="summary" sx={{ cursor: 'pointer' }}>原图叠加、标定校对与逐谱审核</Typography>
        {workspaceOpen && <SpectrumProvider target={target} states={materialStates} readOnly={!listing?.can_edit && !listing?.can_review}>
          <Alert severity="info">校对或审核保存后，请返回原模块查看最新版本。</Alert>
          <SpectrumCollectionWorkspace collectionId={validItem.id} curveId={curve?.id} />
        </SpectrumProvider>}
      </Box>}
      {curve && <>
        <Typography fontWeight={600} sx={{ mt: 2 }}>逐点数据 · 频率 (THz) / 原幅值 ({curve.unit || '单位未说明'}){variant === 'normalized' && ' / 候选 (' + (normalization.unit || '单位未说明') + ')'}</Typography>
        <Box sx={{ overflowX: 'auto' }}><Table size="small"><TableHead><TableRow>{['频率', '原图观测', '原始重建', '所选候选', '点来源', '检测方式'].map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
          {curve.points.slice(page * 100, (page + 1) * 100).map((point, index) => <TableRow key={index}><TableCell>{show(point.frequency_thz)}</TableCell><TableCell>{show(point.observed_amplitude)}</TableCell><TableCell>{show(point.reconstructed_amplitude)}</TableCell><TableCell>{show(candidate.get(point.frequency_thz))}</TableCell><TableCell>{spectrumNames[point.status] || point.status}</TableCell><TableCell>{point.detection_mode || '未说明'}</TableCell></TableRow>)}
        </TableBody></Table></Box>
        <TablePagination component="div" count={curve.points.length} rowsPerPage={100} rowsPerPageOptions={[100]} page={page} onPageChange={(_, next) => setPage(next)} labelDisplayedRows={({ from, to, count }) => String(from) + '–' + to + ' / ' + count} />
      </>}
    </>}
  </Box>
}
