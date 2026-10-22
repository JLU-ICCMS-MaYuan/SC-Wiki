import React, { useEffect, useRef, useState } from 'react'
import { Alert, Button, CircularProgress, IconButton } from '@mui/material'
import { ArrowBackRounded, ArrowForwardRounded, CheckRounded, EmailOutlined, LanguageRounded, PersonOutlineRounded, UploadFileOutlined, VisibilityOutlined, VisibilityOffOutlined } from '@mui/icons-material'
import { useLanguage } from '../../context/LanguageContext'
import { usernameValidationError } from '../../lib/username'
import { authDemoCopy } from './copy'
import { createDemoAuth, DEMO_PASSWORD, type DemoError } from './mockAuth'
import SuperconductorScene from './SuperconductorScene'

type Step = 'login' | 'register' | 'verify' | 'done'
const initialView = () => new URLSearchParams(window.location.search).get('view') === 'entry'

export default function AuthDemo() {
  const { lang, setLang } = useLanguage()
  const c = authDemoCopy[lang]
  const [auth] = useState(createDemoAuth)
  const [entry, setEntry] = useState(initialView)
  const [source, setSource] = useState(new URLSearchParams(window.location.search).get('from') === 'upload' ? 'upload' : 'news')
  const [step, setStep] = useState<Step>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [realName, setRealName] = useState('')
  const [code, setCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<DemoError | ''>('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [resendAt, setResendAt] = useState(0)
  const [seconds, setSeconds] = useState(0)
  const [registered, setRegistered] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const firstRender = useRef(true)
  const alive = useRef(true)

  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return }
    // 切换标签时保留标签焦点，步骤完成/返回入口时把读屏焦点移到标题。
    if (entry || (step !== 'login' && step !== 'register')) heading.current?.focus()
  }, [step, entry])
  useEffect(() => {
    const update = () => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)))
    update()
    if (!resendAt || step !== 'verify') return
    const timer = window.setInterval(update, 250)
    return () => window.clearInterval(timer)
  }, [resendAt, step])
  useEffect(() => {
    const onPop = () => {
      setEntry(initialView()); setStep('login'); setError(''); setPassword('')
      setSource(new URLSearchParams(window.location.search).get('from') === 'upload' ? 'upload' : 'news')
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const goEntry = () => {
    window.history.pushState({}, '', `${window.location.pathname}?view=entry`)
    setEntry(true); setStep('login'); setError(''); setPassword(''); setCode(''); setShowPassword(false)
  }
  const enter = (from: string) => {
    window.history.pushState({}, '', `${window.location.pathname}?from=${from}`)
    setSource(from); setEntry(false); setStep('login'); setError('')
  }
  const changeStep = (next: Step) => { setStep(next); setError(''); setShowPassword(false); setCode('') }
  const readyCode = () => { setSent(true); setSeconds(60); setResendAt(Date.now() + 60_000) }
  const run = async (action: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError('')
    try { await action() } catch (err) {
      if (alive.current) setError((err as Error).message as DemoError)
    } finally { if (alive.current) setBusy(false) }
  }
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    void run(async () => {
      if (step === 'login') {
        setRegistered(false)
        try { await auth.login(email, password) } catch (err) {
          if ((err as Error).message === 'unverified' && alive.current) {
            setSent(false); setResendAt(0); setCode(''); setStep('verify')
          }
          throw err
        }
      } else if (step === 'register') {
        await auth.register({ email, password, username, realName })
        if (!alive.current) return
        setRegistered(true); readyCode(); setStep('verify'); return
      } else if (step === 'verify') {
        if (!/^\d{6}$/.test(code)) throw new Error('invalidCode')
        await auth.verify(email, code)
      }
      if (alive.current) { setPassword(''); setCode(''); setStep('done') }
    })
  }
  const title = step === 'login' ? c.welcome : step === 'register' ? c.join : step === 'verify' ? c.verifyTitle : registered ? c.successRegister : c.successLogin
  const primary = step === 'login' ? c.login : step === 'register' ? c.create : c.verify
  const fill = (unverified: boolean) => {
    setEmail(unverified ? 'unverified@example.com' : 'researcher@example.com')
    setPassword(DEMO_PASSWORD); setStep('login'); setError('')
  }

  return <div className="sc-auth-demo">
    <header className="sc-auth-header">
      <a className="sc-brand" href="?view=entry" onClick={event => { event.preventDefault(); if (!busy) goEntry() }} aria-label="SC-Wiki">
        <span className="sc-brand-mark">sc<span>.</span></span><span className="sc-brand-name">SC-Wiki<span>{c.brandSub}</span></span>
      </a>
      <nav className="sc-header-actions" aria-label={c.back}>
        {!entry && <Button color="inherit" size="small" startIcon={<ArrowBackRounded />} onClick={goEntry} disabled={busy}>{source === 'upload' ? c.returnUpload : c.returnNews}</Button>}
        <Button color="inherit" size="small" startIcon={<LanguageRounded />} onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>{c.language}</Button>
      </nav>
    </header>

    {entry ? <main className="sc-entry">
      <span className="sc-eyebrow">{c.entryBadge}</span>
      <h1 ref={heading} tabIndex={-1}>{c.entryTitle}</h1><p>{c.entryText}</p>
      <div className="sc-entry-buttons">
        <Button variant="contained" startIcon={<PersonOutlineRounded />} endIcon={<ArrowForwardRounded />} onClick={() => enter('news')}>{c.sidebarEntry}</Button>
        <Button variant="outlined" startIcon={<UploadFileOutlined />} endIcon={<ArrowForwardRounded />} onClick={() => enter('upload')}>{c.uploadEntry}</Button>
      </div>
      <a className="sc-live-link" href="/news">SC-Wiki ↗</a>
    </main> : <main className="sc-auth-main">
      <section className="sc-visual" aria-label={c.eyebrow}>
        <div className="sc-hero-copy"><div className="sc-eyebrow"><span />{c.eyebrow}</div>
          <h2>{c.heroFirst}<br />{lang === 'en' ? ' ' : null}<span>{c.heroSecond}</span></h2>
          <p>{c.heroText}<br /><span>{c.heroDetail}</span></p>
        </div>
        <SuperconductorScene copy={c} />
      </section>

      <section className="sc-form-section" aria-labelledby="auth-title">
        <div className="sc-form-content">
          {(step === 'login' || step === 'register') && <div className="sc-tabs" role="tablist" aria-label={`${c.login} / ${c.register}`}>
            {(['login', 'register'] as const).map((tab, index) => <button key={tab} id={`tab-${tab}`} role="tab" type="button" disabled={busy}
              aria-selected={step === tab} aria-controls="auth-panel" tabIndex={step === tab ? 0 : -1}
              onClick={() => changeStep(tab)} onKeyDown={event => {
                if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
                  event.preventDefault()
                  const next = event.key === 'Home' ? 'login' : event.key === 'End' ? 'register' : index === 0 ? 'register' : 'login'
                  changeStep(next); document.getElementById(`tab-${next}`)?.focus()
                }
              }}>{c[tab]}</button>)}
          </div>}

          <div id="auth-panel" role={step === 'login' || step === 'register' ? 'tabpanel' : undefined}
            aria-labelledby={step === 'login' || step === 'register' ? `tab-${step}` : undefined}>
            {step === 'verify' && <div className="sc-step-symbol"><EmailOutlined /></div>}
            {step === 'done' && <div className="sc-step-symbol sc-success-symbol"><CheckRounded /></div>}
            <h1 id="auth-title" ref={heading} tabIndex={-1}>{title}</h1>
            <p className="sc-form-intro">{step === 'login' ? c.welcomeText : step === 'register' ? c.joinText : step === 'verify' ? <>{c.verifyText}<br /><strong>{email}</strong></> : c.successText}</p>

            {step !== 'done' ? <form onSubmit={submit}>
              <fieldset disabled={busy}>
                {step === 'register' && <div className="sc-field"><label htmlFor="demo-username">{c.username}</label>
                  <input id="demo-username" autoComplete="username" required maxLength={32} value={username} onChange={event => { setUsername(event.target.value); if (error === 'invalidUsername') setError('') }}
                    onBlur={() => { if (username && usernameValidationError(username)) setError('invalidUsername') }} aria-describedby="username-hint" aria-invalid={error === 'invalidUsername'} />
                  <span className="sc-field-hint" id="username-hint">{c.usernameHint}</span>
                </div>}
                {step !== 'verify' ? <>
                  <div className="sc-field"><label htmlFor="demo-email">{c.email}</label>
                    <input id="demo-email" name="email" type="email" autoComplete="email" required placeholder="you@university.edu" value={email} onChange={event => setEmail(event.target.value)} />
                  </div>
                  <div className="sc-field"><label htmlFor="demo-password">{c.password}</label>
                    <div className="sc-password"><input id="demo-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={step === 'login' ? 'current-password' : 'new-password'} required
                      minLength={step === 'register' ? 10 : undefined} value={password} onChange={event => setPassword(event.target.value)} aria-describedby={step === 'register' ? 'password-hint' : undefined} />
                      <IconButton size="small" aria-label={showPassword ? c.hidePassword : c.showPassword} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>
                        {showPassword ? <VisibilityOffOutlined fontSize="small" /> : <VisibilityOutlined fontSize="small" />}
                      </IconButton>
                    </div>
                    {step === 'register' && <span className="sc-field-hint" id="password-hint">{c.passwordHint}</span>}
                  </div>
                  {step === 'register' && <div className="sc-field"><label htmlFor="demo-real-name">{c.realName}</label>
                    <input id="demo-real-name" autoComplete="name" value={realName} onChange={event => setRealName(event.target.value)} aria-describedby="real-name-hint" />
                    <span className="sc-field-hint" id="real-name-hint">{c.realNameHint}</span>
                  </div>}
                </> : <>
                  <div className="sc-code-notice" role="status">{sent ? c.codeSent : c.codeNotSent}</div>
                  <div className="sc-field"><label htmlFor="demo-code">{c.code}</label>
                    <input className="sc-code-input" id="demo-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required maxLength={6}
                      value={code} onChange={event => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} />
                  </div>
                </>}
                {error && <Alert severity="error" className="sc-form-error">{c.errors[error] || c.errors.credentials}</Alert>}
                <Button className="sc-submit" variant="contained" type="submit" fullWidth disabled={busy} endIcon={busy ? <CircularProgress size={17} color="inherit" /> : <ArrowForwardRounded />}>
                  {busy ? c.busy : primary}
                </Button>
                {step === 'verify' && <Button className="sc-resend" fullWidth disabled={busy || seconds > 0}
                  onClick={() => void run(async () => { await auth.resend(email); if (alive.current) readyCode() })}>
                  {seconds > 0 ? lang === 'zh' ? `${seconds} ${c.resendIn}` : `${c.resendIn} ${seconds}s` : c.resend}
                </Button>}
              </fieldset>
            </form> : <Button variant="contained" className="sc-submit" fullWidth endIcon={<ArrowForwardRounded />} onClick={goEntry}>{c.successAction}</Button>}

            {step === 'verify' && <Button className="sc-back-login" color="inherit" size="small" disabled={busy} startIcon={<ArrowBackRounded />} onClick={() => changeStep('login')}>{c.backLogin}</Button>}
            {(step === 'login' || step === 'register') && <p className="sc-email-only"><EmailOutlined />{c.emailOnly}</p>}
          </div>

          <div className="sc-demo-note"><span>{c.demo}</span>
            <details><summary>{c.demoDetails}</summary><p>{c.demoHint}</p>
              <div><Button size="small" disabled={busy} onClick={() => fill(false)}>{c.fillDemo}</Button><Button size="small" disabled={busy} onClick={() => fill(true)}>{c.fillUnverified}</Button></div>
            </details>
          </div>
        </div>
      </section>
    </main>}
    <footer className="sc-auth-footer"><span>SC-Wiki <span className="sc-footer-dot">/</span> {c.footer}</span><span>{c.concept} <span className="sc-footer-dot">·</span> 01</span></footer>
  </div>
}
