import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'

export interface User {
  id: number
  email: string
  username: string
  username_change_allowed: boolean
  role: 'user' | 'admin' | 'superadmin'
  is_admin: boolean
  is_superadmin: boolean
  is_approved: boolean
  is_email_verified: boolean
  account_status: 'active' | 'banned' | 'deactivated'
  avatar_url?: string | null
  created_at: string | null
  approved_at: string | null
}

export interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<{ needApproval?: boolean }>
  register: (email: string, password: string, username: string, realName: string) => Promise<{ requiresEmailVerification: boolean; resendAfterSeconds?: number }>
  updateUsername: (username: string) => Promise<void>
  replaceUser: (user: User) => void
  verifyEmail: (email: string, code: string) => Promise<void>
  resendVerification: (email: string, password: string) => Promise<number>
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  loading: true,
  login: async () => ({}),
  register: async () => ({ requiresEmailVerification: false }),
  updateUsername: async () => {},
  replaceUser: () => {},
  verifyEmail: async () => {},
  resendVerification: async () => 60,
  logout: () => {},
})

export const useAuth = () => useContext(AuthContext)

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'
const REVISION_KEY = 'auth_session_revision'

interface SessionIdentity {
  token: string | null
  revision: string
}
interface Session extends SessionIdentity {
  user: User | null
}

function readIdentity(): SessionIdentity {
  return { token: getStoredToken(), revision: localStorage.getItem(REVISION_KEY) || '' }
}

function sameIdentity(a: SessionIdentity, b: SessionIdentity) {
  return a.token === b.token && a.revision === b.revision
}

function advanceRevision() {
  // 同秒重新登录可能拿到相同 JWT，仍须区分两次会话。
  localStorage.setItem(REVISION_KEY, Array.from(crypto.getRandomValues(new Uint32Array(4)), n => n.toString(16)).join('-'))
}

function saveAuth(token: string, user: User) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  advanceRevision()
  localStorage.setItem(TOKEN_KEY, token)
}

