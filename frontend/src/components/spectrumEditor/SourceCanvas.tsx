import { useEffect, useId, useMemo, useRef, useState } from 'react'
import AxisOverlay from './AxisOverlay'
import { recognizedAxes } from './axisGeometry'
import { fitViewport, zoomViewport, wheelPixels, wheelFactor } from './viewport'
import { addPoint, amplitudePixel, curvePath, frequency, markZero, prepareMove, movePrepared, type PreparedMove, type Document, type Rect } from './engine'

export type Tool = 'select' | 'pan' | 'add' | 'box' | 'zero' | 'zeroPoint' | 'calibrate'
type Props = {
  doc: Document; active: string; selected: string[]; editing?: boolean; tool?: Tool; imageOpacity?: number
  linked?: boolean; dragMode?: 'amplitude' | 'free'; display?: string; all?: boolean
  referenceCurves?: Document["curves"]; onSelect?: (ids: string[]) => void; onChange?: (doc: Document, detail?: string) => void
  onAdded?: (id: string) => void; onZeroMarked?: () => void
  onPick?: (x: number, y: number) => void; onError?: (error: string) => void
}
type Gesture = { kind: 'point' | 'pan' | 'box'; start: DOMPoint; view: Rect; doc: Document; clientStart?: {x:number;y:number}; screenScale?: number; id?: string; prepared?: PreparedMove | null; moved?: Document }

