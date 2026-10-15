import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
export type PropertySpectrumTarget = { target: 'upload' | 'paper' | 'revision'; target_id: string }
export interface PropertySpectrumPoint { frequency_thz: number; observed_amplitude: number | null; reconstructed_amplitude: number | null; status: string; detection_mode?: string }
export interface PropertySpectrumCurve { id: string; kind: string; projection?: string | null; unit: string; points: PropertySpectrumPoint[] }
export interface PropertySpectrumItem {
  id: string; version: number; state_key: string | null; stale: boolean
  source: { source_name?: string; pdf_page?: number; panel_id?: string; size_px?: number[]; [key: string]: unknown }
  run: { id?: string; status: string; error_message?: string; algorithm_version?: string }
  review: Record<string, { status?: string; reason?: string; frequency_intervals_thz?: number[][] }>
  result: { curves: PropertySpectrumCurve[]; quality?: Record<string, unknown>; candidates?: Record<string, any>; calibration?: Record<string, unknown>; failures?: unknown[] }
}
export interface PropertySpectrumListing { items: PropertySpectrumItem[]; jobs: Array<{ id: string; status: string }>; version: string; can_edit: boolean; can_review: boolean }
export const SPECTRUM_API = '/api/rag/spectra'
export const spectrumQuery = (target: PropertySpectrumTarget) => new URLSearchParams(target).toString()
export const spectrumNames: Record<string, string> = { phonon_dos: '声子 DOS', alpha2f: 'α²F 谱函数', cumulative_lambda: '累计 λ', needs_review: '待核对', accepted: '已采纳', accepted_limited: '限定频段采纳', excluded: '已排除', queued: '排队中', running: '解析中', succeeded: '解析完成', failed: '解析失败', observed: '原图观测', interpolated: '短缺口插值', baseline_inferred: '近轴推断', boundary_assumption: '边界假设', edge_continuation: '平台延续', missing: '缺失' }
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
