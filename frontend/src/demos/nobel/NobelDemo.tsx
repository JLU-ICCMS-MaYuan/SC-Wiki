import { useState, useRef, useEffect, type CSSProperties, type PointerEvent } from 'react'
import theme from '../../theme'
import { projectGallery } from './projection'
import { laureates, type NobelLaureate } from './data'
import './nobel-demo.css'

const getPerson = () => new URLSearchParams(window.location.search).get('person')

function SourceList({ sources }: { sources: NobelLaureate['sources'] }) {
  return (
    <ol className="nobel-sources">
      {sources.map((source) => (
        <li key={source.url} id={`source-${sources.indexOf(source) + 1}`}>
          <a href={source.url} target="_blank" rel="noopener noreferrer">{source.label}</a>
          <span>{source.supports}</span>
        </li>
      ))}
    </ol>
  )
}

function Citations({ indices }: { indices: number[] }) {
  return <sup className="nobel-citations">{indices.map(index => <a key={index} href={`#source-${index}`} aria-label={`参考资料 ${index}`}>[{index}]</a>)}</sup>
}

function LaureateDetail({ person }: { person: NobelLaureate }) {
  return (
    <main className="nobel-detail">
      <a className="nobel-back" href="/nobel-demo.html">← 返回肖像展</a>
      <div className="nobel-detail-grid">
        <figure className="nobel-detail-portrait">
          <img src={person.image} alt={`${person.englishName} 的原始照片`} />
          <figcaption>历史原照 · 超导诺奖得主展</figcaption>
        </figure>
        <article className="nobel-biography">
          <p className="nobel-kicker">NOBEL PHYSICS · {person.awardYear}</p>
          <h1>{person.name}</h1>
          <p className="nobel-english-name">{person.englishName} <span>({person.years})</span><Citations indices={[1]} /></p>
          <p className="nobel-identity">获奖时国籍/身份：{person.identity}<Citations indices={[1, 2, 3]} /></p>
          {person.identityNote && <p className="nobel-note">{person.identityNote}</p>}
          <section>
            <h2>获奖成果</h2>
            <p>{person.awardReason}<Citations indices={[1, 3]} /></p>
          </section>
          <section>
            <h2>科研经历</h2>
            <p>{person.career}<Citations indices={[2]} /></p>
          </section>
          <section>
            <h2>与超导研究的关系</h2>
            <p>{person.superconductivityLink}<Citations indices={[1, 3, ...(person.sources.length > 3 ? [4] : [])]} /></p>
          </section>
          <section>
            <h2>参考资料</h2>
            <SourceList sources={person.sources} />
          </section>
          <p className="nobel-editorial-note">资料核对日期：2026 年 10 月 23 日。生卒年份与授奖理由依据诺奖官网；国籍、任职机构与出生地分别注明。当前展示历史原始照片，漫画版本后续制作。</p>
        </article>
      </div>
    </main>
  )
}

