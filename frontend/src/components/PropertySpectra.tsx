import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Typography } from '@mui/material'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { hasSpectrumData, loadPropertySpectra, spectrumDetailPath, spectrumGroups, spectrumInterval, spectrumNames, spectrumQuery, usePropertySpectra, type PropertySpectrumListing, type PropertySpectrumTarget, type PropertySpectrumItem, type PropertySpectrumCurve } from '../lib/propertySpectra'
import type { PropertyModuleCode } from '../lib/propertyModules'
import PropertyModuleSection from './PropertyModuleSection'

export interface PropertySpectraContext { target: PropertySpectrumTarget; beforeNavigate?: () => Promise<boolean> }
const Spectra = createContext<(PropertySpectraContext & ReturnType<typeof usePropertySpectra> & { stateKeys?: string[]; readOnly: boolean }) | null>(null)
const Material = createContext({ stateKey: '', summary: '' })
export function PropertySpectraProvider({ context, stateKeys, readOnly = false, children }: PropsWithChildren<{ context?: PropertySpectraContext; stateKeys?: string[]; readOnly?: boolean }>) {
  const state = usePropertySpectra(context?.target)
  const navigation = useRef(context?.beforeNavigate)
  navigation.current = context?.beforeNavigate
  const beforeNavigate = useCallback(() => navigation.current?.() ?? Promise.resolve(true), [])
  const stateKeysIdentity = JSON.stringify(stateKeys)
  const stableStateKeys = useMemo(() => stateKeys, [stateKeysIdentity])
  const value = useMemo(() => context ? { target: context.target, beforeNavigate, ...state, stateKeys: stableStateKeys, readOnly } : null,
    [context?.target.target, context?.target.target_id, beforeNavigate, stableStateKeys, readOnly, state.listing, state.loading, state.error, state.reload, state.replaceListing])
  const busy = state.listing?.jobs.some(job => ['queued', 'running'].includes(job.status)) || state.listing?.items.some(item => ['queued', 'running'].includes(item.run.status))
  useEffect(() => { if (!busy) return; const timer = window.setInterval(state.reload, 3000); return () => window.clearInterval(timer) }, [busy, state.reload])
  return <Spectra.Provider value={value}>{children}</Spectra.Provider>
}
export function PropertySpectrumState({ stateKey, summary, children }: PropsWithChildren<{ stateKey: string; summary: string }>) {
  const value = useMemo(() => ({ stateKey, summary }), [stateKey, summary])
  return <Material.Provider value={value}>{children}</Material.Provider>
}

/** 提取控制与未归属摘要都不挂载原图、图表或点表。 */
export function PropertySpectrumControls() {
  const ctx = useContext(Spectra), [busy, setBusy] = useState(false), [error, setError] = useState('')
  if (!ctx) return null
  const start = async () => {
    setBusy(true); setError('')
    try {
      if (ctx.beforeNavigate && !(await ctx.beforeNavigate())) return
      const current = await loadPropertySpectra(ctx.target)
      await api.post('/api/rag/spectra/extract', { ...ctx.target, expected_version: current.version })
      ctx.reload()
    } catch (error: any) { setError(error.message || '无法启动谱提取') }
    finally { setBusy(false) }
  }
  return <Box sx={{ mb: 2, pointerEvents: 'auto', '& .MuiButton-root': { display: 'inline-flex !important' } }}>
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
      <Typography variant="subtitle2">谱图提取</Typography>
      {!ctx.readOnly && ctx.listing?.can_edit && <Button size="small" disabled={busy} onClick={() => void start()}>{busy ? '正在提交…' : '自动发现并提取谱图'}</Button>}
      <Button size="small" onClick={ctx.reload}>刷新谱状态</Button>
    </Box>
    {(error || ctx.error) && <Alert severity="warning">{error || ctx.error}</Alert>}
    {ctx.listing?.jobs.map(job => <Box component="details" key={job.id} sx={{ fontSize: 12, color: 'text.secondary' }}>
      <Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>谱提取任务 · {spectrumNames[job.status] || job.status}</Typography>
      <Typography variant="caption">{job.error_message || '按材料状态查看下方提取结果。'}</Typography>
    </Box>)}
  </Box>
}

export function PropertySpectrumSection({ moduleCode }: { moduleCode: PropertyModuleCode }) {
  const ctx = useContext(Spectra), material = useContext(Material)
  if (!ctx || !['dynamical_properties', 'superconductive_properties'].includes(moduleCode)) return null
  const dos = moduleCode === 'dynamical_properties'
  const groups = spectrumGroups(ctx.listing?.items || [], material.stateKey).filter(group => group.kind === (dos ? 'phonon_dos' : 'alpha2f'))
  return <Box sx={{ minWidth: 0, my: 1, pointerEvents: 'auto', '& .MuiButton-root': { display: 'inline-flex !important' } }}>
    {ctx.loading && <Typography variant="caption" role="status">正在读取谱解析结果…</Typography>}
    {ctx.error && <Alert severity="warning">谱解析结果暂不可读取：{ctx.error} <Button size="small" onClick={ctx.reload}>重试</Button></Alert>}
    {ctx.listing && !groups.length && <Box sx={{ border: '1px dashed', borderColor: 'divider', borderRadius: 1.5, p: 1.5, display: 'flex', gap: 1, justifyContent: 'space-between', flexWrap: 'wrap' }}>
      <Typography variant="caption" color="text.secondary">尚无明确归属于此状态的{dos ? '声子 DOS' : ' α²F 谱'}</Typography>
      <Button size="small" disabled>{dos ? '暂无声子 DOS' : '暂无 α²F'}</Button>
    </Box>}
    {groups.map(group => <SpectrumSummary key={group.item.id + ':' + group.kind} item={group.item} curves={group.curves} dos={dos} />)}
  </Box>
}

