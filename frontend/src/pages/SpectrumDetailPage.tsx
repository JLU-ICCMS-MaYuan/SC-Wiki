import { useEffect, useState } from 'react'
import { Alert, Box, Button, MenuItem, Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Typography } from '@mui/material'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
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
    <Box component="svg" viewBox="0 0 900 330" role="img" aria-label="谱曲线：原图观测、原始重建与所选候选" sx={{ width: '100%', minWidth: 480 }}>
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
const qualityLabels: Record<string, string> = { observed_fraction: '原图观测覆盖率', missing_fraction: '缺失比例', reconstructed_fraction: '重建比例', frequency_interval_thz: '频域 (THz)', largest_unobserved_gap_samples: '最大未观测间隔（点）', clipped_frequencies_thz: '抵框频率 (THz)', omitted_low_frequency_interval_thz: '未覆盖低频 (THz)', frequency_tick_residual: '频率刻度残差', amplitude_tick_residual: '幅值刻度残差', lambda_integral: 'λ 积分', omega_log_k: 'ωlog (K)', reason: '说明' }
function Quality({ value }: { value: Record<string, any> }) {
  const rows: Array<[string, unknown]> = []
  for (const [id, metrics] of Object.entries<any>(value.curves || {})) for (const [key, metric] of Object.entries(metrics)) if (qualityLabels[key]) rows.push([`${id} · ${qualityLabels[key]}`, metric])
  for (const [variant, metrics] of Object.entries<any>(value.integrals || {})) for (const [key, metric] of Object.entries(metrics)) if (qualityLabels[key]) rows.push([`${({ raw: '原始重建', zero_baseline: '零基线候选', joint: '联合候选' } as Record<string, string>)[variant] || variant} · ${qualityLabels[key]}`, metric])
  return <>
    {value.metric_domain_note && <Alert severity="info">{String(value.metric_domain_note)}</Alert>}
    <Table size="small"><TableBody>{rows.map(([name, metric], index) => <TableRow key={index}><TableCell>{name}</TableCell><TableCell sx={{ overflowWrap: 'anywhere' }}>{Array.isArray(metric) ? metric.map(show).join('–') : typeof metric === 'number' ? show(metric) : String(metric ?? '未知')}</TableCell></TableRow>)}</TableBody></Table>
    {(value.limitations || []).map((text: string, index: number) => <Typography key={index} variant="body2">{text}</Typography>)}
    <Box component="details"><Typography component="summary" sx={{ cursor: 'pointer' }}>完整质量与比较数据</Typography><Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 12 }}>{JSON.stringify(value, null, 2)}</Box></Box>
  </>
}
export default function SpectrumDetailPage() {
  const { collectionId } = useParams(), [params] = useSearchParams(), location = useLocation(), navigate = useNavigate()
  const kind = params.get('target'), targetId = params.get('target_id')
  const target = ['upload', 'paper', 'revision'].includes(kind || '') && targetId ? { target: kind, target_id: targetId } as PropertySpectrumTarget : undefined
  const { listing, loading, error, reload } = usePropertySpectra(target)
  const [material, setMaterial] = useState(''), [materialError, setMaterialError] = useState('')
  const [image, setImage] = useState(''), [actionError, setActionError] = useState(''), [variant, setVariant] = useState('raw'), [page, setPage] = useState(0)
  const item = listing?.items.find(item => item.id === collectionId)
  const curve = item?.result.curves.find(curve => curve.id === params.get('curve'))
  const query = target ? spectrumQuery(target) : ''
  const mismatch = !target ? '谱详情地址缺少有效目标。' : listing && (!item || !curve || item.state_key !== params.get('state_key')) ? '该目标或材料状态下的谱曲线不可访问，可能已删除或没有查看权限。'
    : item && (String(item.version) !== params.get('collection_version') || (params.get('run') && item.run.id !== params.get('run'))) ? '谱版本已变化，请返回原模块重新打开最新结果。' : ''
  const validItem = !mismatch ? item : undefined
  useEffect(() => {
    let active = true, url = ''
    setImage(''); setActionError('')
    if (validItem) void api.download(`${SPECTRUM_API}/${encodeURIComponent(validItem.id)}/image?${query}`).then(blob => {
      url = URL.createObjectURL(blob); if (active) setImage(url)
    }).catch(error => { if (active) setActionError(`原图暂不可读取：${error.message}`) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [validItem?.id, validItem?.version, query])
  useEffect(() => {
    const controller = new AbortController()
    setMaterial(''); setMaterialError('')
    if (!validItem || !target) return () => controller.abort()
    const revisionPaper = safeSpectrumReturn(params.get('return')).match(/^\/papers\/(\d+)\/revise(?:[?#]|$)/)?.[1]
    const endpoint = target.target === 'upload' ? `/api/rag/upload-tasks/${encodeURIComponent(target.target_id)}/draft`
      : target.target === 'paper' ? `/api/papers/${encodeURIComponent(target.target_id)}`
        : revisionPaper ? `/api/rag/papers/${revisionPaper}/revision-draft` : ''
    if (!endpoint) { setMaterialError('材料条件尚未定位，请返回原模块查看。'); return () => controller.abort() }
    void api.get<any>(endpoint, { signal: controller.signal }).then(response => {
      if (controller.signal.aborted) return
      if (target.target === 'revision' && response.revision_id !== target.target_id) throw new Error('返修草稿版本不匹配')
      const draft = response.data || response
      const state = (draft.material_states || []).find((state: any, index: number) => (state.state_key || `state-${index + 1}`) === validItem.state_key)
      if (!state) throw new Error('未找到对应材料状态')
      setMaterial(materialStateSummary(state))
    }).catch(error => { if (!controller.signal.aborted) setMaterialError(`当前材料条件暂不可读取：${error.message}`) })
    return () => controller.abort()
  }, [validItem?.id, query, params.get('return')])
  useEffect(() => { setVariant('raw'); setPage(0) }, [collectionId, curve?.id])
  const download = async (format: 'csv' | 'json') => {
    if (!validItem) return
    try {
      const blob = await api.download(`${SPECTRUM_API}/${encodeURIComponent(validItem.id)}/export?${query}&format=${format}`)
      const url = URL.createObjectURL(blob), a = document.createElement('a')
      a.href = url; a.download = `spectrum-${validItem.id}.${format}`; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error: any) { setActionError(`导出失败：${error.message}`) }
  }
  const candidates = item?.result.candidates || {}
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
  return <Box sx={{ minWidth: 0, pb: 4 }}>
    <Button onClick={() => navigate(safeSpectrumReturn(params.get('return')))}>返回原模块</Button>
    <Typography variant="h5" fontWeight={700} sx={{ my: 2 }}>{curve ? spectrumNames[curve.kind] || '谱' : '谱'}解析详情</Typography>
    {loading && <Typography role="status">正在读取谱结果…</Typography>}
    {(error || mismatch) && <Alert severity="error">{mismatch || error}<Button onClick={reload}>重新读取</Button></Alert>}
    {validItem && curve && <>
      <Typography>{material || location.state?.materialSummary || `材料状态：${validItem.state_key}`}</Typography>
      {materialError && <Alert severity="info">{materialError} 若显示了材料摘要，它是打开详情时的快照。</Alert>}
      <Typography variant="body2" color="text.secondary">{validItem.source.source_name || '来源未命名'} · 第 {validItem.source.pdf_page ?? '未知'} 页 · {validItem.source.panel_id || ''}</Typography>
      <Typography variant="caption">集合版本 {validItem.version} · {spectrumNames[validItem.run.status] || validItem.run.status} · 运行 {validItem.run.id || '未提供'} · {spectrumNames[validItem.review[curve.id]?.status || 'needs_review']}</Typography>
      {validItem.stale && <Alert severity="warning">材料条件或来源已变化，旧采纳与参考比较已失效，请返回核对并重新提取。</Alert>}
      {validItem.run.error_message && <Alert severity="warning">{validItem.run.error_message}</Alert>}
      {actionError && <Alert severity="warning">{actionError}</Alert>}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', my: 2 }}>
        <TextField size="small" select label="谱候选" value={variant} onChange={event => setVariant(event.target.value)} sx={{ minWidth: 180 }}><MenuItem value="raw">原始重建</MenuItem>{choices.map(choice => <MenuItem key={choice.key} value={choice.key}>{choice.label}</MenuItem>)}</TextField>
        <Button onClick={() => void download('json')}>导出 JSON</Button><Button onClick={() => void download('csv')}>导出 CSV</Button>
      </Box>
      {variant === 'normalized' ? <>
        <SpectrumPlot curve={curve} candidate={new Map()} />
        <Typography variant="body2">共同尺度归一化候选 · {normalization.unit || '单位未说明'}</Typography>
        <SpectrumPlot reconstructionLabel="共同尺度归一化候选" curve={{ ...curve, unit: normalization.unit || '', points: curve.points.map(point => ({ ...point, observed_amplitude: null, reconstructed_amplitude: candidate.get(point.frequency_thz) ?? null })) }} candidate={new Map()} />
      </> : <SpectrumPlot curve={curve} candidate={candidate} />}
      {image && <Box component="details" open sx={{ my: 2 }}><Typography component="summary" sx={{ cursor: 'pointer' }}>论文原图</Typography><Box component="img" src={image} alt="经权限校验读取的谱原图" sx={{ maxWidth: '100%', maxHeight: 600, objectFit: 'contain' }} /></Box>}
      <Box component="details" sx={{ my: 2 }}><Typography component="summary" sx={{ cursor: 'pointer' }}>提取质量与比较</Typography><Quality value={validItem.result.quality || {}} /></Box>
      {validItem.review[curve.id]?.reason && <Alert severity="info">采纳说明：{validItem.review[curve.id].reason} {validItem.review[curve.id].frequency_intervals_thz?.map(pair => `${pair.join('–')} THz`).join('；')}</Alert>}
      <Typography fontWeight={600} sx={{ mt: 2 }}>逐点数据 · 频率 (THz) / 原幅值 ({curve.unit || '单位未说明'}){variant === 'normalized' && ` / 候选 (${normalization.unit || '单位未说明'})`}</Typography>
      <Box sx={{ overflowX: 'auto' }}><Table size="small"><TableHead><TableRow>{['频率', '原图观测', '原始重建', '所选候选', '点来源', '检测方式'].map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
        {curve.points.slice(page * 100, (page + 1) * 100).map((point, index) => <TableRow key={index}><TableCell>{show(point.frequency_thz)}</TableCell><TableCell>{show(point.observed_amplitude)}</TableCell><TableCell>{show(point.reconstructed_amplitude)}</TableCell><TableCell>{show(candidate.get(point.frequency_thz))}</TableCell><TableCell>{spectrumNames[point.status] || point.status}</TableCell><TableCell>{point.detection_mode || '未说明'}</TableCell></TableRow>)}
      </TableBody></Table></Box>
      <TablePagination component="div" count={curve.points.length} rowsPerPage={100} rowsPerPageOptions={[100]} page={page} onPageChange={(_, next) => setPage(next)} labelDisplayedRows={({ from, to, count }) => `${from}–${to} / ${count}`} />
    </>}
  </Box>
}
