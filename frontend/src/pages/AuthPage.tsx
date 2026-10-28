import React, { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import AuthExperience from '../features/auth/AuthExperience'
import { createProductionAuth } from '../features/auth/productionService'
import { safeAuthReturnTo } from '../lib/authNavigation'

export default function AuthPage() {
  const { user, loading, login, register, verifyEmail, resendVerification } = useAuth()
  const [localAuthentication, setLocalAuthentication] = useState<'idle' | 'pending' | 'complete'>('idle')
  const { t } = useLanguage()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = safeAuthReturnTo(new URLSearchParams(location.search).get('returnTo'))
  const service = useMemo(() => {
    // 本页认证仍由原成功回调跳转，保留注册默认进入用户中心的规则。
    const locally = async <T,>(action: () => Promise<T>): Promise<T> => {
      setLocalAuthentication('pending')
      try {
        const result = await action()
        setLocalAuthentication('complete')
        return result
      } catch (error) {
        setLocalAuthentication('idle')
        throw error
      }
    }
    return createProductionAuth({
      login: (email, password) => locally(() => login(email, password)),
      register,
      verifyEmail: (email, code) => locally(() => verifyEmail(email, code)),
      resendVerification,
    })
  }, [login, register, verifyEmail, resendVerification])
  useEffect(() => {
    if (user && !loading && localAuthentication === 'idle') {
      navigate(returnTo || '/news', { replace: true })
    }
  }, [user, loading, localAuthentication, navigate, returnTo])
  return <AuthExperience auth={service} sourceLabel={t('common.back')}
    onExit={() => navigate(returnTo || '/news', { replace: true })}
    onAuthenticated={registered => navigate(returnTo || (registered ? '/account' : '/news'), { replace: true })} />
}