function SpectrumSummary({ item, curves, dos, unassigned = false, attempt = false }: { item: PropertySpectrumItem; curves: PropertySpectrumCurve[]; dos?: boolean; unassigned?: boolean; attempt?: boolean }) {
  const ctx = useContext(Spectra)!, material = useContext(Material)
  const location = useLocation()
  const first = curves.find(curve => curve.kind === 'alpha2f') || curves[0]
  const returnTo = location.pathname + location.search + (unassigned ? '#spectra-unassigned' : '#material-state-' + encodeURIComponent(material.stateKey))
  const hasAlpha = curves.some(curve => curve.kind === 'alpha2f') || (!curves.length && item.result.calibration?.curves?.some((curve: { kind: string }) => curve.kind === 'alpha2f'))
  const statuses = [...new Set(curves.map(curve => item.review[curve.id]?.status || 'needs_review'))]
  const review = statuses.length === 1 ? spectrumNames[statuses[0]] || statuses[0] : '部分曲线待核对'
  const title = attempt ? '谱提取记录 · 未生成曲线或标定' : unassigned ? (curves.length ? [...new Set(curves.map(curve => spectrumNames[curve.kind]))].join(' / ') : '谱图候选 · 尚无数值曲线')
    : dos ? '声子态密度 DOS' : hasAlpha ? 'Eliashberg 谱函数 α²F(ω)' : '累计 λ（尚无 α²F 数值）'
  const failures = item.result.failures?.length ? item.result.failures : item.result.quality?.limitations || []
  return <Box data-spectrum-collection={item.id} data-spectrum-group={unassigned ? 'unassigned' : dos ? 'phonon_dos' : 'alpha2f'} sx={{ bgcolor: unassigned ? '#FFFCF5' : '#FAF9FF', border: '1px solid', borderColor: unassigned ? '#ECE1C6' : '#E4DFFA', borderRadius: 1.5, px: 2, py: 1.5, mb: 1 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
      <Box sx={{ minWidth: 0 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}><Typography variant="body2" fontWeight={600}>{title}</Typography>
          {!!curves.length && <Chip size="small" label={dos ? String(curves.length) + ' 条曲线' : curves.some(curve => curve.kind === 'cumulative_lambda') ? '含累计 λ' : 'α²F'} sx={{ height: 22, fontSize: 11 }} />}
        </Box>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: .5, overflowWrap: 'anywhere' }}>
          {item.source.source_name || '来源未命名'} · 第 {item.source.pdf_page ?? '未知'} 页{item.source.panel_id ? ' · ' + item.source.panel_id : ''} · {spectrumInterval(curves)}
        </Typography>
        {!curves.length && !unassigned && <Typography variant="caption" color="text.secondary">尚无数值曲线，可查看原图与提取状态。</Typography>}
        {unassigned && !attempt && <Typography variant="caption" color="text.secondary">材料条件尚未确定，请先检查图注与归属。</Typography>}
        {attempt && <Typography variant="caption" color="text.secondary" display="block" sx={{ overflowWrap: 'anywhere', maxHeight: 120, overflowY: 'auto' }}>{failures.map((value: unknown) => typeof value === 'string' ? value : JSON.stringify(value)).join('；') || item.run.error_message || '尚无可供分配的谱数据。'}</Typography>}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1.5, ml: 'auto', '& .MuiButton-root': { whiteSpace: 'nowrap', flexShrink: 0 } }}>
        <Typography variant="caption" color="text.secondary">{item.stale ? '条件已变化，需重新核对' : ['queued', 'running', 'failed', 'needs_review'].includes(item.run.status) ? spectrumNames[item.run.status] : review}</Typography>
        {unassigned && !ctx.readOnly && ctx.listing?.can_edit && ctx.target.target !== 'paper' && <DeleteUnassignedSpectrum item={item} attempt={attempt} />}
        <Button component="a" href={spectrumDetailPath(ctx.target, item, returnTo, first, unassigned ? undefined : dos ? 'phonon_dos' : 'alpha2f')} target="_blank" rel="noopener noreferrer" variant="outlined" size="small" endIcon={<OpenInNewIcon sx={{ fontSize: '14px !important' }} />}>{attempt ? '查看提取记录' : unassigned ? '核对归属' : dos ? '查看声子 DOS' : hasAlpha ? '查看 α²F' : '查看累计 λ'}</Button>
      </Box>
    </Box>
  </Box>
}

