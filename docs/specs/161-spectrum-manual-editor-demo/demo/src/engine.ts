import { createInfluenceKernel, DRAG_INFLUENCE } from './dragInfluence'

// 源像素是编辑事实；标定只负责换算，不重写原图或初始提取。
export type Axis = { pixels: [number, number]; values: [number, number]; unit: string }
export type Point = { id: string; x: number; y: number; segment: string; status: string; manual?: boolean; breakBefore?: boolean; connectTo?: string }
export type Curve = { id: string; name: string; color: string; points: Point[]; pathOrdered?: boolean }
export type Rect = [number, number, number, number]
export type Document = {
  recognizedAxes?: {sourceId:string;sourceSha256:string;direction:"x"|"y";frequencyUnit:string;frequencyTicks:number[][];lambdaTicks:number[][]}
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
const orderCache = new WeakMap<Point[], { axis: Axis; direction: string; points: Point[] }>()
export function ordered(doc: Document, points: Point[]) {
  const cached = orderCache.get(points)
  if (cached?.axis === doc.calibration.frequency && cached.direction === doc.calibration.direction) return cached.points
  const sorted = [...points].sort((a, b) => frequency(doc, a) - frequency(doc, b))
  orderCache.set(points, { axis: doc.calibration.frequency, direction: doc.calibration.direction, points: sorted })
  return sorted
}
/** 连线只检查频率相邻边；删除断口优先于人工点自动连接。 */
export const connected = (left: Point, right: Point) => right.connectTo !== undefined ? right.connectTo === left.id : right.breakBefore !== undefined ? !right.breakBefore
  : left.segment === right.segment || left.manual === true || right.manual === true
export const tracePoints = (doc: Document, curve: Curve) => curve.pathOrdered ? curve.points : ordered(doc, curve.points)
function freezeTrace(doc: Document, curve: Curve): Point[] {
  if (curve.pathOrdered) return curve.points
  const points = ordered(doc, curve.points)
  return points.map((p, i) => ({ ...p, breakBefore: i === 0 || !connected(points[i - 1], p) }))
}
/** 兼容旧草稿；拖动会改写 status，因此以不可变初始样本的稳定 ID 识别补点。 */
export function restoreManualMarkers(doc: Document, initial: Document): Document {
  return { ...doc, curves: doc.curves.map(c => {
    const original = new Set(initial.curves.find(v => v.id === c.id)!.points.map(p => p.id))
    const marked = { ...c, points: c.points.map(p => !original.has(p.id) && p.manual === undefined ? { ...p, manual: true } : p) }
    return { ...marked, points: freezeTrace(doc, marked), pathOrdered: true }
  }) }
}
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
// 主要影响区与指数尾部均从独立调参文件读取。
const kernel = createInfluenceKernel(DRAG_INFLUENCE)
export const neighborWeight = (distance: number) => kernel[distance] ?? 0
export type PreparedMove = { doc: Document; curveId: string; points: Point[]; weights: number[]; byId: Map<string, number> }
export function prepareMove(doc: Document, curveId: string, pointId: string, linked: boolean): PreparedMove | null {
  const curve = doc.curves.find(c => c.id === curveId)
  if (!curve) return null
  const points = freezeTrace(doc, curve), index = points.findIndex(p => p.id === pointId)
  if (index < 0) return null
  const weights = points.map(() => 0), byId = new Map<string, number>([[pointId, 1]])
  weights[index] = 1
  if (linked) {
    const indexById=new Map(points.map((p,i)=>[p.id,i])), neighbors=points.map(()=>[] as number[])
    points.forEach((p,i)=>{
      const parent=p.connectTo ? indexById.get(p.connectTo) : i>0&&connected(points[i-1],p)?i-1:undefined
      if(parent!==undefined){neighbors[i].push(parent);neighbors[parent].push(i)}
    })
    // 沿明确描线前进，遇分叉停止扩散，避免带动未选择的分支。
    if(neighbors[index].length<=2) for(const start of neighbors[index]) {
      let previous=index,at=start
      for(let d=1;d<kernel.length;d++) {
        weights[at]=kernel[d];byId.set(points[at].id,kernel[d])
        if(neighbors[at].length!==2)break
        const next=neighbors[at].find(i=>i!==previous)!
        previous=at;at=next
      }
    }
  }
  return { doc, curveId, points, weights, byId }
}
export function move(doc: Document, curveId: string, pointId: string, dx: number, dy: number, linked: boolean, mode: 'amplitude' | 'free'): Document {
  const prepared = prepareMove(doc, curveId, pointId, linked)
  return prepared ? movePrepared(prepared, dx, dy, mode) : doc
}
// 全部点共享限位因子；每次拖动复用起点排序和权重，不逐帧重新查找邻点。
export function movePrepared(prepared: PreparedMove, dx: number, dy: number, mode: 'amplitude' | 'free'): Document {
  const { doc, curveId, points, weights } = prepared
  if (![dx, dy].every(Number.isFinite)) return doc
  if (mode === 'amplitude') { if (doc.calibration.direction === 'x') dx = 0; else dy = 0 }
  const [x0, y0, x1, y1] = doc.source.plot
  let factor = 1
  const limit = (value: number, delta: number, low: number, high: number) => {
    if (delta > 0) factor = Math.min(factor, (high - value) / delta)
    if (delta < 0) factor = Math.min(factor, (low - value) / delta)
  }
  points.forEach((p, i) => { limit(p.x, dx * weights[i], x0, x1); limit(p.y, dy * weights[i], y0, y1) })
  factor = Math.max(0, factor)
  if (Math.abs(dx * factor) + Math.abs(dy * factor) < 1e-10) return doc
  const moved = points.map((p, i) => weights[i] ? { ...p, x: p.x + dx * weights[i] * factor, y: p.y + dy * weights[i] * factor, status: '人工调整' } : p)
  return { ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points: moved, pathOrdered: true } : c) }
}
export function removePoints(doc: Document, curveId: string, ids: string[]): Document {
  const selected = new Set(ids), curve = doc.curves.find(c => c.id === curveId)
  if (!curve || !curve.points.some(p => selected.has(p.id))) return doc
  const original = freezeTrace(doc, curve), points: Point[] = []
  let interrupted = true
  for (const p of original) {
    if (selected.has(p.id)) { interrupted = true; continue }
    if(p.connectTo && selected.has(p.connectTo)) {
      const {connectTo,...rest}=p;points.push({...rest,breakBefore:true})
    } else points.push({ ...p, breakBefore: interrupted || p.breakBefore === true })
    interrupted = false
  }
  return record({ ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points, pathOrdered: true } : c), zero: doc.zero ? { ...doc.zero, pointIds: doc.zero.pointIds.filter(id => !selected.has(id)) } : null }, 'delete', `删除 ${ids.length} 个选中点，保留缺口`)
}
/** 只在点击时线性检查已有边/开放端点；不按频率重排、不改变点击坐标。 */
function insertOnTrace(points: Point[], point: Point): Point[] {
  if (!points.length) return [{ ...point, breakBefore: true }]
  let best = Infinity, index = 0, start = true, joinNext = false
  const consider = (distance: number, at: number, starts: boolean, joins = false) => {
    if (distance < best) { best = distance; index = at; start = starts; joinNext = joins }
  }
  for (let i = 0; i < points.length; i++) {
    const p = points[i], next = points[i + 1], distance = (point.x - p.x) ** 2 + (point.y - p.y) ** 2
    if (i === 0 || !connected(points[i - 1], p)) consider(distance, i, true)
    if (!next || !connected(p, next)) consider(distance, i + 1, false)
    if (next) {
      const dx = next.x - p.x, dy = next.y - p.y, length = dx * dx + dy * dy
      const t = length ? ((point.x - p.x) * dx + (point.y - p.y) * dy) / length : -1
      if (t > 0 && t < 1) consider((point.x - p.x - t * dx) ** 2 + (point.y - p.y - t * dy) ** 2, i + 1, false, true)
    }
  }
  const result = [...points.slice(0, index), { ...point, breakBefore: start }, ...points.slice(index)]
  if ((start || joinNext) && index + 1 < result.length) result[index + 1] = { ...result[index + 1], breakBefore: false }
  return result
}
export function reconnectManualPoints(doc: Document, curveId: string): Document {
  const curve = doc.curves.find(c => c.id === curveId)
  if (!curve || !curve.points.some(p => p.manual)) return doc
  const points = [...freezeTrace(doc, curve)]
  const distance = (a: Point | undefined, b: Point | undefined) => a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0
  let swaps = 0
  // 只交换近乎同一频率像素的相邻人工点，避免整段重建跨过窄峰。
  // 固定两遍 O(n)；原图像素、原有点的相对顺序以及所有断口均保留。
  for (let pass = 0; pass < 2; pass++) for (let i = 0; i + 1 < points.length; i++) {
    const before = points[i - 1], left = points[i], right = points[i + 1], after = points[i + 2]
    if (before?.connectTo || left.connectTo || right.connectTo || after?.connectTo || !(left.manual || right.manual) || !connected(left, right)) continue
    if (Math.abs(frequencyPixel(doc, left) - frequencyPixel(doc, right)) > .5) continue
    const previous = before && connected(before, left) ? before : undefined
    const next = after && connected(right, after) ? after : undefined
    const current = distance(previous, left) + distance(left, right) + distance(right, next)
    const reversed = distance(previous, right) + distance(right, left) + distance(left, next)
    if (reversed + 1e-6 >= current) continue
    points[i] = { ...right, breakBefore: left.breakBefore }
    points[i + 1] = { ...left, breakBefore: false }
    swaps++
  }
  return swaps ? record({ ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points, pathOrdered: true } : c) }, 'reconnect', `调整 ${swaps} 对局部相邻连线，保留全部坐标和断口`) : doc

}

