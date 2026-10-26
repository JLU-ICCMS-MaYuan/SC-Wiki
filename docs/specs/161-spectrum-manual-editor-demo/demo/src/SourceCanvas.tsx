import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { addPoint, curvePath, frequency, markZero, prepareMove, movePrepared, type PreparedMove, type Document, type Point, type Rect } from './engine'

export type Tool = 'select' | 'pan' | 'add' | 'box' | 'zero' | 'zeroPoint' | 'calibrate'
type Props = {
  doc: Document; active: string; selected: string[]; editing?: boolean; tool?: Tool
  linked?: boolean; dragMode?: 'amplitude' | 'free'; display?: string; all?: boolean
  onSelect?: (ids: string[]) => void; onChange?: (doc: Document, detail?: string) => void
  onPick?: (x: number, y: number) => void; onError?: (error: string) => void
}
type Gesture = { kind: 'point' | 'pan' | 'box'; start: DOMPoint; view: Rect; doc: Document; id?: string; prepared?: PreparedMove | null; moved?: Document }

export default function SourceCanvas({ doc, active, selected, editing = false, tool = 'select', linked = true, dragMode = 'amplitude', display = 'overlay', all = true, onSelect, onChange, onPick, onError }: Props) {
  const svg = useRef<SVGSVGElement>(null), gesture = useRef<Gesture | null>(null)
  const initial = (): Rect => { const [x, y, w, h] = doc.source.viewport; return [x - 34, y - 3, w + 40, h + 10] }
  const [view, setView] = useState<Rect>(initial), [preview, setPreview] = useState<Document | null>(null)
  const [box, setBox] = useState<Rect | null>(null), [imageFailed, setImageFailed] = useState(false), [retry, setRetry] = useState(0), [scale, setScale] = useState(1)
  const clip = useId().replace(/:/g, ''), scene = preview || doc
  const curve = scene.curves.find(c => c.id === active)!
  const influence = useMemo(() => gesture.current?.doc === doc && gesture.current.id === selected[0]
    ? gesture.current.prepared : prepareMove(doc, active, selected[0], linked), [doc, active, selected[0], linked])
  const paths = useMemo(() => new Map(scene.curves.map(c => [c.id, curvePath(scene, c)])), [scene])
  const [x0, y0, x1, y1] = scene.source.plot
  useEffect(() => { setView(initial()); setImageFailed(false); setPreview(null) }, [doc.id])
  useEffect(() => {
    const update = () => setScale(svg.current?.getScreenCTM()?.a || 1)
    update(); const observer = new ResizeObserver(update)
    if (svg.current) observer.observe(svg.current)
    return () => observer.disconnect()
  }, [view])
  const pointer = (clientX: number, clientY: number) => new DOMPoint(clientX, clientY).matrixTransform(svg.current!.getScreenCTM()!.inverse())
  const zoom = (factor: number, anchor?: DOMPoint) => setView(v => {
    const original = initial(), w = Math.max(original[2] / 24, Math.min(original[2] * 2, v[2] * factor)), ratio = w / v[2]
    const x = anchor?.x ?? v[0] + v[2] / 2, y = anchor?.y ?? v[1] + v[3] / 2
    return [x - (x - v[0]) * ratio, y - (y - v[1]) * ratio, w, v[3] * ratio]
  })
  useEffect(() => {
    const element = svg.current!
    const wheel = (event: WheelEvent) => { event.preventDefault(); zoom(Math.exp(event.deltaY * .0015), pointer(event.clientX, event.clientY)) }
    element.addEventListener('wheel', wheel, { passive: false })
    return () => element.removeEventListener('wheel', wheel)
  }, [doc.id])
  const finish = (cancel = false) => {
    const g = gesture.current
    if (g && !cancel) {
      if (g.kind === 'point' && g.moved) onChange?.(g.moved, linked ? '拖动点及邻近片段' : '拖动单点')
      if (g.kind === 'box' && box) {
        const [a, b, w, h] = box
        onSelect?.(curve.points.filter(p => p.x >= a && p.x <= a + w && p.y >= b && p.y <= b + h).map(p => p.id))
      }
    }
    gesture.current = null; setPreview(null); setBox(null)
  }
  const operate = (action: () => void) => { try { action() } catch (e) { onError?.((e as Error).message) } }
  return <div className={'canvas-shell ' + (editing ? 'interactive' : 'detail-canvas')}>
    <div className="canvas-controls">
      <button aria-label="缩小" onClick={() => zoom(1.35)}>−</button><span>{Math.round(initial()[2] / view[2] * 100)}%</span>
      <button aria-label="放大" onClick={() => zoom(1 / 1.35)}>＋</button><button onClick={() => setView(initial())}>适应窗口</button>
    </div>
    {imageFailed && <div className="canvas-error" role="alert">原图加载失败，暂不能选点。<button onClick={() => { setRetry(n => n + 1); setImageFailed(false) }}>重试图片</button></div>}
    <svg ref={svg} className={'source-canvas tool-' + tool} role={editing ? 'application' : 'img'} aria-label={editing ? '谱线人工编辑画布' : '原图与提取结果'}
      data-viewbox={view.join(',')} viewBox={view.join(' ')} preserveAspectRatio="xMidYMid meet"
      onContextMenu={e => e.preventDefault()}
      onPointerDown={event => {
        if (!editing || imageFailed) return
        event.preventDefault(); const p = pointer(event.clientX, event.clientY)
        const pan = tool === 'pan' || event.button === 1 || event.button === 2 || event.altKey
        if (!pan && event.button !== 0) return
        if (pan) gesture.current = { kind: 'pan', start: p, view, doc }
        else if (tool === 'add') return operate(() => onChange?.(addPoint(doc, active, p.x, p.y)))
        else if (tool === 'zeroPoint') return operate(() => onChange?.(addPoint(doc, active, p.x, p.y, true)))
        else if (tool === 'zero') return operate(() => onChange?.(markZero(doc, p.x, p.y)))
        else if (tool === 'calibrate') return onPick?.(p.x, p.y)
        else if (tool === 'box') { gesture.current = { kind: 'box', start: p, view, doc }; setBox([p.x, p.y, 0, 0]) }
        else {
          const candidates = curve.points.map(point => ({ point, distance: Math.hypot(point.x - p.x, point.y - p.y) * scale })).filter(v => v.distance <= 9).sort((a, b) => a.distance - b.distance)
          if (!candidates.length) { onSelect?.([]); return }
          const point = candidates[0].point
          onSelect?.([point.id]); gesture.current = { kind: 'point', start: p, view, doc, id: point.id, prepared: prepareMove(doc, active, point.id, linked) }
        }
        svg.current!.setPointerCapture(event.pointerId)
      }}
      onPointerMove={event => {
        const g = gesture.current
        if (!g) return
        const p = pointer(event.clientX, event.clientY)
        if (g.kind === 'pan') {
          setView(v => [v[0] - (p.x - g.start.x), v[1] - (p.y - g.start.y), v[2], v[3]])
        } else if (g.kind === 'box') setBox([Math.min(g.start.x, p.x), Math.min(g.start.y, p.y), Math.abs(p.x - g.start.x), Math.abs(p.y - g.start.y)])
        else {
          g.moved = g.prepared ? movePrepared(g.prepared, p.x - g.start.x, p.y - g.start.y, dragMode) : g.doc
          setPreview(g.moved)
        }
      }} onPointerUp={() => finish()} onPointerCancel={() => finish(true)}>
      <defs><clipPath id={clip}><rect x={scene.source.viewport[0]} y={scene.source.viewport[1]} width={scene.source.viewport[2]} height={scene.source.viewport[3]} /></clipPath></defs>
      {display !== 'data' && <image key={retry} href={scene.source.image} width={scene.source.width} height={scene.source.height} clipPath={`url(#${clip})`} onError={() => setImageFailed(true)} />}
      {display === 'data' && <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="#fff" stroke="#9ea8b9" strokeWidth={1 / scale} />}
      {display !== 'source' && scene.curves.filter(c => all || c.id === active).map(c => <g key={c.id} opacity={editing && c.id !== active ? .3 : 1}>
        <path d={paths.get(c.id)} fill="none" stroke="white" strokeWidth={4 / scale}/>
        <path data-curve={c.id} d={paths.get(c.id)} fill="none" stroke={c.color} strokeWidth={1.7 / scale}/>
        {editing && c.id === active && c.points.map(point => {
          const picked = selected.includes(point.id), affected = (influence?.byId.get(point.id) || 0) > 0
          return <circle key={point.id} data-point={point.id} data-x={point.x} data-y={point.y} cx={point.x} cy={point.y} r={(picked ? 5 : affected ? 3.5 : 2) / scale}
            fill={picked ? '#fff' : affected ? '#f5ad35' : c.color} stroke={picked ? '#4f46e5' : '#fff'} strokeWidth={(picked ? 2.5 : .6) / scale} pointerEvents="none" />
        })}
      </g>)}
      {scene.zero && (scene.calibration.direction === 'y'
        ? <line data-testid="zero-line" x1={x0} x2={x1} y1={scene.zero.pixel} y2={scene.zero.pixel} stroke="#e28a19" strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale} ${4 / scale}`} />
        : <line data-testid="zero-line" y1={y0} y2={y1} x1={scene.zero.pixel} x2={scene.zero.pixel} stroke="#e28a19" strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale} ${4 / scale}`} />)}
      {box && <rect x={box[0]} y={box[1]} width={box[2]} height={box[3]} fill="#6455e822" stroke="#6455e8" strokeWidth={1 / scale} />}
      {Array.from({ length: 5 }, (_, i) => {
        const p = { id: '', segment: '', status: '', x: x0 + (x1 - x0) * i / 4, y: y1 - (y1 - y0) * i / 4 } as Point
        const vertical = scene.calibration.direction === 'y'
        return <text key={i} x={vertical ? x0 - 6 : p.x} y={vertical ? p.y + 2 : y1 + 13} fontSize={7} fill="#6e7890" textAnchor={vertical ? 'end' : 'middle'}>{Number(frequency(scene, p).toFixed(1))}</text>
      })}
    </svg>
    <div className="canvas-caption">{editing ? '滚轮缩放 · 右键 / Alt 拖动平移 · 橙色点为联动范围' : '人工补点自动连线 · 未补选的缺口保留 · 演示数据'}</div>
  </div>
}
