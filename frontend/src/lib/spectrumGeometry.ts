import type { PropertySpectrumCurve as Curve } from './propertySpectra'

export type SpectrumRect = [number, number, number, number]
export interface SpectrumGeometry { plot: SpectrumRect; crop: SpectrumRect; method: 'frame' | 'calibration' | 'roi' }
export const spectrumCurveColor = (curve: Curve, index: number) => curve.kind === 'alpha2f' ? '#e11d48'
  : ({ La: '#6155d9', Sc: '#d25693', H: '#168b68' } as Record<string, string>)[curve.projection || ''] || ['#6155d9', '#d25693', '#168b68'][index % 3]
const validRect = (r: unknown, width: number, height: number): r is SpectrumRect => Array.isArray(r) && r.length === 4 && r.every(Number.isFinite)
  && r[0] >= 0 && r[1] >= 0 && r[2] < width && r[3] < height && r[2] > r[0] && r[3] > r[1]
const union = (rects: SpectrumRect[]): SpectrumRect => [Math.min(...rects.map(r => r[0])), Math.min(...rects.map(r => r[1])), Math.max(...rects.map(r => r[2])), Math.max(...rects.map(r => r[3]))]

/** 只在已有曲线 ROI 邻域寻找包围它的灰黑长直边；不猜材料、压力或谱种类。 */
export function spectrumGeometry(curves: Curve[], width: number, height: number, pixels?: Uint8ClampedArray): SpectrumGeometry | null {
  if (!curves.length || !curves.every(c => validRect(c.roi, width, height))) return null
  const seed = union(curves.map(c => c.roi as SpectrumRect))
  let plot = seed, method: SpectrumGeometry['method'] = 'roi'
  if (pixels && pixels.length === width * height * 4) {
    const dark = (x: number, y: number) => {
      const at = (y * width + x) * 4, r = pixels[at], g = pixels[at + 1], b = pixels[at + 2]
      return pixels[at + 3] > 128 && Math.max(r, g, b) - Math.min(r, g, b) < 35 && (r + g + b) / 3 < 160
    }
    const edge = (start: number, step: number, distance: number, horizontal: boolean, low: number, high: number) => {
      for (let at = Math.round(start), count = 0; count <= distance && at >= 0 && at < (horizontal ? height : width); at += step, count++) {
        let black = 0
        for (let p = Math.ceil(low); p <= Math.floor(high); p++) if (horizontal ? dark(p, at) : dark(at, p)) black++
        if (black / (Math.floor(high) - Math.ceil(low) + 1) >= 0.7) return at
      }
      return null
    }
    const reachY = Math.max(12, Math.ceil((seed[3] - seed[1]) * .25)), reachX = Math.max(8, Math.ceil((seed[2] - seed[0]) * .15))
    const top = edge(seed[1], -1, reachY, true, seed[0], seed[2]), bottom = edge(seed[3], 1, reachY, true, seed[0], seed[2])
    if (top != null && bottom != null) {
      const left = edge(seed[0], -1, reachX, false, top, bottom), right = edge(seed[2], 1, reachX, false, top, bottom)
      if (left != null && right != null && right > left && bottom > top) { plot = [left, top, right, bottom]; method = 'frame' }
    }
  }
  // 旧数据只保留窄边距与下方刻度；不能因补齐共用频率轴而吞入隔壁 DOS 或声子色散。
  const footer = Math.min(24, Math.max(12, (plot[3] - plot[1]) * .06))
  let crop: SpectrumRect = [Math.max(0, plot[0] - 4), Math.max(0, plot[1] - 4), Math.min(width - 1, plot[2] + 8), Math.min(height - 1, plot[3] + footer)]
  const proposed = curves.map(c => c.display_bbox).filter((r): r is SpectrumRect => validRect(r, width, height))
  if (proposed.length === curves.length) {
    const box = union(proposed), pw = plot[2] - plot[0], ph = plot[3] - plot[1]
    // 显示框必须包住图框，且不得跨入整行/整页；模型坐标只是候选，不直接信任。
    if (box[0] <= plot[0] && box[1] <= plot[1] && box[2] >= plot[2] && box[3] >= plot[3]
      && plot[0] - box[0] <= Math.max(12, pw * .2) && box[2] - plot[2] <= Math.max(12, pw * .2)
      && plot[1] - box[1] <= Math.max(16, ph * .15) && box[3] - plot[3] <= Math.max(24, ph * .15)) {
      crop = box; if (method !== 'frame') method = 'calibration'
    }
  }
  return { plot, crop, method }
}

/** 原图、独立数据与叠加均留在同一源像素坐标系，裁切不重写科学数据。 */
export function spectrumPixelPath(curve: Curve): string {
  const axis = curve.axis_calibration?.amplitude
  if (!axis || !Number.isFinite(axis.slope) || axis.slope === 0 || !curve.frequency_direction) return ''
  let path = '', open = false
  for (const p of curve.points) {
    if (p.reconstructed_amplitude == null || p.frequency_pixel == null || !Number.isFinite(p.reconstructed_amplitude) || !Number.isFinite(p.frequency_pixel)) { open = false; continue }
    const amp = (p.reconstructed_amplitude - axis.intercept) / axis.slope
    const [x, y] = curve.frequency_direction === 'y' ? [amp, p.frequency_pixel] : [p.frequency_pixel, amp]
    if (!Number.isFinite(x) || !Number.isFinite(y)) { open = false; continue }
    path += `${open ? 'L' : 'M'}${x},${y} `; open = true
  }
  return path
}
