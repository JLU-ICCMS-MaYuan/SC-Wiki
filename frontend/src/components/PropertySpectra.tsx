import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react'
import { Alert, Box, Button, Typography } from '@mui/material'
import { useLocation, useNavigate } from 'react-router-dom'
import { loadPropertySpectra, spectrumNames, usePropertySpectra, type PropertySpectrumTarget, type PropertySpectrumItem, type PropertySpectrumCurve } from '../lib/propertySpectra'
import type { PropertyModuleCode } from '../lib/propertyModules'

export interface PropertySpectraContext { target: PropertySpectrumTarget; beforeNavigate?: () => Promise<boolean> }
const Spectra = createContext<(PropertySpectraContext & ReturnType<typeof usePropertySpectra>) | null>(null)
const Material = createContext({ stateKey: '', summary: '' })
export function PropertySpectraProvider({ context, children }: PropsWithChildren<{ context?: PropertySpectraContext }>) {
  const state = usePropertySpectra(context?.target)
  const busy = state.listing?.jobs.some(job => ['queued', 'running'].includes(job.status)) || state.listing?.items.some(item => ['queued', 'running'].includes(item.run.status))
  useEffect(() => { if (!busy) return; const timer = window.setInterval(state.reload, 3000); return () => window.clearInterval(timer) }, [busy, state.reload])
  return <Spectra.Provider value={context ? { ...context, ...state } : null}>{children}</Spectra.Provider>
}
export function PropertySpectrumState({ stateKey, summary, children }: PropsWithChildren<{ stateKey: string; summary: string }>) {
  return <Material.Provider value={{ stateKey, summary }}>{children}</Material.Provider>
}
export function PropertySpectrumSection({ moduleCode }: { moduleCode: PropertyModuleCode }) {
  const ctx = useContext(Spectra), material = useContext(Material)
  if (!ctx || !['dynamical_properties', 'superconductive_properties'].includes(moduleCode)) return null
  const kinds = moduleCode === 'dynamical_properties' ? ['phonon_dos'] : ['alpha2f', 'cumulative_lambda']
  const curves = (ctx.listing?.items || []).filter(item => item.state_key === material.stateKey)
    .flatMap(item => (item.result.curves || []).filter(curve => kinds.includes(curve.kind)).map(curve => ({ item, curve })))
  return <Box sx={{ minWidth: 0, my: 1, pointerEvents: 'auto', '& .MuiButton-root': { display: 'inline-flex !important' } }}>
    {ctx.loading && <Typography variant="caption" role="status">正在读取谱解析结果…</Typography>}
    {ctx.error && <Alert severity="warning">谱解析结果暂不可读取：{ctx.error} <Button size="small" onClick={ctx.reload}>重试</Button></Alert>}
    {ctx.listing && !curves.length && <Typography variant="caption" color="text.secondary">暂无{moduleCode === 'dynamical_properties' ? '声子 DOS' : 'α²F'}解析结果</Typography>}
    {curves.map(({ item, curve }) => <SpectrumSummary key={`${item.id}:${curve.id}`} item={item} curve={curve} />)}
  </Box>
}
function SpectrumSummary({ item, curve }: { item: PropertySpectrumItem; curve: PropertySpectrumCurve }) {
  const ctx = useContext(Spectra)!, material = useContext(Material)
  const navigate = useNavigate(), location = useLocation()
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const frequencies = curve.points.map(point => point.frequency_thz).filter(Number.isFinite)
  const interval = frequencies.length ? `${Math.min(...frequencies)}–${Math.max(...frequencies)} THz` : '频域未确定'
  const open = async () => {
    if (busy) return
    setBusy(true); setError('')
    try {
      if (ctx.beforeNavigate && !(await ctx.beforeNavigate())) throw new Error('主表单尚未保存，请处理保存错误后重试。')
      const fresh = await loadPropertySpectra(ctx.target)
      const current = fresh.items.find(value => value.id === item.id && value.state_key === material.stateKey)
      if (!current || !current.result.curves.some(value => value.id === curve.id)) throw new Error('谱结果已变化，请刷新后重新打开。')
      const params = new URLSearchParams({ ...ctx.target, state_key: material.stateKey, curve: curve.id, collection_version: String(current.version), run: current.run.id || '', return: `${location.pathname}${location.search}#material-state-${encodeURIComponent(material.stateKey)}` })
      navigate(`/spectra/${encodeURIComponent(item.id)}?${params}`, { state: { materialSummary: material.summary, targetVersion: fresh.version } })
    } catch (error: any) { setError(error.message || '无法打开谱详情') }
    finally { setBusy(false) }
  }
  return <Box sx={{ bgcolor: '#F4F3FF', borderRadius: 1.5, px: 1.5, py: 1, mb: 1 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="body2" fontWeight={600}>{spectrumNames[curve.kind]} {curve.projection || ''}</Typography>
      <Typography variant="caption">{item.source.source_name || '来源未命名'} · 第 {item.source.pdf_page ?? '未知'} 页 · {interval}</Typography>
      <Typography variant="caption">{spectrumNames[item.run.status] || item.run.status} · {item.stale ? '条件已变化，旧采纳失效' : spectrumNames[item.review[curve.id]?.status || 'needs_review']}</Typography>
      <Button size="small" disabled={busy} onClick={() => void open()}>{busy ? '正在保存…' : '查看详情'}</Button>
    </Box>
    {error && <Alert severity="error">{error}</Alert>}
  </Box>
}

/** 谱可能先于标量记录产生；显示归属模块，不为此伪造持久化记录。 */
export function MissingPropertySpectrumModules({ existing }: { existing: PropertyModuleCode[] }) {
  const ctx = useContext(Spectra), material = useContext(Material)
  const kinds = (ctx?.listing?.items || []).filter(item => item.state_key === material.stateKey).flatMap(item => item.result.curves.map(curve => curve.kind))
  const modules: Array<{ code: PropertyModuleCode; label: string; kinds: string[] }> = [
    { code: 'dynamical_properties', label: '动力学性质', kinds: ['phonon_dos'] },
    { code: 'superconductive_properties', label: '超导性质', kinds: ['alpha2f', 'cumulative_lambda'] },
  ]
  return <>{modules.filter(module => !existing.includes(module.code) && module.kinds.some(kind => kinds.includes(kind))).map(module => <Box key={module.code} data-testid={`property-module-${module.code}`} sx={{ borderTop: 1, borderColor: 'divider', pt: 1.5 }}><Typography variant="subtitle2" fontWeight={700}>{module.label}</Typography><PropertySpectrumSection moduleCode={module.code} /></Box>)}</>
}