function DeleteUnassignedSpectrum({ item, attempt }: { item: PropertySpectrumItem; attempt: boolean }) {
  const ctx = useContext(Spectra)!
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const extracting = ctx.listing?.jobs.some(job => ['queued', 'running'].includes(job.status))
    || ctx.listing?.items.some(value => ['queued', 'running'].includes(value.run.status))
  const label = attempt ? '删除提取记录' : '删除谱数据'
  const remove = async () => {
    setBusy(true); setError('')
    try {
      if (ctx.beforeNavigate && !(await ctx.beforeNavigate())) {
        setError('主表单尚未保存，未删除记录。请先处理保存提示。')
        return
      }
      const current = await loadPropertySpectra(ctx.target)
      const query = new URLSearchParams({ ...ctx.target, expected_version: current.version, expected_collection_version: String(item.version) })
      const next = await api.del<PropertySpectrumListing>(`/api/rag/spectra/${encodeURIComponent(item.id)}?${query}`)
      ctx.replaceListing(next)
      setOpen(false)
    } catch (error: any) { setError(error.message || '删除失败，记录已保留。') }
    finally { setBusy(false) }
  }
  return <>
    <Button color="error" size="small" disabled={busy || extracting} onClick={() => { setError(''); setOpen(true) }}>{label}</Button>
    <Dialog open={open} onClose={() => { if (!busy) setOpen(false) }} aria-labelledby={`delete-spectrum-${item.id}`}>
      <DialogTitle id={`delete-spectrum-${item.id}`}>{label}？</DialogTitle>
      <DialogContent>
        <DialogContentText>{item.source.source_name || '来源未命名'} · 第 {item.source.pdf_page ?? '未知'} 页</DialogContentText>
        <DialogContentText sx={{ mt: 1 }}>删除后不再保留这条记录及其提取历史，也不会随论文提交审核。原 PDF 和其他谱数据不受影响。此操作无法撤销。</DialogContentText>
        {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button disabled={busy} onClick={() => setOpen(false)}>取消</Button>
        <Button color="error" disabled={busy || extracting} onClick={() => void remove()}>{busy ? '正在删除…' : '确认删除'}</Button>
      </DialogActions>
    </Dialog>
  </>
}

export function UnassignedPropertySpectra() {
  const ctx = useContext(Spectra), restored = useRef(false)
  useEffect(() => {
    if (restored.current || !ctx?.listing || window.location.hash !== '#spectra-unassigned') return
    const section = document.getElementById('spectra-unassigned')
    if (section) {
      section.scrollIntoView?.({ block: 'start' }); section.tabIndex = -1; section.focus({ preventScroll: true })
      restored.current = true
    }
  }, [ctx?.listing])
  if (!ctx?.listing) return null
  const items = ctx.listing.items.filter(item => !item.state_key || ctx.stateKeys && !ctx.stateKeys.includes(item.state_key))
  if (!items.length) return null
  const spectra = items.filter(hasSpectrumData), attempts = items.filter(item => !hasSpectrumData(item))
  return <Box id="spectra-unassigned" sx={{ mt: 3, pointerEvents: 'auto', '& .MuiButton-root': { display: 'inline-flex !important' } }}>
    {!!spectra.length && <>
    <Typography variant="subtitle2" sx={{ mb: 1 }}>待确认归属 · {spectra.length} 组谱数据</Typography>
    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>未确认的谱不并入任何材料状态。</Typography>
    {spectra.map(item => <SpectrumSummary key={item.id} item={item} curves={item.result.curves} unassigned />)}
    </>}
    {!!attempts.length && <Box component="details" sx={{ mt: 2 }}>
      <Typography component="summary" variant="subtitle2" sx={{ cursor: 'pointer', mb: 1 }}>谱提取记录 · {attempts.length} 条未生成曲线或标定</Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>保留失败原因与来源。这些记录不计入待确认归属的谱数量。</Typography>
      {attempts.map(item => <SpectrumSummary key={item.id} item={item} curves={[]} unassigned attempt />)}
    </Box>}
  </Box>
}

/** 谱入口不依赖标量记录；不为显示入口伪造物性数据。 */
export function MissingPropertySpectrumModules({ existing }: { existing: PropertyModuleCode[] }) {
  const ctx = useContext(Spectra)
  if (!ctx) return null
  const modules: Array<{ code: PropertyModuleCode; label: string }> = [
    { code: 'dynamical_properties', label: '动力学性质' }, { code: 'superconductive_properties', label: '超导性质' },
  ]
  return <>{modules.filter(module => !existing.includes(module.code)).map(module => <Box key={module.code} data-testid={'property-module-' + module.code} sx={{ borderTop: 1, borderColor: 'divider', pt: 1.5 }}>
    <PropertyModuleSection title={module.label}><PropertySpectrumSection moduleCode={module.code} /></PropertyModuleSection>
  </Box>)}</>
}
