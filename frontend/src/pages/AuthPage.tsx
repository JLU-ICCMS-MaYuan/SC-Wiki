import React, { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import AuthExperience from '../features/auth/AuthExperience'
import { createProductionAuth } from '../features/auth/productionService'
import { safeAuthReturnTo } from '../lib/authNavigation'

export default function AuthPage() {
  const { login, register, verifyEmail, resendVerification } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = safeAuthReturnTo(new URLSearchParams(location.search).get('returnTo'))
  const service = useMemo(() => createProductionAuth({ login, register, verifyEmail, resendVerification }), [login, register, verifyEmail, resendVerification])
  return <AuthExperience auth={service} sourceLabel={t('common.back')}
    onExit={() => navigate(returnTo || '/news', { replace: true })}
    onAuthenticated={registered => navigate(returnTo || (registered ? '/account' : '/news'), { replace: true })} />
}