function clearAuth() {
  advanceRevision()
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/**
 * 认证错误码机制。
 *
 * AuthContext 是模块（非组件渲染路径），不能使用 useLanguage。因此本文件抛出的
 * Error.message 一律是稳定的机器键（如 'loginFailed'、'invalidCredentials'），
 * 由消费组件（AuthPage / AccountPage）在渲染时用 `t('account.' + message)`
 * 映射为界面文案，从而随语言切换。
 *
 * 后端返回的中文 detail 是服务端数据（backend/api/auth_routes.py 的常量），
 * 此处按已知常量归类为机器键；未知名回退到调用方传入的 fallback 机器键，
 * 保证前端永远不直接展示后端原文。
 */
const SERVER_DETAIL_TO_CODE: Record<string, string> = {
  '邮箱或密码错误': 'invalidCredentials',
  '邮箱未验证，请先完成邮箱验证': 'emailNotVerified',
  '您的管理员申请尚未通过审批，请耐心等待': 'approvalPending',
  '该邮箱已注册': 'emailRegistered',
  '该邮箱已占用其他用户名': 'emailTaken',
  '用户名已被占用': 'usernameTaken',
  '邮箱或用户名已被占用': 'emailOrUsernameTaken',
  '发送验证码失败，请稍后重试': 'sendCodeFailed',
  '用户不存在，请先注册': 'userNotFound',
  '邮箱已验证，请直接登录': 'alreadyVerified',
  '验证码错误': 'invalidCode',
  '验证码已过期，请重新获取': 'codeExpired',
  '登录已失效': 'sessionExpired',
}

export class AuthRequestError extends Error {
  constructor(message: string, public code?: string, public resendAfterSeconds = 0, public requiresEmailVerification = false) {
    super(message)
  }
}

async function responseError(res: Response, fallback: string): Promise<AuthRequestError> {
  const data = await res.json().catch(() => ({}))
  const codes: Record<string, string> = {
    invalid_credentials: 'invalidCredentials', email_not_verified: 'emailNotVerified', verification_send_failed: 'sendCodeFailed',
    verification_rate_limited: 'verificationRateLimited', invalid_verification_code: 'invalidOrExpiredCode',
    verification_attempts_exceeded: 'verificationAttemptsExceeded', verification_unavailable: 'verificationUnavailable',
    invalid_email: 'invalidEmail', account_inactive: 'accountInactive',
  }
  const detail = data.error || data.detail
  const message = codes[data.code] || (typeof detail === 'string' ? SERVER_DETAIL_TO_CODE[detail] : undefined)
  const retry = Number(res.headers.get('Retry-After') || data.resend_after_seconds || 0)
  return new AuthRequestError(message || fallback, data.code, Number.isFinite(retry) ? Math.max(0, retry) : 0, data.requires_email_verification === true)
}

/** 包装 fetch：网络层失败（TypeError）统一归类为机器键，避免浏览器英文原文透出。 */
async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw new Error('networkError')
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session>(() => ({ ...readIdentity(), user: null }))
  const [loading, setLoading] = useState(true)
  const current = useRef(session)
  const mounted = useRef(false)
  const validation = useRef(0)
  const authentication = useRef(0)
  const pending = useRef<SessionIdentity | null>(null)

  const applySession = useCallback((next: Session) => {
    current.current = next
    setSession(next)
  }, [])

  const invalidateValidation = useCallback(() => {
    validation.current += 1
    pending.current = null
  }, [])

  const syncAuth = useCallback(() => {
    const identity = readIdentity()
    if (!sameIdentity(identity, current.current)) {
      invalidateValidation()
      // 两个旧存储键不是原子记录；新凭据只采用服务端核验出的匹配身份。
      applySession({ ...identity, user: null })
    }
    if (!identity.token) {
      setLoading(false)
      return
    }
    if (current.current.user && localStorage.getItem(USER_KEY) === JSON.stringify(current.current.user)) return
    if (pending.current && sameIdentity(pending.current, identity)) return
    pending.current = identity
    const request = ++validation.current
    const isCurrent = () => mounted.current && request === validation.current && sameIdentity(identity, readIdentity())
    setLoading(!current.current.user)
    void authFetch('/api/auth/me', { headers: { Authorization: `Bearer ${identity.token}` } })
      .then(async response => {
        if (!isCurrent()) return
        if (response.status === 401 || response.status === 403) {
          clearAuth()
          applySession({ ...readIdentity(), user: null })
          return
        }
        if (!response.ok) return
        const data = await response.json()
        if (!isCurrent() || !data.user?.username) return
        // 核验响应绝不写回 token；相同 user 字符串不会再次触发 storage 事件。
        localStorage.setItem(USER_KEY, JSON.stringify(data.user))
        applySession({ ...identity, user: data.user })
      })
      .catch(() => {
        // 网络或服务暂时故障不等于会话失效；保留凭据，恢复页面时可重试。
      })
      .finally(() => {
        if (mounted.current && request === validation.current) {
          pending.current = null
          setLoading(false)
        }
      })
  }, [applySession, invalidateValidation])

  useEffect(() => {
    mounted.current = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const onStorage = (event: StorageEvent) => {
      if (event.storageArea !== localStorage) return
      if (event.key !== null && ![TOKEN_KEY, USER_KEY, REVISION_KEY].includes(event.key)) return
      // 合并一次登录产生的多键通知，读取最新值而不是重放旧事件。
      clearTimeout(timer)
      timer = setTimeout(syncAuth, 0)
    }
    const onVisible = () => { if (document.visibilityState === 'visible') syncAuth() }
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', syncAuth)
    document.addEventListener('visibilitychange', onVisible)
    syncAuth()
    return () => {
      mounted.current = false
      authentication.current += 1
      invalidateValidation()
      clearTimeout(timer)
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', syncAuth)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [syncAuth, invalidateValidation])

  const authenticate = useCallback(async (path: string, body: object, fallback: string) => {
    const identity = readIdentity()
    const operation = ++authentication.current
    const res = await authFetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw await responseError(res, fallback)
    const data = await res.json()
    if (!mounted.current || operation !== authentication.current || !sameIdentity(identity, readIdentity())) {
      throw new Error('sessionExpired')
    }
    saveAuth(data.access_token, data.user)
    invalidateValidation()
    applySession({ ...readIdentity(), user: data.user })
    setLoading(false)
  }, [applySession, invalidateValidation])

  const login = useCallback(async (email: string, password: string) => {
    await authenticate('/api/auth/login', { email, password }, 'loginFailed')
    return {}
  }, [authenticate])

  const register = useCallback(async (email: string, password: string, username: string, realName: string) => {
    const res = await authFetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, username, real_name: realName || undefined }),
    })
    if (!res.ok) {
      throw await responseError(res, 'registerFailed')
    }
    const data = await res.json()
    return { requiresEmailVerification: Boolean(data.requires_email_verification), resendAfterSeconds: data.resend_after_seconds ?? 60 }
  }, [])

  const replaceUser = useCallback((nextUser: User) => {
    if (!session.token || !sameIdentity(session, readIdentity()) || nextUser.id !== session.user?.id) return
    invalidateValidation()
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    applySession({ ...session, user: nextUser })
    setLoading(false)
  }, [session, applySession, invalidateValidation])

  const updateUsername = useCallback(async (username: string) => {
    if (!session.token || !sameIdentity(session, readIdentity())) throw new Error('sessionExpired')
    const res = await authFetch('/api/auth/username', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.token}` },
      body: JSON.stringify({ username }),
    })
    if (!res.ok) throw await responseError(res, 'usernameUpdateFailed')
    const data = await res.json()
    const updatedUser: User = data.user
    replaceUser(updatedUser)
  }, [replaceUser, session])

  const verifyEmail = useCallback(async (email: string, code: string) => {
    await authenticate('/api/auth/verify-email', { email, code }, 'verifyFailed')
  }, [authenticate])

  const resendVerification = useCallback(async (email: string, password: string) => {
    const res = await authFetch('/api/auth/resend-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) throw await responseError(res, 'resendFailed')
    const data = await res.json()
    return Number(data.resend_after_seconds ?? 60)
  }, [])

  const logout = useCallback(() => {
    authentication.current += 1
    invalidateValidation()
    clearAuth()
    applySession({ ...readIdentity(), user: null })
    setLoading(false)
  }, [applySession, invalidateValidation])

  return (
    <AuthContext.Provider value={{ user: session.user, token: session.token, loading, login, register, updateUsername, replaceUser, verifyEmail, resendVerification, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
