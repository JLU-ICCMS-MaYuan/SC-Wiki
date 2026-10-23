import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
export type PropertySpectrumTarget = { target: 'upload' | 'paper' | 'revision'; target_id: string }
export interface PropertySpectrumPoint { frequency_thz: number; frequency_pixel?: number; amplitude_pixel?: number | null; observed_amplitude: number | null; reconstructed_amplitude: number | null; status: string; detection_mode?: string }
export interface PropertySpectrumCurve { id: string; kind: string; projection?: string | null; unit: string; points: PropertySpectrumPoint[]; frequency_direction?: 'x' | 'y'; roi?: number[]; axis_calibration?: { amplitude: { slope: number; intercept: number }; frequency: { slope: number; intercept: number } } }
export interface PropertySpectrumItem {
  id: string; version: number; state_key: string | null; stale: boolean
  recorded_at?: string; historical?: boolean; recorded_state_key?: string | null; recorded_caption?: string
  source: { source_name?: string; pdf_page?: number; panel_id?: string; size_px?: number[]; [key: string]: unknown }
  run: { id?: string; status: string; error_message?: string; algorithm_version?: string }
  review: Record<string, { status?: string; reason?: string; frequency_intervals_thz?: number[][] }>
  result: { curves: PropertySpectrumCurve[]; quality?: Record<string, any>; candidates?: Record<string, any>; calibration?: Record<string, any>; failures?: unknown[] }
}
export interface PropertySpectrumListing { items: PropertySpectrumItem[]; jobs: Array<{ id: string; status: string; error_message?: string }>; version: string; can_edit: boolean; can_review: boolean }
export const SPECTRUM_API = '/api/rag/spectra'
/** 无曲线且无可用标定的是提取记录，不能计作等待分配的谱。 */
export function hasSpectrumData(item: PropertySpectrumItem): boolean {
  return Boolean(item.result.curves.length || item.result.calibration?.curves?.length)
}
export const spectrumQuery = (target: PropertySpectrumTarget) => new URLSearchParams(target).toString()
export const spectrumNames: Record<string, string> = { phonon_dos: '声子 DOS', alpha2f: 'α²F 谱函数', cumulative_lambda: '累计 λ', needs_review: '待核对', accepted: '已采纳', accepted_limited: '限定频段采纳', excluded: '已排除', queued: '排队中', running: '解析中', succeeded: '解析完成', failed: '解析失败', observed: '原图观测', interpolated: '短缺口插值', baseline_inferred: '近轴推断', boundary_assumption: '边界假设', edge_continuation: '平台延续', missing: '缺失' }

export interface PropertySpectrumGroup {
  item: PropertySpectrumItem
  kind: 'phonon_dos' | 'alpha2f'
  curves: PropertySpectrumCurve[]
  history: PropertySpectrumItem[]
}

/** 当前表示最新有数据的展示版本，不表示科学采纳；其他来源/提取保留在历史。 */
export function spectrumGroups(items: PropertySpectrumItem[], stateKey: string): PropertySpectrumGroup[] {
  return (['phonon_dos', 'alpha2f'] as const).flatMap(kind => {
    const candidates = items.filter(item => item.state_key === stateKey).flatMap(item => {
      const curves = item.result.curves.filter(curve => kind === 'phonon_dos'
        ? curve.kind === kind : ['alpha2f', 'cumulative_lambda'].includes(curve.kind))
      const calibrated = item.result.calibration?.curves?.some((curve: { kind: string }) => kind === 'phonon_dos'
        ? curve.kind === kind : ['alpha2f', 'cumulative_lambda'].includes(curve.kind))
      return curves.length || calibrated ? [{ item, kind, curves }] : []
    }).sort((a, b) => Number(Boolean(b.curves.length)) - Number(Boolean(a.curves.length))
      || (b.item.recorded_at || '').localeCompare(a.item.recorded_at || '') || b.item.id.localeCompare(a.item.id))
    return candidates.length ? [{ ...candidates[0], history: candidates.slice(1).map(value => value.item) }] : []
  })
}

export function spectrumInterval(curves: PropertySpectrumCurve[]): string {
  let minimum = Infinity, maximum = -Infinity
  const primary = curves.some(curve => curve.kind === 'alpha2f') ? curves.filter(curve => curve.kind === 'alpha2f') : curves
  for (const curve of primary) for (const point of curve.points) {
    if (Number.isFinite(point.frequency_thz)) {
      minimum = Math.min(minimum, point.frequency_thz)
      maximum = Math.max(maximum, point.frequency_thz)
    }
  }
  return Number.isFinite(minimum) ? String(Number(minimum.toPrecision(5))) + '–' + Number(maximum.toPrecision(5)) + ' THz' : '频域未确定'
}

export function spectrumDetailPath(target: PropertySpectrumTarget, item: PropertySpectrumItem,
  returnTo: string, curve?: PropertySpectrumCurve, kind?: 'phonon_dos' | 'alpha2f'): string {
  const params = new URLSearchParams({ ...target, state_key: item.state_key || 'unassigned',
    collection_version: String(item.version), run: item.run.id || '', return: returnTo })
  if (curve) params.set('curve', curve.id)
  if (kind || curve) params.set('kind', kind || (curve?.kind === 'phonon_dos' ? 'phonon_dos' : 'alpha2f'))
  return '/spectra/' + encodeURIComponent(item.id) + '?' + params
}
export async function loadPropertySpectra(target: PropertySpectrumTarget, signal?: AbortSignal): Promise<PropertySpectrumListing> {
  const listing = await api.get<PropertySpectrumListing>(`${SPECTRUM_API}?${spectrumQuery(target)}`, { signal })
  if (!Array.isArray(listing?.items) || !Array.isArray(listing?.jobs)) throw new Error('谱服务返回结构无效')
  return listing
}
export function usePropertySpectra(target?: PropertySpectrumTarget) {
  const key = target ? spectrumQuery(target) : ''
  const [reloadKey, setReloadKey] = useState(0)
  const [state, setState] = useState<{ key: string; listing: PropertySpectrumListing | null; error: string; loading: boolean }>({ key: '', listing: null, error: '', loading: false })
  useEffect(() => {
    const controller = new AbortController()
    setState({ key, listing: null, error: '', loading: !!key })
    if (key) void loadPropertySpectra(Object.fromEntries(new URLSearchParams(key)) as PropertySpectrumTarget, controller.signal)
      .then(listing => { if (!controller.signal.aborted) setState({ key, listing, error: '', loading: false }) })
      .catch(error => { if (!controller.signal.aborted) setState({ key, listing: null, error: error.message || '谱服务不可用', loading: false }) })
    return () => controller.abort()
  }, [key, reloadKey])
  const reload = useCallback(() => setReloadKey(value => value + 1), [])
  const current = state.key === key ? state : { listing: null, error: '', loading: !!key }
  return { ...current, reload }
}
export function safeSpectrumReturn(value: string | null): string {
  return value && /^\/(?!\/)/.test(value) && !/[\\\u0000-\u001f]/.test(value) ? value : '/upload'
}
