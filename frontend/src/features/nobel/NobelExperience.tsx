import { useState, useRef, useEffect, useLayoutEffect, useMemo, type CSSProperties, type PointerEvent } from 'react'
import theme from '../../theme'
import { projectGallery } from './projection'
import type { NobelLaureate } from './data'
import type { Lang } from '../../i18n'
import { getLaureates, coAwardText, copy, contacts } from './copy'
import './nobel.css'


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

function Citations({ indices, lang }: { indices: number[]; lang: Lang }) {
  return <sup className="nobel-citations">{indices.map(index => <a key={index} href={`#source-${index}`} aria-label={copy[lang].citation(index)}>[{index}]</a>)}</sup>
}

export function NobelDetail({ person, lang = 'zh', backHref = '/news#nobel-milestones' }: { person: NobelLaureate; lang?: Lang; backHref?: string }) {
  const text = copy[lang]
  const people = getLaureates(lang)
  return (
    <section className="nobel-detail">
      <a className="nobel-back" href={backHref}>{text.back}</a>
      <div className="nobel-detail-grid">
        <figure className="nobel-detail-portrait">
          <img src={person.image} alt={`${person.englishName} · ${text.photo}`} />
          <figcaption>{text.photoCaption}</figcaption>
        </figure>
        <article className="nobel-biography">
          <p className="nobel-kicker">NOBEL PHYSICS · {person.awardYear}</p>
          <h1>{person.name}</h1>
          <p className="nobel-english-name">{person.englishName} <span>({person.years})</span><Citations lang={lang} indices={[1]} /></p>
          <p className="nobel-identity">{text.identity}{person.identity}<Citations lang={lang} indices={[1, 2, 3]} /></p>
          {person.identityNote && <p className="nobel-note">{person.identityNote}</p>}
          <section>
            <h2>{text.achievement}</h2>
            <p>{person.awardReason}<Citations lang={lang} indices={[1, 3]} /></p>
            <p className="nobel-coaward">{coAwardText(person, people, lang)}<Citations lang={lang} indices={[1, 3]} /></p>
            <p>{text.share}<strong>{person.prizeShare}</strong><Citations lang={lang} indices={[1]} /></p>
          </section>
          <section>
            <h2>{text.career}</h2>
            <p>{person.career}<Citations lang={lang} indices={[2]} /></p>
          </section>
          <section>
            <h2>{text.connection}</h2>
            <p>{person.superconductivityLink}<Citations lang={lang} indices={[1, 3, ...(person.sources.length > 3 ? [4] : [])]} /></p>
          </section>
          <section>
            <h2>{text.sources}</h2>
            <SourceList sources={person.sources} />
          </section>
          <p className="nobel-editorial-note">{text.note}</p>
        </article>
      </div>
    </section>
  )
}

