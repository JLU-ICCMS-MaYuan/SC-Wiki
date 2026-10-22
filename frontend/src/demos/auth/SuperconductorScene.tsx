import React, { useEffect, useRef, useState } from 'react'
import { IconButton } from '@mui/material'
import { PauseRounded, PlayArrowRounded } from '@mui/icons-material'
import type { AuthDemoCopy } from './copy'

const TAU = Math.PI * 2
const point = (angle: number, rx: number, ry: number, offset = 0) => `${360 + Math.cos(angle) * rx},${245 + Math.sin(angle) * ry + offset}`

export default function SuperconductorScene({ copy }: { copy: AuthDemoCopy }) {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  const [choice, setChoice] = useState<boolean | null>(null)
  const [visible, setVisible] = useState(!document.hidden)
  const running = (choice ?? !reduced) && visible
  const puck = useRef<SVGGElement>(null)
  const shadow = useRef<SVGEllipseElement>(null)
  const elapsed = useRef(0)

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
      const angle = 0.55 + elapsed.current / 16_000 * TAU
      const x = 360 + 244 * Math.cos(angle)
      const y = 245 + 98 * Math.sin(angle)
      const scale = 0.9 + 0.1 * Math.sin(angle)
      puck.current?.setAttribute('transform', `translate(${x} ${y - 42}) scale(${scale})`)
      puck.current?.setAttribute('data-phase', String(elapsed.current / 16_000))
      shadow.current?.setAttribute('cx', String(x))
      shadow.current?.setAttribute('cy', String(y + 2))
      shadow.current?.setAttribute('rx', String(39 * scale))
    }
    const tick = (now: number) => {
      if (last !== null) elapsed.current = (elapsed.current + now - last) % 16_000
      last = now
      draw()
      frame = requestAnimationFrame(tick)
    }
    draw()
    if (running) frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [running])

  return <div className="sc-scene">
    <svg className="sc-orbit" viewBox="0 65 720 345" role="img" aria-label={copy.sceneLabel}>
      <defs>
        <linearGradient id="sc-track" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e9e7fc" /><stop offset="1" stopColor="#b8b0ed" />
        </linearGradient>
        <linearGradient id="sc-puck-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#625b91" /><stop offset="1" stopColor="#30294e" />
        </linearGradient>
        <radialGradient id="sc-puck-top" cx="35%" cy="25%" r="80%">
          <stop offset="0" stopColor="#a7a0c7" /><stop offset="0.55" stopColor="#70688f" /><stop offset="1" stopColor="#4a426b" />
        </radialGradient>
        <filter id="sc-soft-shadow" x="-50%" y="-100%" width="200%" height="300%"><feGaussianBlur stdDeviation="5" /></filter>
      </defs>

      {/* 背景测量线与磁场示意保持低对比，视觉重心留给悬浮圆片。 */}
      <g fill="none" stroke="#e9eaf1" strokeWidth="1">
        <ellipse cx="360" cy="257" rx="316" ry="135" strokeDasharray="3 8" />
        <path d="M29 257H691M360 103V413" strokeDasharray="3 8" />
      </g>
      <ellipse cx="360" cy="273" rx="273" ry="109" fill="none" stroke="#c9c6dc" strokeWidth="19" opacity=".16" filter="url(#sc-soft-shadow)" />

      {/* 磁轨侧面、表面与内外边缘提供连续的透视深度。 */}
      <ellipse cx="360" cy="258" rx="246" ry="99" fill="none" stroke="#cbc6e8" strokeWidth="48" />
      <ellipse cx="360" cy="245" rx="246" ry="99" fill="none" stroke="url(#sc-track)" strokeWidth="48" />
      {Array.from({ length: 64 }, (_, i) => {
        const start = i / 64 * TAU + 0.012
        const end = (i + 1) / 64 * TAU - 0.012
        return <polygon key={i} points={`${point(start, 270, 111)} ${point(end, 270, 111)} ${point(end, 222, 87)} ${point(start, 222, 87)}`}
          fill={i % 2 ? '#efedf9' : '#d5d0f1'} stroke="#ffffff" strokeWidth=".7" />
      })}
      <ellipse cx="360" cy="245" rx="272" ry="113" fill="none" stroke="#aaa0d8" strokeWidth="1.5" />
      <ellipse cx="360" cy="245" rx="219" ry="86" fill="none" stroke="#c2bae6" strokeWidth="1.5" />
      <g fill="none" stroke="#aba3dd" strokeWidth="1" opacity=".35">
        <ellipse cx="360" cy="245" rx="247" ry="100" />
        <path d="M160 209C168 91 262 72 291 158M177 202C187 120 252 103 276 165M431 164C456 97 537 106 553 210" />
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

      <ellipse ref={shadow} cx="568" cy="298" rx="39" ry="10" fill="#4f46a1" opacity=".22" filter="url(#sc-soft-shadow)" />
      <g ref={puck} data-testid="superconductor-puck">
        {/* 绕过圆片的场线仅为示意，不表示磁场求解结果。 */}
        <g fill="none" stroke="#86c1d0" strokeWidth="1.2" opacity=".75">
          <path d="M-57 33C-75 13-66-19-47-24M57 33C75 13 66-19 47-24" />
          <path d="M-47 28C-59 11-56-10-43-16M47 28C59 11 56-10 43-16" />
        </g>
        <path d="M-38-5C-38-27 38-27 38-5V9C38 30-38 30-38 9Z" fill="url(#sc-puck-side)" />
        <ellipse cx="0" cy="-5" rx="38" ry="18" fill="url(#sc-puck-top)" stroke="#a29ab9" strokeWidth=".8" />
        <ellipse cx="-5" cy="-8" rx="26" ry="10" fill="none" stroke="#b7b0ce" opacity=".35" strokeWidth=".6" />
        <path d="M-29 11Q0 24 29 11" fill="none" stroke="#9690b5" strokeWidth=".7" opacity=".6" />
      </g>
    </svg>
    <div className="sc-scene-meta">
      <span className="sc-state"><span className="sc-state-dot" />{copy.orbitLabel}</span>
      <div className="sc-scene-actions">
        <span className="sc-temperature">T &lt; T<sub>c</sub></span>
        <IconButton size="small" aria-label={running ? copy.pause : copy.play} onClick={() => setChoice(!(choice ?? !reduced))}>
          {running ? <PauseRounded fontSize="small" /> : <PlayArrowRounded fontSize="small" />}
        </IconButton>
      </div>
    </div>
    <details className="sc-science"><summary>{copy.science}</summary><p>{copy.scienceText}</p></details>
  </div>
}
