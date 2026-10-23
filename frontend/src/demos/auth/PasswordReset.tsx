import React, { useEffect, useRef, useState } from 'react'
import { Alert, Button, CircularProgress, IconButton } from '@mui/material'
import { ArrowBackRounded, ArrowForwardRounded, CheckRounded, EmailOutlined, LockOutlined, VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material'
import type { AuthDemoCopy } from './copy'
import type { createDemoAuth, DemoError } from './mockAuth'

interface Props {
  auth: ReturnType<typeof createDemoAuth>
  copy: AuthDemoCopy
  lang: 'zh' | 'en'
  initialEmail: string
  onBack: (email: string) => void
}

export default function PasswordReset({ auth, copy: c, lang, initialEmail, onBack }: Props) {
  const [step, setStep] = useState<'email' | 'code' | 'password' | 'success'>('email')
  const [email, setEmail] = useState(initialEmail)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [show, setShow] = useState(false)
  const [grant, setGrant] = useState('')
  const [error, setError] = useState<DemoError | ''>('')
  const [busy, setBusy] = useState(false)
  const [resendAt, setResendAt] = useState(0)
  const [seconds, setSeconds] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  const alive = useRef(true)
  const currentEmail = useRef(email)
  currentEmail.current = email

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; auth.cancelPasswordReset(currentEmail.current) }
  }, [auth])
  useEffect(() => { heading.current?.focus() }, [step])
  useEffect(() => {
    const update = () => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)))
    update()
    if (!resendAt || step !== 'code') return
    const timer = window.setInterval(update, 250)
    return () => window.clearInterval(timer)
  }, [resendAt, step])

  const run = async (work: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError('')
    try { await work() } catch (err) {
      if (alive.current) setError((err as Error).message as DemoError)
    } finally { if (alive.current) setBusy(false) }
  }
  const requestCode = async () => {
    await auth.requestPasswordReset(email)
    if (!alive.current) return
    setResendAt(Date.now() + 60_000); setSeconds(60); setStep('code'); setCode('')
  }
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    void run(async () => {
      if (step === 'email') await requestCode()
      else if (step === 'code') {
        const result = await auth.verifyPasswordReset(email, code)
        if (!alive.current) { auth.cancelPasswordReset(email); return }
        setGrant(result); setCode(''); setStep('password')
      } else if (step === 'password') {
        if (password !== confirmation) throw new Error('passwordMismatch')
        await auth.resetPassword(email, grant, password)
        if (!alive.current) return
        setGrant(''); setPassword(''); setConfirmation(''); setStep('success')
      }
    })
  }
  const stage = ['email', 'code', 'password', 'success'].indexOf(step)
  const title = step === 'email' ? c.resetTitle : step === 'code' ? c.resetCodeTitle : step === 'password' ? c.newPasswordTitle : c.resetSuccess

  return <div className="sc-reset-panel">
    <div className="sc-reset-progress" aria-hidden="true">{[0, 1, 2].map(n => <span key={n} className={n <= stage ? 'is-complete' : ''} />)}</div>
    <div className={`sc-step-symbol ${step === 'success' ? 'sc-success-symbol' : ''}`}>
      {step === 'success' ? <CheckRounded /> : step === 'password' ? <LockOutlined /> : <EmailOutlined />}
    </div>
    <h1 id="auth-title" ref={heading} tabIndex={-1}>{title}</h1>
    <p className="sc-form-intro">{step === 'email' ? c.resetIntro : step === 'code' ? <>{c.resetCodeIntro}<br /><strong>{email}</strong></> : step === 'password' ? c.newPasswordIntro : c.resetSuccessText}</p>
    {step === 'success' ? <Button className="sc-submit" variant="contained" fullWidth endIcon={<ArrowForwardRounded />} onClick={() => onBack(email)}>{c.backLogin}</Button> : <>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          {step === 'email' && <div className="sc-field"><label htmlFor="reset-email">{c.email}</label>
            <input id="reset-email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="you@university.edu" />
          </div>}
          {step === 'code' && <>
            <div className="sc-code-notice" role="status">{c.resetDemoHint}</div>
            <div className="sc-field"><label htmlFor="reset-code">{c.code}</label>
              <input id="reset-code" className="sc-code-input" inputMode="numeric" autoComplete="one-time-code" required pattern="[0-9]{6}" maxLength={6} value={code} onChange={event => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} />
            </div>
          </>}
          {step === 'password' && <>
            <div className="sc-field"><label htmlFor="reset-password">{c.newPassword}</label>
              <div className="sc-password"><input id="reset-password" type={show ? 'text' : 'password'} autoComplete="new-password" required minLength={10} value={password} onChange={event => setPassword(event.target.value)} aria-describedby="reset-password-hint" />
                <IconButton size="small" aria-label={show ? c.hidePassword : c.showPassword} aria-pressed={show} onClick={() => setShow(!show)}>{show ? <VisibilityOffOutlined fontSize="small" /> : <VisibilityOutlined fontSize="small" />}</IconButton>
              </div><span id="reset-password-hint" className="sc-field-hint">{c.passwordHint}</span>
            </div>
            <div className="sc-field"><label htmlFor="reset-confirm">{c.confirmPassword}</label>
              <input id="reset-confirm" type={show ? 'text' : 'password'} autoComplete="new-password" required minLength={10} value={confirmation} onChange={event => setConfirmation(event.target.value)} aria-invalid={error === 'passwordMismatch'} />
            </div>
          </>}
          {error && <Alert severity="error" className="sc-form-error">{c.errors[error] || c.errors.expired}</Alert>}
          <Button className="sc-submit" variant="contained" fullWidth type="submit" disabled={busy} endIcon={busy ? <CircularProgress size={17} color="inherit" /> : <ArrowForwardRounded />}>
            {busy ? c.busy : step === 'email' ? c.sendReset : step === 'code' ? c.verify : c.savePassword}
          </Button>
          {step === 'code' && <Button className="sc-resend" fullWidth disabled={busy || seconds > 0} onClick={() => void run(requestCode)}>
            {seconds > 0 ? lang === 'zh' ? `${seconds} ${c.resendIn}` : `${c.resendIn} ${seconds}s` : c.resend}
          </Button>}
        </fieldset>
      </form>
      <Button className="sc-back-login" size="small" color="inherit" disabled={busy} startIcon={<ArrowBackRounded />} onClick={() => onBack(email)}>{c.backLogin}</Button>
      {step !== 'email' && <Button size="small" disabled={busy} onClick={() => {
        auth.cancelPasswordReset(email); setGrant(''); setPassword(''); setConfirmation(''); setError(''); setCode(''); setStep('email')
      }}>{c.changeEmail}</Button>}
    </>}
  </div>
}
