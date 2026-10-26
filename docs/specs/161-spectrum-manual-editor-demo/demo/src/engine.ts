// 源像素是编辑事实；标定只负责换算，不重写原图或初始提取。
export type Axis = { pixels: [number, number]; values: [number, number]; unit: string }
export type Point = { id: string; x: number; y: number; segment: string; status: string }
export type Curve = { id: string; name: string; color: string; points: Point[] }
export type Rect = [number, number, number, number]
export type Document = {
  schemaVersion: 1; id: string; title: string; description: string
  source: { id: string; sha256: string; image: string; width: number; height: number; viewport: Rect; plot: Rect }
  calibration: { direction: 'x' | 'y'; frequency: Axis; amplitude: Axis; amplitudeEvidence: string }
  curves: Curve[]
  zero: { pixel: number; pointIds: string[] } | null
  operations: { kind: string; at: string; detail: string }[]
}
export type History = { past: Document[]; present: Document; future: Document[] }
export const clone = <T,>(value: T): T => structuredClone(value)
export const uid = () => crypto.randomUUID()
export function valueAt(axis: Axis, pixel: number) {
  return axis.values[0] + (pixel - axis.pixels[0]) * (axis.values[1] - axis.values[0]) / (axis.pixels[1] - axis.pixels[0])
}
export function pixelAt(axis: Axis, value: number) {
  return axis.pixels[0] + (value - axis.values[0]) * (axis.pixels[1] - axis.pixels[0]) / (axis.values[1] - axis.values[0])
}
export const frequencyPixel = (doc: Document, p: Point) => p[doc.calibration.direction]
export const amplitudePixel = (doc: Document, p: Point) => p[doc.calibration.direction === 'x' ? 'y' : 'x']
export const frequency = (doc: Document, p: Point) => valueAt(doc.calibration.frequency, frequencyPixel(doc, p))
export const amplitude = (doc: Document, p: Point) => valueAt(doc.calibration.amplitude, amplitudePixel(doc, p))
export const ordered = (doc: Document, points: Point[]) => [...points].sort((a, b) => frequency(doc, a) - frequency(doc, b))
export function frequencySpan(doc: Document) {
  const [x0, y0, x1, y1] = doc.source.plot
  const bounds = doc.calibration.direction === 'x' ? [x0, x1] : [y0, y1]
  return Math.abs(valueAt(doc.calibration.frequency, bounds[1]) - valueAt(doc.calibration.frequency, bounds[0]))
}
export function axisValid(axis: Axis) {
  return [axis.pixels, axis.values].every(v => Array.isArray(v) && v.length === 2 && v.every(Number.isFinite) && Math.abs(v[1] - v[0]) > 1e-9)
}
export function record(doc: Document, kind: string, detail: string): Document {
  return { ...doc, operations: [...doc.operations, { kind, detail, at: new Date().toISOString() }] }
}
export function commit(history: History, doc: Document): History {
  if (JSON.stringify(history.present) === JSON.stringify(doc)) return history
  return { past: [...history.past, history.present], present: doc, future: [] }
}
export function undo(h: History): History {
  return h.past.length ? { past: h.past.slice(0, -1), present: h.past.at(-1)!, future: [h.present, ...h.future] } : h
}
export function redo(h: History): History {
  return h.future.length ? { past: [...h.past, h.present], present: h.future[0], future: h.future.slice(1) } : h
}
export function weight(doc: Document, center: Point, point: Point, radius: number, linked: boolean) {
  if (center.id === point.id) return 1
  if (!linked || point.segment !== center.segment || radius <= 0) return 0
  const d = Math.abs(frequency(doc, point) - frequency(doc, center)) / radius
  return d >= 1 ? 0 : (1 - d * d) ** 2
}

