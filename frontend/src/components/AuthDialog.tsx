import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Typography, Tabs, Tab, Box, IconButton,
  InputAdornment, CircularProgress, Alert,
} from '@mui/material'
import {
  Visibility, VisibilityOff, Close, Login as LoginIcon,
} from '@mui/icons-material'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import UsernameField from './UsernameField'

type Step = 'form' | 'verify' | 'done'

interface Props {
  open: boolean
  onClose: () => void
}

const AuthDialog: React.FC<Props> = ({ open, onClose }) => {
  const { login, register, verifyEmail, resendVerification } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()

  // tab
  const [tab, setTab] = useState(0)  // 0=login, 1=register

  // login
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [showLoginPw, setShowLoginPw] = useState(false)

  // register
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regUsername, setRegUsername] = useState('')
  const [regRealName, setRegRealName] = useState('')
  const [showRegPw, setShowRegPw] = useState(false)

  // verify
  const [verifyCode, setVerifyCode] = useState('')
  const [resendSeconds, setResendSeconds] = useState(60)
  const [codeSent, setCodeSent] = useState(false)

  // shared
  const [step, setStep] = useState<Step>('form')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [doneMessage, setDoneMessage] = useState('')

  const reset = () => {
    setStep('form')
    setTab(0)
    setLoginEmail(''); setLoginPassword(''); setShowLoginPw(false)
    setRegEmail(''); setRegPassword(''); setRegUsername(''); setRegRealName(''); setShowRegPw(false)
    setVerifyCode('')
    setCodeSent(false)
    setResendSeconds(0)
    setError('')
    setDoneMessage('')
  }

  useEffect(() => {
    if (step !== 'verify' || resendSeconds <= 0) return
    const timer = window.setTimeout(() => setResendSeconds(value => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [resendSeconds, step])

  const handleClose = () => {
    reset()
    onClose()
  }

  /**
   * 错误消息映射：AuthContext 抛出的 Error.message 是机器键（如 'loginFailed'），
   * 此处映射为 `account.*` 字典文案（随语言切换）；非机器键（如 api 层原文）原样显示。
   */
  const errorText = (error: unknown): string => {
    const message = (error as Error).message
    const key = `account.${message}`
    const mapped = t(key)
    return mapped === key ? message : mapped
  }

  // ── Login ─────────────────────────────────────────
  const handleLogin = async () => {
    setError('')
    if (!loginEmail || !loginPassword) { setError(t('account.fillEmailPassword')); return }
    setLoading(true)
    try {
      const result = await login(loginEmail, loginPassword)
      if (result.needApproval) {
        setDoneMessage(t('account.loginApprovalPending'))
        setStep('done')
      } else {
        handleClose()
      }
    } catch (e: unknown) {
      if ((e as { code?: string }).code === 'email_not_verified') {
        setRegEmail(loginEmail)
        setRegPassword(loginPassword)
        setVerifyCode('')
        setCodeSent(false)
        setResendSeconds(0)
        setStep('verify')
      }
      setError(errorText(e) || t('account.loginFailed'))
    } finally {
      setLoading(false)
    }
  }

  // ── Register → verify ─────────────────────────────
  const handleRegister = async () => {
    setError('')
    if (!regEmail || !regPassword || !regUsername) { setError(t('account.fillRegisterFields')); return }
    if (regPassword.length < 10) { setError(t('account.passwordTooShort')); return }
    setLoading(true)
    try {
      const result = await register(regEmail, regPassword, regUsername, regRealName)
      if (result.requiresEmailVerification) {
        setResendSeconds(result.resendAfterSeconds ?? 60)
        setCodeSent(true)
        setStep('verify')
      } else {
        await login(regEmail, regPassword)
        handleClose()
        navigate('/account')
      }
    } catch (e: unknown) {
      const failure = e as { requiresEmailVerification?: boolean; resendAfterSeconds?: number }
      if (failure.requiresEmailVerification) {
        setCodeSent(false)
        setResendSeconds(failure.resendAfterSeconds ?? 60)
        setStep('verify')
      }
      setError(errorText(e) || t('account.registerFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async () => {
    setError('')
    if (!/^\d{6}$/.test(verifyCode)) { setError(t('account.enterCode')); return }
    setLoading(true)
    try {
      await verifyEmail(regEmail, verifyCode)
      handleClose()
      navigate('/account')
    } catch (e: unknown) {
      setError(errorText(e) || t('account.verifyFailed'))
    } finally {
      setLoading(false)
    }
  }

  // ═══════════════════════════════════════════════════
  // Render helpers
  // ═══════════════════════════════════════════════════
  const loginForm = (
    <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}
         onSubmit={e => { e.preventDefault(); handleLogin() }}>
      <fieldset disabled={loading} style={{ border: 0, padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <TextField
        label={t('account.email')} type="email" autoFocus fullWidth size="small"
        value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
      />
      <TextField
        label={t('account.password')} type={showLoginPw ? 'text' : 'password'} fullWidth size="small"
        value={loginPassword} onChange={e => setLoginPassword(e.target.value)}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => setShowLoginPw(!showLoginPw)} edge="end">
                {showLoginPw ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      {error && <Alert severity="error" sx={{ py: 0 }}>{error}</Alert>}
      <Button
        variant="contained" fullWidth type="submit" disabled={loading}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <LoginIcon />}
      >
        {t('nav.login')}
      </Button>
      </fieldset>
    </Box>
  )

  const registerForm = (
    <Box component="form" sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}
         onSubmit={e => { e.preventDefault(); handleRegister() }}>
      <fieldset disabled={loading} style={{ border: 0, padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <UsernameField value={regUsername} onChange={setRegUsername} autoFocus />
      <TextField
        label={t('account.realNameOptional')} fullWidth size="small"
        value={regRealName} onChange={e => setRegRealName(e.target.value)}
      />
      <TextField
        label={t('account.email')} type="email" fullWidth size="small"
        value={regEmail} onChange={e => setRegEmail(e.target.value)}
      />
      <TextField
        label={t('account.password')} type={showRegPw ? 'text' : 'password'} fullWidth size="small"
        value={regPassword} onChange={e => setRegPassword(e.target.value)}
        helperText={t('account.passwordMinHint')}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => setShowRegPw(!showRegPw)} edge="end">
                {showRegPw ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      {error && <Alert severity="error" sx={{ py: 0 }}>{error}</Alert>}
      <Button
        variant="outlined" fullWidth type="submit" disabled={loading}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {t('account.register')}
      </Button>
      </fieldset>
    </Box>
  )

  const verifyStep = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1, alignItems: 'center' }}>
      <Alert severity="info" sx={{ width: '100%' }}>
        {codeSent ? t('account.codeSentBefore') : t('account.continueVerificationBefore')} <strong>{regEmail}</strong>{codeSent ? t('account.codeSentAfter') : t('account.continueVerificationAfter')}
      </Alert>
      <TextField
        disabled={loading} label={t('account.codeLabel')} autoFocus fullWidth size="small"
        value={verifyCode} onChange={e => setVerifyCode(e.target.value)}
        inputProps={{ maxLength: 6, inputMode: 'numeric', autoComplete: 'one-time-code' }}
        sx={{ maxWidth: 220 }}
      />
      {error && <Alert severity="error" sx={{ py: 0, width: '100%' }}>{error}</Alert>}
      <Button
        variant="contained" fullWidth sx={{ maxWidth: 220 }}
        onClick={handleVerify} disabled={loading}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {t('account.verify')}
      </Button>
      <Button
        size="small"
        disabled={loading || resendSeconds > 0}
        onClick={async () => {
          setError('')
          setLoading(true)
          try {
            const seconds = await resendVerification(regEmail, regPassword)
            setResendSeconds(seconds)
            setCodeSent(true)
          } catch (e: unknown) {
            setResendSeconds((e as { resendAfterSeconds?: number }).resendAfterSeconds ?? 0)
            setError(errorText(e) || t('account.resendFailed'))
          } finally {
            setLoading(false)
          }
        }}
      >
        {resendSeconds > 0 ? t('account.resendIn', { seconds: resendSeconds }) : t('account.resendCode')}
      </Button>
    </Box>
  )

  const doneStep = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1, alignItems: 'center' }}>
      <Alert severity="success" sx={{ width: '100%' }}>{doneMessage}</Alert>
      <Button variant="contained" onClick={handleClose} sx={{ minWidth: 120 }}>
        {t('common.close')}
      </Button>
    </Box>
  )

  // ═══════════════════════════════════════════════════
  return (
    <Dialog open={open} onClose={() => { if (!loading) handleClose() }} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 0, fontSize: '1.25rem', fontWeight: 600 }}>
        <Box component="span">
          {step === 'verify' ? t('account.verifyEmailTitle') : step === 'done' ? t('account.done') : t('account.authTitle')}
        </Box>
        <IconButton size="small" disabled={loading} onClick={handleClose}><Close fontSize="small" /></IconButton>
      </DialogTitle>

      <DialogContent>
        {step === 'form' && (
          <>
            <Tabs value={tab} onChange={(_, v) => { setTab(v); setError('') }}
                  variant="fullWidth" sx={{ mb: 1 }}>
              <Tab disabled={loading} label={t('nav.login')} />
              <Tab disabled={loading} label={t('account.register')} />
            </Tabs>
            {tab === 0 ? loginForm : registerForm}
          </>
        )}
        {step === 'verify' && verifyStep}
        {step === 'done' && doneStep}
      </DialogContent>

      {step === 'form' && (
        <DialogActions sx={{ justifyContent: 'center', pb: 2 }}>
          <Typography variant="caption" color="text.disabled">
            {tab === 0 ? t('account.switchToRegisterHint') : t('account.switchToLoginHint')}
          </Typography>
        </DialogActions>
      )}
    </Dialog>
  )
}

export default AuthDialog