export function NobelGallery({ lang = 'zh', embedded = false, detailHref = id => `/nobel/${id}` }: {
  lang?: Lang; embedded?: boolean; detailHref?: (id: string) => string
}) {
  const text = copy[lang]
  const laureates = useMemo(() => getLaureates(lang), [lang])
  const Title = embedded ? 'h2' : 'h1'
  const [angle, setAngle] = useState(0)
  const [focused, setFocused] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [reduced, setReduced] = useState(false)
  const [width, setWidth] = useState(1100)
  const [cardHeights, setCardHeights] = useState<number[]>([])
  const stage = useRef<HTMLDivElement>(null)
  const direction = useRef(1)
  const gesture = useRef<{ id: number; startX: number; lastX: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const step = 360 / laureates.length
  const frontIndex = ((Math.round(-angle / step) % laureates.length) + laureates.length) % laureates.length
  const layout = projectGallery(angle, laureates.length, width)
  const visible = (index: number) => {
    const card = layout[index]
    return card.opacity > 0 && Math.abs(card.x) < width / 2 + card.cardWidth * card.scale / 2
  }
  // 8px顶部 + 可见卡片变换后的底边 + 12px底部，不使用会留下大片空白的固定高度。
  const stageHeight = Math.ceil(8 + Math.max(...layout.map((card, index) =>
    visible(index) ? card.y + (cardHeights[index] || 660) * card.scale : 0)) + 12)

  useLayoutEffect(() => {
    const cards = [...(stage.current?.querySelectorAll<HTMLElement>('.nobel-face') ?? [])]
    const measure = () => {
      const heights = cards.map(card => card.offsetHeight)
      setCardHeights(previous => heights.every((height, index) => height === previous[index]) ? previous : heights)
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    cards.forEach(card => observer?.observe(card))
    return () => observer?.disconnect()
  }, [lang])

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media?.matches ?? true)
    update()
    media?.addEventListener('change', update)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    if (stage.current) observer?.observe(stage.current)
    return () => { media?.removeEventListener('change', update); observer?.disconnect() }
  }, [])

  useEffect(() => {
    if (focused || hovered || dragging || reduced) return
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
  }, [focused, hovered, dragging, reduced])

  const choose = (index: number) => setAngle(-index * step)
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
    <section className={`nobel-exhibition${embedded ? ' nobel-embedded' : ''}`} id={embedded ? 'nobel-milestones' : undefined}>
      <header className="nobel-header">
        {!embedded && <a className="nobel-brand" href="/">SC-Wiki <span>{text.brand}</span></a>}
        <p className="nobel-kicker">{text.kicker}</p>
        <Title>{text.title}</Title>
        <p className="nobel-intro">{text.intro}</p>
      </header>
      <section className="nobel-gallery" aria-label={text.gallery}>
        <div className="nobel-stage" ref={stage} data-dragging={dragging} data-angle={angle} style={{ height: stageHeight }}
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
          <div className="nobel-ring" role="list" aria-label={text.ring}>
            {laureates.map((person, index) => {
              const { x, y, scale, cardWidth, yaw, opacity } = layout[index]
              const isVisible = visible(index)
              return (
                <a key={person.id} role="listitem"
                  className={`nobel-face${index === frontIndex ? ' is-selected' : ''}`}
                  data-scale={scale}
                  style={{ transform: `translate(-50%, 0) translate(${x}px, ${y}px) scale(${scale})`,
                    width: cardWidth, '--portrait-yaw': `${yaw}deg`, opacity,
                    visibility: isVisible ? 'visible' : 'hidden' } as CSSProperties}
                  href={detailHref(person.id)} target="_blank" rel="noopener noreferrer"
                  tabIndex={isVisible ? 0 : -1} draggable={false}
                  aria-label={text.visit(person.englishName, person.awardYear)}
                  onPointerEnter={event => { if (event.pointerType === 'mouse' && !gesture.current) setHovered(true) }}
                  onPointerLeave={() => setHovered(false)}
                  onFocus={() => { if (!gesture.current) { choose(index); setFocused(true) } }}
                  onBlur={() => setFocused(false)}>
                  <div className="nobel-photo"><img src={person.image} alt={`${person.englishName} · ${text.photo}`} draggable={false} /></div>
                  <div className="nobel-person-copy">
                    <span className="nobel-award-year">{person.awardYear} · {text.prize}</span>
                    <h2>{person.name}</h2>
                    {lang === 'zh' && <span className="nobel-person-english">{person.englishName}</span>}
                    <span className="nobel-person-years">{person.years}</span>
                    <p className="nobel-person-identity">{person.identity}</p>
                    <p className="nobel-person-achievement">{person.achievement}</p>
                    <p className="nobel-person-coaward">{coAwardText(person, laureates, lang)}</p>
                    <span className="nobel-person-open">{text.read}</span>
                  </div>
                </a>
              )
            })}
          </div>
        </div>
        <nav className="nobel-person-index" aria-label={text.select}>
          {laureates.map((person, index) => <button key={person.id} type="button" aria-pressed={frontIndex === index}
            onClick={() => choose(index)}>{person.englishName.split(' ').slice(-1)[0]}</button>)}
        </nav>
      </section>
      <footer className="nobel-contact">
        <div className="nobel-contact-list">
          {contacts.map(contact => <span key={contact.zh} className="nobel-contact-person">
            <span>{contact[lang]}</span>
            {contact.email && <a href={`mailto:${contact.email}`}>{contact.email}</a>}
          </span>)}
        </div>
        <p>{text.contactInvite}</p>
      </footer>
    </section>
  )
}

export function NobelSurface({ children }: { children: React.ReactNode }) {
  return (
    <div className="nobel-feature" style={{
      '--nobel-primary': theme.palette.primary.main,
      '--nobel-text': theme.palette.text.primary,
      '--nobel-muted': theme.palette.text.secondary,
      '--nobel-divider': theme.palette.divider,
      fontFamily: theme.typography.fontFamily,
    } as CSSProperties}>{children}</div>
  )
}
