import { createContext, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { Alert, Box, Button, Chip, Typography } from '@mui/material'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { loadPropertySpectra, spectrumDetailPath, spectrumGroups, spectrumInterval, spectrumNames, spectrumQuery, usePropertySpectra, type PropertySpectrumTarget, type PropertySpectrumItem, type PropertySpectrumCurve } from '../lib/propertySpectra'
import type { PropertyModuleCode } from '../lib/propertyModules'
import PropertyModuleSection from './PropertyModuleSection'

export interface PropertySpectraContext { target: PropertySpectrumTarget; beforeNavigate?: () => Promise<boolean> }
const Spectra = createContext<(PropertySpectraContext & ReturnType<typeof usePropertySpectra> & { stateKeys?: string[]; readOnly: boolean }) | null>(null)
const Material = createContext({ stateKey: '', summary: '' })
export function PropertySpectraProvider({ context, stateKeys, readOnly = false, children }: PropsWithChildren<{ context?: PropertySpectraContext; stateKeys?: string[]; readOnly?: boolean }>) {
  const state = usePropertySpectra(context?.target)
  const busy = state.listing?.jobs.some(job => ['queued', 'running'].includes(job.status)) || state.listing?.items.some(item => ['queued', 'running'].includes(item.run.status))
  useEffect(() => { if (!busy) return; const timer = window.setInterval(state.reload, 3000); return () => window.clearInterval(timer) }, [busy, state.reload])
  return <Spectra.Provider value={context ? { ...context, ...state, stateKeys, readOnly } : null}>{children}</Spectra.Provider>
}
export function PropertySpectrumState({ stateKey, summary, children }: PropsWithChildren<{ stateKey: string; summary: string }>) {
  return <Material.Provider value={{ stateKey, summary }}>{children}</Material.Provider>
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

function SpectrumSummary({ item, curves, dos, unassigned = false }: { item: PropertySpectrumItem; curves: PropertySpectrumCurve[]; dos?: boolean; unassigned?: boolean }) {
  const ctx = useContext(Spectra)!, material = useContext(Material)
  const navigate = useNavigate(), location = useLocation()
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const first = curves.find(curve => curve.kind === 'alpha2f') || curves[0]
  const open = async () => {
    if (busy) return
    setBusy(true); setError('')
    try {
      if (ctx.beforeNavigate && !(await ctx.beforeNavigate())) throw new Error('主表单尚未保存，请处理保存错误后重试。')
      const fresh = await loadPropertySpectra(ctx.target)
      const current = fresh.items.find(value => value.id === item.id && value.state_key === item.state_key)
      if (!current || first && !current.result.curves.some(value => value.id === first.id && value.kind === first.kind)) throw new Error('谱结果或材料归属已变化，请刷新后重新打开。')
      const returnTo = location.pathname + location.search + (unassigned ? '#spectra-unassigned' : '#material-state-' + encodeURIComponent(material.stateKey))
      navigate(spectrumDetailPath(ctx.target, current, returnTo, first), { state: { materialSummary: unassigned ? '归属待确认' : material.summary } })
    } catch (error: any) { setError(error.message || '无法打开谱详情') }
    finally { setBusy(false) }
  }
  const hasAlpha = curves.some(curve => curve.kind === 'alpha2f') || (!curves.length && item.result.calibration?.curves?.some((curve: { kind: string }) => curve.kind === 'alpha2f'))
  const statuses = [...new Set(curves.map(curve => item.review[curve.id]?.status || 'needs_review'))]
  const review = statuses.length === 1 ? spectrumNames[statuses[0]] || statuses[0] : '部分曲线待核对'
  const title = unassigned ? (curves.length ? [...new Set(curves.map(curve => spectrumNames[curve.kind]))].join(' / ') : '谱图候选 · 尚无数值曲线')
    : dos ? '声子态密度 DOS' : hasAlpha ? 'Eliashberg 谱函数 α²F(ω)' : '累计 λ（尚无 α²F 数值）'
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
        {unassigned && <Typography variant="caption" color="text.secondary">材料条件尚未确定，请先检查图注与归属。</Typography>}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, ml: 'auto' }}>
        <Typography variant="caption" color="text.secondary">{item.stale ? '条件已变化，需重新核对' : ['queued', 'running', 'failed', 'needs_review'].includes(item.run.status) ? spectrumNames[item.run.status] : review}</Typography>
        <Button variant="outlined" size="small" disabled={busy} endIcon={<OpenInNewIcon sx={{ fontSize: '14px !important' }} />} onClick={() => void open()}>{busy ? '正在打开…' : unassigned ? '核对归属' : dos ? '查看声子 DOS' : hasAlpha ? '查看 α²F' : '查看累计 λ'}</Button>
      </Box>
    </Box>
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
  </Box>
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
  return <Box id="spectra-unassigned" sx={{ mt: 3, pointerEvents: 'auto', '& .MuiButton-root': { display: 'inline-flex !important' } }}>
    <Typography variant="subtitle2" sx={{ mb: 1 }}>待确认归属 · {items.length} 组谱数据</Typography>
    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>未确认的谱不并入任何材料状态。</Typography>
    {items.map(item => <SpectrumSummary key={item.id} item={item} curves={item.result.curves} unassigned />)}
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