// SVG 逆变换在边框处会产生约1e-5像素的指针/矩阵舍入误差，只容忍数值噪声，不吸附真实图外点击。
function clickInPlot(doc: Document, x: number, y: number): [number, number] {
  const [x0,y0,x1,y1] = doc.source.plot, epsilon = 1e-4
  if (![x,y].every(Number.isFinite) || x < x0-epsilon || x > x1+epsilon || y < y0-epsilon || y > y1+epsilon) throw new Error('请在原图图框内选点')
  return [Math.max(x0,Math.min(x1,x)), Math.max(y0,Math.min(y1,y))]
}
export function addPoint(doc: Document, curveId: string, x: number, y: number, zero = false): Document {
  const curve = doc.curves.find(c => c.id === curveId)
  if (!curve) throw new Error('请先选择一条曲线')
  ;[x,y] = clickInPlot(doc,x,y)
  if (zero) {
    if (!doc.zero) throw new Error('请先标记原图的真实零频位置')
    const at = doc.calibration.direction === 'x' ? x : y
    if (Math.abs(at - doc.zero.pixel) > 3) throw new Error('请在已标记的零频线上点选曲线；幅值来自你的点击位置')
    if (doc.calibration.direction === 'x') x = doc.zero.pixel; else y = doc.zero.pixel
  }
  const p: Point = { id: uid(), x, y, segment: uid(), manual: true, status: zero ? '人工零频选点' : '人工补选' }
  const points = freezeTrace(doc, curve)
  const existing = zero ? points.find(v => Math.abs(frequency(doc, v) - frequency(doc, p)) < 1e-6) : undefined
  if (!zero && points.some(v => Math.hypot(v.x - x, v.y - y) < 1e-8)) throw new Error('该位置已有点，请选中后调整坐标')
  let result: Point[]
  if (existing) {
    p.id = existing.id; p.segment = existing.segment; p.breakBefore = existing.breakBefore
    result = points.map(v => v.id === p.id ? p : v)
  } else result = insertOnTrace(points, p)
  return record({ ...doc, curves: doc.curves.map(c => c.id === curveId ? { ...c, points: result, pathOrdered: true } : c), zero: zero && doc.zero ? { ...doc.zero, pointIds: [...new Set([...doc.zero.pointIds, p.id])] } : doc.zero }, zero ? 'zero-point' : 'add', `${curve.name}：在源像素 (${x.toFixed(2)}, ${y.toFixed(2)}) 选点`)
}
/** 普通连续描线只连接明确的前驱，旧点和旧连线不变。 */
export function appendPoint(doc: Document, curveId: string, anchorId: string, x: number, y: number): Document {
  const curve=doc.curves.find(c=>c.id===curveId),anchor=curve?.points.find(p=>p.id===anchorId)
  if(!curve || !anchor)throw new Error('请先选中当前曲线的一个已有点，再增加点。')
  ;[x,y]=clickInPlot(doc,x,y)
  if(curve.points.some(p=>Math.hypot(p.x-x,p.y-y)<1e-8))throw new Error('该位置已有点，请换一个位置；不会自动连接其他点。')
  const point:Point={id:uid(),x,y,segment:uid(),status:'人工连续描线',manual:true,breakBefore:true,connectTo:anchor.id}
  const points=[...freezeTrace(doc,curve),point]
  return record({...doc,curves:doc.curves.map(c=>c.id===curveId?{...c,points,pathOrdered:true}:c)},'add-chain','从点 '+anchor.id+' 连接到新点 '+point.id)
}
export function markZero(doc: Document, x: number, y: number): Document {
  ;[x,y] = clickInPlot(doc,x,y)
  const pixel = doc.calibration.direction === 'x' ? x : y
  const axis = doc.calibration.frequency, offset = valueAt(axis, pixel)
  return record({ ...doc, calibration: { ...doc.calibration, frequency: { ...axis, values: [axis.values[0] - offset, axis.values[1] - offset] } }, zero: { pixel, pointIds: [] } }, 'zero-line', '人工标记原图零频位置，仍需补选当前曲线零频点')
}
export function zeroCovered(doc: Document, curveId: string) {
  return Boolean(doc.zero && doc.curves.find(c => c.id === curveId)?.points.some(p => doc.zero!.pointIds.includes(p.id) && Math.abs(frequency(doc, p)) < 1e-6))
}
export function curvePath(doc: Document, curve: Curve) {
  let previous: Point | undefined
  const byId=new Map(curve.points.map(p=>[p.id,p]))
  return tracePoints(doc, curve).map(p => {
    if(p.connectTo){const parent=byId.get(p.connectTo);previous=p;return parent?'M'+parent.x+','+parent.y+' L'+p.x+','+p.y:'M'+p.x+','+p.y}
    const command = previous && connected(previous, p) ? 'L' : 'M'; previous = p
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
      if (c.pathOrdered !== undefined && typeof c.pathOrdered !== 'boolean') throw Error()
      if (!source || curveIds.has(c.id) || c.name !== source.name || c.color !== source.color) throw Error()
      curveIds.add(c.id)
      const earlier=new Set<string>()
      for (const p of c.points) {
        if (!p.id || ids.has(p.id) || !p.segment || typeof p.status !== 'string' || ![p.x, p.y].every(Number.isFinite) || p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) throw Error()
        if (p.manual !== undefined && typeof p.manual !== 'boolean' || p.breakBefore !== undefined && typeof p.breakBefore !== 'boolean') throw Error()
        if(p.connectTo !== undefined && (typeof p.connectTo !== 'string' || !earlier.has(p.connectTo)))throw Error()
        ids.add(p.id);earlier.add(p.id)
      }
      const sorted = ordered(d, c.points)
      if (!c.pathOrdered && sorted.some((p, i) => i > 0 && frequency(d, p) - frequency(d, sorted[i - 1]) < 1e-9)) throw Error()
    }
    if (d.zero && (!Number.isFinite(d.zero.pixel) || Math.abs(valueAt(d.calibration.frequency, d.zero.pixel)) > 1e-6 || !Array.isArray(d.zero.pointIds) || !d.zero.pointIds.every(id => ids.has(id)))) throw Error()
  } catch { throw new Error('草稿格式、来源或坐标无效，未覆盖已有数据。可恢复原始示例后再保存。') }
}
