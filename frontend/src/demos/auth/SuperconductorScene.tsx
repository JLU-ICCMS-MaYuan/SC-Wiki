import React, { useEffect, useRef, useState } from 'react'
import { IconButton } from '@mui/material'
import { PauseRounded, PlayArrowRounded } from '@mui/icons-material'
import type { AuthDemoCopy } from './copy'
import { advanceOrbit, DEFAULT_SPEED, MAX_SPEED, normalizeAngle, pushOrbit, TAU, type OrbitMotion } from './orbitMotion'
import MagneticField from './MagneticField'

const point = (angle: number, rx: number, ry: number, offset = 0) => `${360 + Math.cos(angle) * rx},${245 + Math.sin(angle) * ry + offset}`
const TRAIL_COUNT = 28
const LOCAL_CLOUD_COUNT = 16

export default function SuperconductorScene({ copy }: { copy: AuthDemoCopy }) {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  const [choice, setChoice] = useState<boolean | null>(null)
  const [visible, setVisible] = useState(!document.hidden)
  const [parked, setParked] = useState(false)
  const [stopAngle, setStopAngle] = useState<number | null>(null)
  const [atLimit, setAtLimit] = useState(false)
  const enabled = (choice ?? !reduced) && visible
  const running = enabled && !parked
  const svg = useRef<SVGSVGElement>(null)
  const puck = useRef<SVGGElement>(null)
  const shadow = useRef<SVGEllipseElement>(null)
  const vapor = useRef<SVGGElement>(null)
  const trail = useRef<SVGGElement>(null)
  const clouds = useRef<Array<{ cycle: number; x: number; y: number; scale: number; drift: number }>>([])
  const vaporTime = useRef(0)
  const motion = useRef<OrbitMotion>({ angle: 0.55, speed: DEFAULT_SPEED, target: null })

  const push = () => {
    pushOrbit(motion.current, !running)
    setStopAngle(null); setParked(false); setChoice(true)
    setAtLimit(motion.current.speed >= MAX_SPEED)
  }
  const selectStop = (angle: number) => {
    motion.current.target = normalizeAngle(angle)
    setStopAngle(motion.current.target)
  }
  const clickTrack = (event: React.MouseEvent<SVGEllipseElement>) => {
    const matrix = svg.current?.getScreenCTM()
    if (!matrix || !svg.current) return
    const position = svg.current.createSVGPoint()
    position.x = event.clientX; position.y = event.clientY
    const local = position.matrixTransform(matrix.inverse())
    selectStop(Math.atan2((local.y - 245) / 98, (local.x - 360) / 244))
  }

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const onMotion = () => { setReduced(media?.matches ?? false); setChoice(null) }
    const onVisibility = () => setVisible(!document.hidden)
    media?.addEventListener('change', onMotion)
    document.addEventListener('visibilitychange', onVisibility)
    return () => { media?.removeEventListener('change', onMotion); document.removeEventListener('visibilitychange', onVisibility) }
  }, [])

  useEffect(() => {
    let frame = 0
    let last: number | null = null
    const draw = () => {
      const angle = motion.current.angle
      const x = 360 + 244 * Math.cos(angle)
      const y = 245 + 98 * Math.sin(angle)
      const scale = 0.9 + 0.1 * Math.sin(angle)
      puck.current?.setAttribute('transform', `translate(${x} ${y - 42}) scale(${scale})`)
      puck.current?.setAttribute('data-phase', String(angle / TAU))
      puck.current?.setAttribute('data-period', motion.current.speed ? String(Math.round(TAU / motion.current.speed)) : 'stopped')
      shadow.current?.setAttribute('cx', String(x))
      shadow.current?.setAttribute('cy', String(y + 2))
      shadow.current?.setAttribute('rx', String(39 * scale))
      // 世界坐标尾迹保留在经过的轨道附近，不像贴在圆片上的透明装饰。
      Array.from(trail.current?.children ?? []).forEach((cloud, i) => {
        const clock = vaporTime.current / 3200 + i / TRAIL_COUNT
        const phase = clock % 1, cycle = Math.floor(clock)
        if (!clouds.current[i] || clouds.current[i].cycle !== cycle) {
          const emissionAngle = clouds.current[i] ? angle : angle - Math.min(.7, motion.current.speed * phase * 1400)
          const spread = ((i * 13) % 23) - 11
          clouds.current[i] = {
            cycle, x: 360 + (244 + spread) * Math.cos(emissionAngle),
            y: 245 + 98 * Math.sin(emissionAngle) - 33 + (i % 4) * 4,
            scale: .88 + .1 * Math.sin(emissionAngle), drift: Math.sin(emissionAngle) * 34 + spread,
          }
        }
        const origin = clouds.current[i]
        const dx = origin.drift * phase + Math.sin(phase * Math.PI * 3 + i) * 5
        const dy = 50 * phase - Math.sin(phase * Math.PI) * 15
        cloud.setAttribute('transform', `translate(${origin.x + dx} ${origin.y + dy}) scale(${origin.scale * (.8 + phase * 1.9)})`)
        cloud.setAttribute('opacity', String(Math.pow(Math.sin(phase * Math.PI), .6) * .92))
      })
      // 近表面浓雾持续向两侧翻滚；同一时钟保证暂停和后台冻结。
      Array.from(vapor.current?.children ?? []).forEach((cloud, i) => {
        const phase = (vaporTime.current / 2400 + i / LOCAL_CLOUD_COUNT) % 1
        const spread = i % 2 ? 1 : -1
        const x = spread * (15 + 45 * phase) + Math.sin(angle) * phase * 30
        const y = -4 - 50 * Math.sin(phase * Math.PI) + 22 * phase
        cloud.setAttribute('transform', `translate(${x} ${y}) scale(${.8 + phase * 1.9})`)
        cloud.setAttribute('opacity', String(Math.sin(phase * Math.PI) * .88))
      })
    }
    const tick = (now: number) => {
      if (last !== null) {
        const delta = now - last
        vaporTime.current += delta
        if (advanceOrbit(motion.current, delta)) { setParked(true); setAtLimit(false) }
      }
      last = now
      draw()
      frame = requestAnimationFrame(tick)
    }
    draw()
    if (enabled) frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [enabled])

  return <div className="sc-scene">
    <svg ref={svg} className="sc-orbit" viewBox="0 65 720 345" role="group" aria-label={copy.sceneLabel}>
      <defs>
        <linearGradient id="sc-track" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f6f7fa" /><stop offset=".45" stopColor="#d6dbe4" /><stop offset=".65" stopColor="#f8fafc" /><stop offset="1" stopColor="#b7becd" />
        </linearGradient>
        <linearGradient id="sc-track-side" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#eef0f5" /><stop offset=".5" stopColor="#b1b8c8" /><stop offset="1" stopColor="#d1d6e1" /></linearGradient>
        <linearGradient id="sc-puck-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#626874" /><stop offset=".2" stopColor="#343a44" /><stop offset=".65" stopColor="#171b23" /><stop offset="1" stopColor="#333a46" />
        </linearGradient>
        <radialGradient id="sc-puck-top" cx="35%" cy="25%" r="80%">
          <stop offset="0" stopColor="#858e98" /><stop offset=".3" stopColor="#555d67" /><stop offset=".7" stopColor="#323943" /><stop offset="1" stopColor="#20262f" />
        </radialGradient>
        <radialGradient id="sc-vapor" cx="43%" cy="34%"><stop offset="0" stopColor="#e2e8f0" stopOpacity=".95" /><stop offset=".5" stopColor="#e8edf4" stopOpacity=".9" /><stop offset=".8" stopColor="#f1f4f8" stopOpacity=".72" /><stop offset="1" stopColor="#e4eaf2" stopOpacity="0" /></radialGradient>
        <g id="sc-cloud-shape">
          <path d="M-40 7C-48-2-39-11-30-10C-37-25-12-30-6-19C1-34 22-26 22-14C42-23 53-3 36 5C49 19 26 29 15 18C6 34-17 26-20 17C-37 27-52 17-40 7Z" fill="url(#sc-vapor)" />
          <path d="M-30-5C-39-19-13-25-7-12C5-29 27-19 20-6C35-15 44-2 29 6C18 15 4 7-7 14C-18 20-29 10-30-5Z" fill="#fff" opacity=".7" />
        </g>
        <marker id="sc-field-arrow" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L6 4L1 7" fill="none" stroke="#238ca5" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /></marker>
        <marker id="sc-current-arrow" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L6 4L1 7" fill="none" stroke="#9868bf" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /></marker>
        <linearGradient id="sc-frost" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fff" stopOpacity=".9" /><stop offset="1" stopColor="#b8d8e8" stopOpacity=".05" /></linearGradient>
        <pattern id="sc-grain" width="29" height="23" patternUnits="userSpaceOnUse">
          {Array.from({ length: 39 }, (_, i) => <ellipse key={i} cx={(i * 17.37) % 29} cy={(i * 11.79) % 23} rx={.25 + i % 4 * .19} ry={.2 + i % 3 * .16} fill={i % 3 ? '#bdc8d3' : '#10161e'} opacity={.15 + i % 5 * .065} />)}
        </pattern>
        <filter id="sc-vapor-soft" x="-50%" y="-100%" width="200%" height="300%">
          <feTurbulence type="fractalNoise" baseFrequency=".035 .065" numOctaves="2" seed="8" result="cloud-noise" />
          <feDisplacementMap in="SourceGraphic" in2="cloud-noise" scale="17" xChannelSelector="R" yChannelSelector="G" />
          <feGaussianBlur stdDeviation="2" />
        </filter>
        <filter id="sc-soft-shadow" x="-50%" y="-100%" width="200%" height="300%"><feGaussianBlur stdDeviation="5" /></filter>
      </defs>

      {/* 背景测量线与有方向的磁场示意分开，不把测量线冒充物理场线。 */}
      <g fill="none" stroke="#e9eaf1" strokeWidth="1">
        <ellipse cx="360" cy="257" rx="316" ry="135" strokeDasharray="3 8" />
        <path d="M29 257H691M360 103V413" strokeDasharray="3 8" />
      </g>
      <ellipse cx="360" cy="273" rx="273" ry="109" fill="none" stroke="#c9c6dc" strokeWidth="19" opacity=".16" filter="url(#sc-soft-shadow)" />

      {/* 磁轨侧面、表面与内外边缘提供连续的透视深度。 */}
      <ellipse cx="360" cy="258" rx="246" ry="99" fill="none" stroke="url(#sc-track-side)" strokeWidth="48" />
      <ellipse cx="360" cy="245" rx="246" ry="99" fill="none" stroke="url(#sc-track)" strokeWidth="48" />
      {Array.from({ length: 64 }, (_, i) => {
        const start = i / 64 * TAU + 0.012
        const end = (i + 1) / 64 * TAU - 0.012
        return <polygon key={i} points={`${point(start, 270, 111)} ${point(end, 270, 111)} ${point(end, 222, 87)} ${point(start, 222, 87)}`}
          fill={i % 2 ? '#eef0f5' : '#ccd2df'} stroke="#ffffff" strokeWidth=".7" />
      })}
      <ellipse cx="360" cy="245" rx="272" ry="113" fill="none" stroke="#969db3" strokeWidth="1.5" />
      <ellipse cx="360" cy="245" rx="219" ry="86" fill="none" stroke="#b1b8c8" strokeWidth="1.5" />
      <g fill="none" stroke="#aba3dd" strokeWidth="1" opacity=".35">
        <ellipse cx="360" cy="245" rx="247" ry="100" />
      </g>
      <g fill="#8e86ac" fontFamily="inherit" fontSize="11" letterSpacing="2">
        <text x="360" y="242" textAnchor="middle">SC-WIKI</text>
        <text x="360" y="262" textAnchor="middle" fontSize="8" letterSpacing="3" fill="#ada7bb">SUPERCONDUCTIVITY</text>
      </g>
      <g fill="none" stroke="#c1badc" strokeWidth="1">
        <path d="M107 328L76 358H40M585 184L618 155H674" />
        <circle cx="107" cy="328" r="3" fill="white" /><circle cx="585" cy="184" r="3" fill="white" />
      </g>
      <text x="42" y="376" fill="#9b95b0" fontSize="10" letterSpacing="1.3">01 / MAGNETIC TRACK</text>
      <text x="610" y="145" fill="#9b95b0" fontSize="10" letterSpacing="1.3">T &lt; T<tspan baselineShift="sub" fontSize="8">c</tspan></text>

      <g ref={trail} className="sc-vapor sc-vapor-trail" pointerEvents="none" aria-hidden="true" filter="url(#sc-vapor-soft)">
        {Array.from({ length: TRAIL_COUNT }, (_, i) => <g key={i}>
          <use href="#sc-cloud-shape" transform={`rotate(${(i % 5 - 2) * 11})`} />
        </g>)}
      </g>

      <ellipse className="sc-track-control" cx="360" cy="245" rx="244" ry="98" fill="none" stroke="transparent" strokeWidth="49"
        role="button" tabIndex={0} aria-label={copy.stopTrack} onClick={clickTrack} onKeyDown={event => {
          if (['Enter', ' ', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
            event.preventDefault()
            selectStop((stopAngle ?? motion.current.angle + Math.PI / 2) + (event.key === 'ArrowLeft' ? -.2 : event.key === 'ArrowRight' ? .2 : 0))
          }
        }} />
      {stopAngle !== null && <g className="sc-stop-marker" pointerEvents="none" transform={`translate(${360 + 244 * Math.cos(stopAngle)} ${245 + 98 * Math.sin(stopAngle)})`}>
        <ellipse rx="23" ry="10" fill="#ffffff" fillOpacity=".8" stroke="#8a6bbd" strokeWidth="1.5" strokeDasharray="3 3" />
        <path d="M0 0V-28M-7-28H7" stroke="#8063ad" strokeWidth="2" strokeLinecap="round" />
      </g>}

      <ellipse ref={shadow} cx="568" cy="298" rx="39" ry="10" fill="#4f46a1" opacity=".22" filter="url(#sc-soft-shadow)" />
      <g ref={puck} data-testid="superconductor-puck" className="sc-puck-interactive" role="button" tabIndex={0} aria-label={copy.pushPuck}
        onClick={event => { event.stopPropagation(); push() }} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); push() } }}>
        <title>{copy.pushPuck}</title>
        <ellipse rx="60" ry="50" fill="transparent" />
        <ellipse className="sc-push-halo" cy="10" rx="49" ry="25" fill="none" stroke="#9890c8" strokeWidth="1" strokeDasharray="3 4" />
        <g ref={vapor} className="sc-vapor sc-vapor-local" pointerEvents="none" aria-hidden="true" filter="url(#sc-vapor-soft)">
          {Array.from({ length: LOCAL_CLOUD_COUNT }, (_, i) => <g key={i}><use href="#sc-cloud-shape" transform={`rotate(${(i % 5 - 2) * 13}) scale(.85)`} /></g>)}
        </g>
        <g className="sc-puck-body">
          <path d="M-42-5C-42-31 42-31 42-5V12C42 37-42 37-42 12Z" fill="url(#sc-puck-side)" stroke="#252d37" strokeWidth=".5" />
          {[5, 9, 13, 17].map(y => <path key={y} d={`M-40 ${y}Q0 ${y + 24} 40 ${y}`} fill="none" stroke={y === 17 ? '#9ba9b8' : '#788490'} strokeWidth=".5" opacity={y === 17 ? '.55' : '.22'} />)}
          <ellipse cy="-5" rx="42" ry="21" fill="url(#sc-puck-top)" stroke="#aab5c0" strokeWidth=".85" />
          <ellipse cy="-5" rx="40" ry="19" fill="url(#sc-grain)" />
          <ellipse cy="-5" rx="37" ry="17" fill="none" stroke="#adb9c7" opacity=".28" strokeWidth=".5" />
          <path d="M-31-17Q-18-26 3-23M-39-8Q-39-15-33-17" fill="none" stroke="url(#sc-frost)" strokeWidth="2.4" strokeLinecap="round" />
          <path d="M-13-17l3 5 6-2 5 6M18 1l-3-5 4-5M-24 1l6 3 2 5" fill="none" stroke="#18232e" opacity=".5" strokeWidth=".55" />
          {Array.from({ length: 45 }, (_, i) => {
            const a = i * 2.39996, r = .63 + ((i * 17) % 31) / 100
            return <ellipse key={i} cx={Math.cos(a) * 39 * r} cy={-5 + Math.sin(a) * 18 * r} rx={.4 + i % 3 * .25} ry={.3 + i % 2 * .15} fill={i % 4 ? '#c6ddeb' : '#fff'} opacity={.25 + (i % 5) * .1} />
          })}
          <path d="M-39-2l1 9M-35 3l1 10M-29 8v5M32 7l-1 7" stroke="url(#sc-frost)" strokeWidth="1" opacity=".65" />
        </g>
        <MagneticField />
      </g>
    </svg>
    <div className="sc-scene-meta">
      <span className="sc-state" aria-live="polite"><span className="sc-state-dot" />{parked ? copy.parked : atLimit ? copy.maxSpeed : stopAngle !== null ? copy.stopping : copy.orbitLabel}</span>
      <div className="sc-scene-actions">
        <span className="sc-temperature">T &lt; T<sub>c</sub></span>
        <IconButton size="small" aria-label={running ? copy.pause : copy.play} onClick={() => { if (parked) push(); else setChoice(!(choice ?? !reduced)) }}>
          {running ? <PauseRounded fontSize="small" /> : <PlayArrowRounded fontSize="small" />}
        </IconButton>
      </div>
    </div>
    <div className="sc-field-legend"><span><i className="sc-field-key" />{copy.fieldLegend}</span><span><i className="sc-current-key" />{copy.currentLegend}</span><span className="sc-meissner-caption">{copy.meissnerCaption}</span></div>
    <p className="sc-orbit-hint">{copy.orbitHint}</p>
    <details className="sc-science"><summary>{copy.science}</summary><p>{copy.scienceText}</p></details>
  </div>
}