// 全部点共享同一缩放因子，遇到边界/顺序约束时整体停止，避免局部截断拉坏形状。
export function move(doc: Document, curveId: string, pointId: string, dx: number, dy: number, radius: number, linked: boolean, mode: 'amplitude' | 'free'): Document {
  const curve = doc.curves.find(c => c.id === curveId), center = curve?.points.find(p => p.id === pointId)
  if (!curve || !center || ![dx, dy, radius].every(Number.isFinite)) return doc
  if (mode === 'amplitude') { if (doc.calibration.direction === 'x') dx = 0; else dy = 0 }
  const points = ordered(doc, curve.points), weights = points.map(p => weight(doc, center, p, radius, linked))
  const [x0, y0, x1, y1] = doc.source.plot
  let factor = 1
  const limit = (value: number, delta: number, low: number, high: number) => {
    if (delta > 0) factor = Math.min(factor, (high - value) / delta)
    if (delta < 0) factor = Math.min(factor, (low - value) / delta)
  }
  points.forEach((p, i) => { limit(p.x, dx * weights[i], x0, x1); limit(p.y, dy * weights[i], y0, y1) })
  const fdelta = valueAt(doc.calibration.frequency, doc.calibration.frequency.pixels[0] + (doc.calibration.direction === 'x' ? dx : dy)) - doc.calibration.frequency.values[0]
  for (let i = 1; i < points.length; i++) {
    const gap = frequency(doc, points[i]) - frequency(doc, points[i - 1])
    const change = fdelta * (weights[i] - weights[i - 1])
    if (change < 0) factor = Math.min(factor, (gap - Math.min(1e-6, gap / 2)) / -change)
  }
  factor = Math.max(0, factor)
  if (Math.abs(dx * factor) + Math.abs(dy * factor) < 1e-10) return doc
  const moved = points.map((p, i) => weights[i] ? { ...p, x: p.x + dx * weights[i] * factor, y: p.y + dy * weights[i] * factor, status: '人工调整' } : p)
  return { ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points: moved } : c) }
}
export function removePoints(doc: Document, curveId: string, ids: string[]): Document {
  const selected = new Set(ids), curve = doc.curves.find(c => c.id === curveId)
  if (!curve || !curve.points.some(p => selected.has(p.id))) return doc
  let previousSegment: string | null = null, nextSegment = '', interrupted = true
  const points: Point[] = []
  for (const p of ordered(doc, curve.points)) {
    if (selected.has(p.id)) { interrupted = true; continue }
    if (interrupted || previousSegment !== p.segment) nextSegment = uid()
    points.push({ ...p, segment: nextSegment }); previousSegment = p.segment; interrupted = false
  }
  return record({ ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points } : c), zero: doc.zero ? { ...doc.zero, pointIds: doc.zero.pointIds.filter(id => !selected.has(id)) } : null }, 'delete', `删除 ${ids.length} 个选中点，保留缺口`)
}
export function addPoint(doc: Document, curveId: string, x: number, y: number, zero = false): Document {
  const curve = doc.curves.find(c => c.id === curveId)
  if (!curve) throw new Error('请先选择一条曲线')
  const [x0, y0, x1, y1] = doc.source.plot
  if (![x, y].every(Number.isFinite) || x < x0 || x > x1 || y < y0 || y > y1) throw new Error('请在图框内选点')
  if (zero) {
    if (!doc.zero) throw new Error('请先标记原图的真实零频位置')
    const at = doc.calibration.direction === 'x' ? x : y
    if (Math.abs(at - doc.zero.pixel) > 3) throw new Error('请在已标记的零频线上点选曲线；幅值来自你的点击位置')
    if (doc.calibration.direction === 'x') x = doc.zero.pixel; else y = doc.zero.pixel
  }
  const p: Point = { id: uid(), x, y, segment: uid(), status: zero ? '人工零频选点' : '人工补选' }
  const f = frequency(doc, p), points = ordered(doc, curve.points)
  const existing = points.find(v => Math.abs(frequency(doc, v) - f) < 1e-6)
  if (existing && !zero) throw new Error('该频率已有点，请选中后调整坐标')
  if (existing) { p.id = existing.id; p.segment = existing.segment }
  else {
    const i = points.findIndex(v => frequency(doc, v) > f)
    if (i > 0 && points[i - 1].segment === points[i].segment) p.segment = points[i].segment
  }
  const result = ordered(doc, [...points.filter(v => v.id !== p.id), p])
  return record({ ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points: result } : c), zero: zero && doc.zero ? { ...doc.zero, pointIds: [...new Set([...doc.zero.pointIds, p.id])] } : doc.zero }, zero ? 'zero-point' : 'add', `${curve.name}：在源像素 (${x.toFixed(2)}, ${y.toFixed(2)}) 选点`)
}
export function markZero(doc: Document, x: number, y: number): Document {
  const pixel = doc.calibration.direction === 'x' ? x : y
  const [x0, y0, x1, y1] = doc.source.plot
  if (x < x0 || x > x1 || y < y0 || y > y1) throw new Error('零频位置必须在原图图框内')
  const axis = doc.calibration.frequency, offset = valueAt(axis, pixel)
  return record({ ...doc, calibration: { ...doc.calibration, frequency: { ...axis, values: [axis.values[0] - offset, axis.values[1] - offset] } }, zero: { pixel, pointIds: [] } }, 'zero-line', '人工标记原图零频位置，仍需补选当前曲线零频点')
}
export function zeroCovered(doc: Document, curveId: string) {
  return Boolean(doc.zero && doc.curves.find(c => c.id === curveId)?.points.some(p => doc.zero!.pointIds.includes(p.id) && Math.abs(frequency(doc, p)) < 1e-6))
}
export function curvePath(doc: Document, curve: Curve) {
  let previous = ''
  return ordered(doc, curve.points).map(p => {
    const command = previous === p.segment ? 'L' : 'M'; previous = p.segment
    return `${command}${p.x},${p.y}`
  }).join(' ')
}
export function validateDocument(value: unknown, initial: Document): asserts value is Document {
  const d = value as Document
  try {
    if (!d || d.schemaVersion !== 1 || d.id !== initial.id || JSON.stringify(d.source) !== JSON.stringify(initial.source)) throw Error()
    if (!['x', 'y'].includes(d.calibration.direction) || !axisValid(d.calibration.frequency) || !axisValid(d.calibration.amplitude)) throw Error()
    if (typeof d.calibration.amplitudeEvidence !== 'string' || !['THz', 'cm-1', 'meV'].includes(d.calibration.frequency.unit) || typeof d.calibration.amplitude.unit !== 'string') throw Error()
    if (d.curves.length !== initial.curves.length || !Array.isArray(d.operations) || !d.operations.every(o => typeof o.kind === 'string' && typeof o.at === 'string' && typeof o.detail === 'string')) throw Error()
    const ids = new Set<string>(), curveIds = new Set<string>(), [x0, y0, x1, y1] = d.source.plot
    for (const c of d.curves) {
      const source = initial.curves.find(v => v.id === c.id)
      if (!source || curveIds.has(c.id) || c.name !== source.name || c.color !== source.color) throw Error()
      curveIds.add(c.id)
      for (const p of c.points) {
        if (!p.id || ids.has(p.id) || !p.segment || typeof p.status !== 'string' || ![p.x, p.y].every(Number.isFinite) || p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) throw Error()
        ids.add(p.id)
      }
      const sorted = ordered(d, c.points)
      if (sorted.some((p, i) => i > 0 && frequency(d, p) - frequency(d, sorted[i - 1]) < 1e-9)) throw Error()
    }
    if (d.zero && (!Number.isFinite(d.zero.pixel) || Math.abs(valueAt(d.calibration.frequency, d.zero.pixel)) > 1e-6 || !Array.isArray(d.zero.pointIds) || !d.zero.pointIds.every(id => ids.has(id)))) throw Error()
  } catch { throw new Error('草稿格式、来源或坐标无效，未覆盖已有数据。可恢复原始示例后再保存。') }
}