function Exhibition() {
  const [angle, setAngle] = useState(0)
  const [paused, setPaused] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [reduced, setReduced] = useState(false)
  const [width, setWidth] = useState(1100)
  const stage = useRef<HTMLDivElement>(null)
  const direction = useRef(1)
  const gesture = useRef<{ id: number; startX: number; lastX: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const step = 360 / laureates.length
  const frontIndex = ((Math.round(-angle / step) % laureates.length) + laureates.length) % laureates.length
  const layout = projectGallery(angle, laureates.length, width)

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    update()
    media.addEventListener('change', update)
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    if (stage.current) observer.observe(stage.current)
    return () => { media.removeEventListener('change', update); observer.disconnect() }
  }, [])

  useEffect(() => {
    if (paused || hovered || dragging || reduced) return
    let frame: number
    let previous = 0
    const tick = (now: number) => {
      // 隐藏标签页或卡顿恢复时不补跑全部时间，避免大幅跳动。
      if (previous) setAngle(value => value + direction.current * Math.min(now - previous, 40) * 0.005)
      previous = now
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [paused, hovered, dragging, reduced])

  const choose = (index: number) => { setAngle(-index * step); setPaused(true) }
  const pointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary || event.button !== 0 || gesture.current) return
    gesture.current = { id: event.pointerId, startX: event.clientX, lastX: event.clientX, moved: false }
    // 在原点击元素捕获，既保留普通链接点击，也能接收拖出舞台后的释放事件。
    ;(event.target as HTMLElement).setPointerCapture(event.pointerId)
    suppressClick.current = false
    setDragging(true)
  }
  const pointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const active = gesture.current
    if (!active || active.id !== event.pointerId) return
    if (!active.moved && Math.abs(event.clientX - active.startX) < 6) return
    if (!active.moved) {
      active.moved = true
      suppressClick.current = true
      event.currentTarget.setPointerCapture(event.pointerId)
    }
    const delta = event.clientX - active.lastX
    if (delta) direction.current = Math.sign(delta)
    setAngle(value => value + delta * 180 / Math.max(width, 360))
    active.lastX = event.clientX
    setHovered(false)
  }
  const pointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (gesture.current?.id !== event.pointerId) return
    gesture.current = null
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    const underPointer = document.elementFromPoint(event.clientX, event.clientY)
    setHovered(event.type !== 'pointercancel' && event.pointerType === 'mouse' && Boolean(underPointer?.closest('.nobel-face')))
  }

  return (
    <main className="nobel-exhibition">
      <header className="nobel-header">
        <a className="nobel-brand" href="/">SC-Wiki <span>科学史展厅</span></a>
        <p className="nobel-kicker">诺贝尔奖里程碑 · 1913—2003</p>
        <h1>超导研究的诺奖群像</h1>
        <p className="nobel-intro">十二位科学家，一段关于超导与量子物态的探索。</p>
      </header>
      <section className="nobel-gallery" aria-label="诺贝尔物理学奖得主肖像展">
        <div className="nobel-gallery-topline">
          <span>按住左右拖动，控制旋转方向 · 悬停暂停 · 点击阅读</span>
          <button type="button" onClick={() => setPaused(!paused)} aria-pressed={paused} disabled={reduced}>
            {reduced ? '减少动态已开启' : paused ? '继续旋转' : '暂停旋转'}
          </button>
        </div>
        <div className="nobel-stage" ref={stage} data-dragging={dragging} data-angle={angle}
          onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd}
          onPointerCancel={pointerEnd}
          onLostPointerCapture={event => {
            // 触屏从图片的隐式捕获转交舞台时，图片的 lost 事件会冒泡；它不是手势结束。
            if (event.target === event.currentTarget) pointerEnd(event)
          }}
          onPointerLeave={() => setHovered(false)}
          onClickCapture={event => {
            if (suppressClick.current) { event.preventDefault(); event.stopPropagation(); suppressClick.current = false }
          }}>
          <div className="nobel-ring" role="list" aria-label="旋转的获奖者肖像">
            {laureates.map((person, index) => {
              const { x, y, scale, cardWidth, yaw, opacity } = layout[index]
              const visible = opacity > 0 && Math.abs(x) < width / 2 + cardWidth * scale / 2
              return (
                <a key={person.id} role="listitem"
                  className={`nobel-face${index === frontIndex ? ' is-selected' : ''}`}
                  data-scale={scale}
                  style={{ transform: `translate(-50%, 0) translate(${x}px, ${y}px) scale(${scale})`,
                    width: cardWidth, '--portrait-yaw': `${yaw}deg`, opacity,
                    visibility: visible ? 'visible' : 'hidden' } as CSSProperties}
                  href={`/nobel-demo.html?person=${person.id}`} target="_blank" rel="noopener noreferrer"
                  tabIndex={visible ? 0 : -1} draggable={false}
                  aria-label={`查看 ${person.englishName}，${person.awardYear} 年诺贝尔物理学奖得主`}
                  onPointerEnter={event => { if (event.pointerType === 'mouse' && !gesture.current) setHovered(true) }}
                  onPointerLeave={() => setHovered(false)}
                  onFocus={() => { if (!gesture.current) choose(index) }}>
                  <div className="nobel-photo"><img src={person.image} alt={`${person.englishName} 原始照片`} draggable={false} /></div>
                  <div className="nobel-person-copy">
                    <span className="nobel-award-year">{person.awardYear} · 诺贝尔物理学奖</span>
                    <h2>{person.name}</h2>
                    <span className="nobel-person-english">{person.englishName}</span>
                    <span className="nobel-person-years">{person.years}</span>
                    <p className="nobel-person-identity">{person.identity}</p>
                    <p className="nobel-person-achievement">{person.achievement}</p>
                    <span className="nobel-person-open">科研经历与参考资料 ↗</span>
                  </div>
                </a>
              )
            })}
          </div>
        </div>
        <nav className="nobel-person-index" aria-label="选择获奖者">
          {laureates.map((person, index) => <button key={person.id} type="button" aria-pressed={frontIndex === index}
            onClick={() => choose(index)}>{person.englishName.split(' ').slice(-1)[0]}</button>)}
        </nav>
      </section>
      <footer className="nobel-footer">当前使用历史原照进行交互预览，漫画肖像后续制作。</footer>
    </main>
  )
}

export default function NobelDemo() {
  const personId = getPerson()
  const person = laureates.find((entry) => entry.id === personId)

  return (
    <div className="nobel-demo-shell" style={{
      '--nobel-primary': theme.palette.primary.main,
      '--nobel-text': theme.palette.text.primary,
      '--nobel-muted': theme.palette.text.secondary,
      '--nobel-divider': theme.palette.divider,
      fontFamily: theme.typography.fontFamily,
    } as CSSProperties}>
      {person ? <LaureateDetail person={person} /> : <Exhibition />}
    </div>
  )
}
