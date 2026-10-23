import React, { useEffect, useState } from 'react'
import { Alert, Box, Button, Collapse, Stack, TextField, Typography } from '@mui/material'
import { Check, ExpandMore, LockOutlined } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { api, type ApiError } from '../lib/api'

export default function AccountSecurity() {
  const { t } = useLanguage()
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [nextSend, setNextSend] = useState(0)
  const [expires, setExpires] = useState(0)
  const [now, setNow] = useState(Date.now())
  const seconds = Math.max(0, Math.ceil((nextSend - now) / 1000))
  useEffect(() => {
    if (!nextSend && !expires) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [nextSend, expires])
  const reset = () => {
    setSent(false); setCurrentPassword(''); setEmail(''); setCode(''); setPassword(''); setConfirm(''); setError(''); setExpires(0)
  }
  const failed = (cause: unknown) => {
    const failure = cause as ApiError
    setError(failure.message)
    const wait = Number((failure.detail as { resend_after_seconds?: number } | undefined)?.resend_after_seconds)
    if (wait > 0) { setNextSend(Date.now() + wait * 1000); setNow(Date.now()) }
  }
  const send = async () => {
    if (busy || seconds > 0) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ resend_after_seconds: number; expires_in_seconds: number }>('/api/account/password-change-code', { current_password: currentPassword, email: email.trim() })
      const timestamp = Date.now()
      setNextSend(timestamp + result.resend_after_seconds * 1000)
      setExpires(timestamp + result.expires_in_seconds * 1000)
      setNow(timestamp); setCode(''); setSent(true)
    } catch (cause) { failed(cause) } finally { setBusy(false) }
  }
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (busy) return
    if (!sent) { await send(); return }
    if (password !== confirm) { setError(t('account.passwordMismatch')); return }
    if (password === currentPassword) { setError(t('account.passwordUnchanged')); return }
    if (Date.now() >= expires) { setError(t('account.codeExpired')); return }
    setBusy(true); setError('')
    try {
      await api.post('/api/account/change-password', { current_password: currentPassword, email: email.trim(), code, new_password: password })
      reset(); logout(); navigate('/news')
    } catch (cause) { failed(cause) } finally { setBusy(false) }
  }
  return <section className="account-card account-security">
    <button type="button" className="account-security-toggle" disabled={busy} aria-expanded={open} onClick={() => { reset(); setOpen(!open) }}>
      <span className="account-section-icon"><LockOutlined /></span><span><b>{t('account.securitySection')}</b><small>{t('account.securityHint')}</small></span><ExpandMore sx={{ ml: 'auto', transform: open ? 'rotate(180deg)' : undefined }} />
    </button>
    <Collapse in={open} unmountOnExit><Box component="form" onSubmit={event => void submit(event)} className="account-password-form">
      <Stack direction="row" spacing={3} sx={{ mb: 2 }}><Typography color={!sent ? 'primary' : 'text.secondary'}>{sent ? <Check fontSize="small" /> : '1.'} {t('account.verifyIdentity')}</Typography><Typography color={sent ? 'primary' : 'text.secondary'}>2. {t('account.setNewPassword')}</Typography></Stack>
      {!sent ? <><Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t('account.passwordIdentityHint')}</Typography><div className="account-security-fields">
        <TextField label={t('account.currentPassword')} required type="password" autoComplete="current-password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} disabled={busy} />
        <TextField label={t('account.boundEmail')} required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} disabled={busy} />
      </div></> : <>
        <Alert severity="success" sx={{ mb: 2, overflowWrap: 'anywhere' }}>{t('account.passwordCodeSent', { email: email.trim() })}</Alert>
        <div className="account-code-row"><TextField label={t('account.emailCode')} required value={code} onChange={e => setCode(e.target.value)} autoComplete="one-time-code" inputProps={{ inputMode: 'numeric', pattern: '[0-9]{6}', maxLength: 6 }} disabled={busy} /><Button type="button" variant="outlined" disabled={busy || seconds > 0} onClick={() => void send()}>{seconds > 0 ? t('account.resendCountdown', { seconds }) : t('account.resendCode')}</Button></div>
        <div className="account-security-fields"><TextField label={t('account.newPassword')} required type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} inputProps={{ minLength: 10 }} disabled={busy} helperText={t('account.passwordMinHint')} /><TextField label={t('account.confirmPassword')} required type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} inputProps={{ minLength: 10 }} disabled={busy} /></div>
        {now >= expires && <Alert severity="warning" sx={{ mt: 2 }}>{t('account.codeExpired')}</Alert>}
      </>}
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      <Stack direction="row" justifyContent="flex-end" gap={1} sx={{ mt: 3 }}><Button disabled={busy} onClick={() => { reset(); setOpen(false) }}>{t('common.cancel')}</Button>{sent && <Button disabled={busy} onClick={reset}>{t('account.verifyAgain')}</Button>}<Button type="submit" variant="contained" disabled={busy || (!sent && (!currentPassword || !email || seconds > 0))}>{busy ? t('account.processing') : sent ? t('account.verifyAndChange') : seconds > 0 ? t('account.resendCountdown', { seconds }) : t('account.verifyAndSend')}</Button></Stack>
    </Box></Collapse>
  </section>
}