export default function SourceCanvas({ doc, active, selected, editing = false, tool = 'select', linked = true, dragMode = 'free', display = 'overlay', all = true, imageOpacity = 100, onSelect, onChange, onPick, onError, onAdded, onZeroMarked, referenceCurves=[] }: Props) {
  const svg = useRef<SVGSVGElement>(null), gesture = useRef<Gesture | null>(null)
  const initial = (): Rect => { const [x, y, w, h] = doc.source.viewport; return [x - 46, y - 10, w + 62, h + 32] }
  const [view, setView] = useState<Rect>(initial), [preview, setPreview] = useState<Document | null>(null)
  const [showAxes, setShowAxes] = useState(true)
  const [fit, setFit] = useState<Rect>(initial), fitRef = useRef<Rect>(initial()), manualView = useRef(false)
  const [box, setBox] = useState<Rect | null>(null), [imageFailed, setImageFailed] = useState(false), [retry, setRetry] = useState(0), [scale, setScale] = useState(1)
  const clip = useId().replace(/:/g, ''), scene = preview || doc
  const curve = scene.curves.find(c => c.id === active)!
  const influence = useMemo(() => gesture.current?.doc === doc && gesture.current.id === selected[0]
    ? gesture.current.prepared : prepareMove(doc, active, selected[0], linked), [doc, active, selected[0], linked])
  const renderCurves=[...scene.curves,...referenceCurves.filter(c=>!scene.curves.some(v=>v.id===c.id))]
  const paths = new Map(renderCurves.map(c => [c.id, curvePath(scene, c)]))
  const [x0, y0, x1, y1] = scene.source.plot
  useEffect(() => { manualView.current=false; setImageFailed(false); setPreview(null) }, [doc.id])
  useEffect(() => {
    const element=svg.current!
    const update=()=>{
      const {width,height}=element.getBoundingClientRect()
      if (!width || !height) return
      const next=fitViewport(doc.source.viewport,width,height,showAxes)
      fitRef.current=next; setFit(next)
      if (!manualView.current) setView(next)
      setScale(element.getScreenCTM()?.a || 1)
    }
    update(); const observer=new ResizeObserver(update);observer.observe(element)
    return ()=>observer.disconnect()
  }, [doc.id,showAxes])
  useEffect(()=>{setScale(svg.current?.getScreenCTM()?.a || 1)},[view])
  const pointer=(clientX:number,clientY:number)=>new DOMPoint(clientX,clientY).matrixTransform(svg.current!.getScreenCTM()!.inverse())
  const zoom=(factor:number,anchor?:DOMPoint)=>{
    manualView.current=true
    setView(v=>zoomViewport(v,fitRef.current,factor,anchor))
  }
  const fitWindow=()=>{manualView.current=false;setView(fitRef.current)}
  useEffect(()=>{
    const element=svg.current!;let frame=0,delta=0,anchor:DOMPoint|undefined
    const wheel=(event:WheelEvent)=>{
      event.preventDefault();delta+=wheelPixels(event.deltaY,event.deltaMode,element.clientHeight);anchor=pointer(event.clientX,event.clientY)
      if(!frame) frame=requestAnimationFrame(()=>{frame=0;zoom(wheelFactor(delta),anchor);delta=0})
    }
    element.addEventListener('wheel',wheel,{passive:false})
    return ()=>{element.removeEventListener('wheel',wheel);cancelAnimationFrame(frame)}
  },[doc.id])
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
  const add = (x: number, y: number, zero = false) => operate(() => {
    const ids = new Set(curve.points.map(p => p.id)), next = addPoint(doc, active, x, y, zero)
    const nextCurve = next.curves.find(c => c.id === active)!
    const added = nextCurve.points.find(p => !ids.has(p.id)) || (zero ? nextCurve.points.find(p => next.zero?.pointIds.includes(p.id)
      && Math.abs(frequency(next, p)) < 1e-6 && Math.abs(amplitudePixel(next, p) - (next.calibration.direction === 'y' ? x : y)) <= 1e-4) : undefined)
    onChange?.(next)
    if (added) { onSelect?.([added.id]); onAdded?.(added.id) }
  })
  return <div className={'canvas-shell ' + (editing ? 'interactive' : 'detail-canvas')}>
    <div className="canvas-toolbar"><button className="axis-toggle" aria-pressed={showAxes} onClick={() => setShowAxes(v => !v)}>轴与刻度</button>
    <div className="canvas-controls">
      <button aria-label="缩小" title="缩小约5%" onClick={() => zoom(1.05)}>−</button><span>{Number((fit[2] / view[2] * 100).toFixed(1))}%</span>
      <button aria-label="放大" title="放大约5%" onClick={() => zoom(1 / 1.05)}>＋</button><button onClick={fitWindow}>适应窗口</button>
    </div>
    </div>
    {showAxes && <div className="axis-legend"><span>蓝：当前标定</span><span>灰：已有识别 / {recognizedAxes(doc)?.frequencyUnit || '待核对'}</span>{Boolean(recognizedAxes(doc)?.lambdaTicks.length) && <span>棕：累计 λ 参考</span>}</div>}
    {imageFailed && <div className="canvas-error" role="alert">原图加载失败，暂不能选点。<button onClick={() => { setRetry(n => n + 1); setImageFailed(false) }}>重试图片</button></div>}
    <svg ref={svg} className={'source-canvas tool-' + tool} role={editing ? 'application' : 'img'} aria-label={editing ? '谱线人工编辑画布' : display==='source'?'论文谱原图':display==='overlay'?'原图与提取数据叠加':`提取谱数据，频率沿${doc.calibration.direction==='y'?'竖轴':'横轴'}，与来源图一致`}
      data-source-crop={doc.source.viewport.join(',')} data-viewbox={view.join(',')} viewBox={view.join(' ')} preserveAspectRatio="xMidYMid meet"
      onContextMenu={e => e.preventDefault()}
      onPointerDown={event => {
        const pan = editing && tool === 'pan' || event.button === 1 || event.button === 2 || event.altKey
        if (!pan && (!editing || imageFailed || event.button !== 0)) return
        event.preventDefault(); const p = pointer(event.clientX, event.clientY)
        if (pan) { manualView.current=true; gesture.current = { kind:'pan', start:p, view, doc, clientStart:{x:event.clientX,y:event.clientY}, screenScale:svg.current!.getScreenCTM()!.a } }
        else if (tool === 'add') return add(p.x, p.y)
        else if (tool === 'zeroPoint') return add(p.x, p.y, true)
        else if (tool === 'zero') return operate(() => { onChange?.(markZero(doc, p.x, p.y)); onSelect?.([]); onZeroMarked?.() })
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
          setView([g.view[0]-(event.clientX-g.clientStart!.x)/g.screenScale!,g.view[1]-(event.clientY-g.clientStart!.y)/g.screenScale!,g.view[2],g.view[3]])
        } else if (g.kind === 'box') setBox([Math.min(g.start.x, p.x), Math.min(g.start.y, p.y), Math.abs(p.x - g.start.x), Math.abs(p.y - g.start.y)])
        else {
          g.moved = g.prepared ? movePrepared(g.prepared, p.x - g.start.x, p.y - g.start.y, dragMode) : g.doc
          setPreview(g.moved)
        }
      }} onPointerUp={() => finish()} onPointerCancel={() => finish(true)}>
      <defs><clipPath id={clip}><rect x={scene.source.viewport[0]} y={scene.source.viewport[1]} width={scene.source.viewport[2]} height={scene.source.viewport[3]} /></clipPath></defs>
      {display !== 'data' && scene.source.image && <image data-testid="source-image" opacity={imageOpacity / 100} key={retry} href={scene.source.image} width={scene.source.width} height={scene.source.height} clipPath={`url(#${clip})`} onError={() => setImageFailed(true)} />}
      {display === 'data' && <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="#fff" stroke="#9ea8b9" strokeWidth={1 / scale} />}
      {display !== 'source' && renderCurves.filter(c => all || c.id === active).map(c => <g key={c.id} opacity={editing && c.id !== active ? .3 : 1}>
        <path d={paths.get(c.id)} fill="none" stroke="white" strokeWidth={4 / scale}/>
        <path data-curve={c.id} d={paths.get(c.id)} fill="none" stroke={c.color} strokeWidth={1.7 / scale}/>
        {editing && c.id === active && c.points.map(point => {
          const picked = selected.includes(point.id), affected = (influence?.byId.get(point.id) || 0) > 0
          return <circle key={point.id} data-point={point.id} data-x={point.x} data-y={point.y} cx={point.x} cy={point.y} r={(picked ? 5 : affected ? 3.5 : 2) / scale}
            fill={picked ? '#fff' : affected ? '#f5ad35' : c.color} stroke={picked ? '#4f46e5' : '#fff'} strokeWidth={(picked ? 2.5 : .6) / scale} pointerEvents="none" />
        })}
      </g>)}
      {showAxes && <AxisOverlay doc={scene} scale={scale} point={curve.points.find(p => p.id === selected[0])}/>}
      {scene.zero && (scene.calibration.direction === 'y'
        ? <line data-testid="zero-line" x1={x0} x2={x1} y1={scene.zero.pixel} y2={scene.zero.pixel} stroke="#e28a19" strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale} ${4 / scale}`} />
        : <line data-testid="zero-line" y1={y0} y2={y1} x1={scene.zero.pixel} x2={scene.zero.pixel} stroke="#e28a19" strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale} ${4 / scale}`} />)}
      {box && <rect x={box[0]} y={box[1]} width={box[2]} height={box[3]} fill="#6455e822" stroke="#6455e8" strokeWidth={1 / scale} />}

    </svg>
    <div className="canvas-caption">{editing ? '滚轮缩放 · 右键 / Alt 拖动平移 · 橙色点为联动范围' : '人工修订可追溯 · 未补选的缺口保留'}</div>
  </div>
}
