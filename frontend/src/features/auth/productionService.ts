import type { AuthState } from '../../context/AuthContext'
import { checkUsernameAvailability } from '../../lib/username'
import { AuthFailure, type AuthService } from './service'

const errorKeys: Record<string, string> = {
  invalidCredentials: 'credentials', emailNotVerified: 'unverified', emailRegistered: 'taken', emailTaken: 'taken', usernameTaken: 'taken', emailOrUsernameTaken: 'taken',
  invalidOrExpiredCode: 'expired', codeExpired: 'expired', verificationAttemptsExceeded: 'tooManyAttempts', verificationRateLimited: 'cooldown', verificationUnavailable: 'unavailable',
  invalid_verification_code: 'expired', invalid_reset_token: 'expired', verification_attempts_exceeded: 'tooManyAttempts', verification_rate_limited: 'cooldown',
  verification_send_failed: 'sendCodeFailed', verification_unavailable: 'unavailable', invalid_password: 'invalidPassword', invalid_email: 'invalidEmail',
}

async function adapt<T>(action: () => Promise<T>): Promise<T> {
  try { return await action() } catch (error) {
    const failure = error as Error & { code?: string; resendAfterSeconds?: number; requiresEmailVerification?: boolean }
    throw new AuthFailure(errorKeys[failure.code || ''] || errorKeys[failure.message] || failure.message, failure.resendAfterSeconds || 0, !!failure.requiresEmailVerification)
  }
}

async function resetRequest(action: string, body: Record<string, string>) {
  let response: Response
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 25_000)
  try {
    response = await fetch(`/api/auth/password-reset/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal })
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}))
    if (!response.ok) {
      const retry = Number(response.headers.get('Retry-After') || data.resend_after_seconds || 0)
      throw new AuthFailure(errorKeys[data.code] || 'requestFailed', Number.isFinite(retry) ? Math.max(0, retry) : 0)
    }
    return data
  } catch (error) {
    if (error instanceof AuthFailure) throw error
    throw new AuthFailure('networkError')
  } finally { window.clearTimeout(timeout) }
}

export function createProductionAuth(auth: Pick<AuthState, 'login' | 'register' | 'verifyEmail' | 'resendVerification'>): AuthService {
  return {
    login: (email, password) => adapt(() => auth.login(email, password)),
    register: form => adapt(() => auth.register(form.email, form.password, form.username, form.realName)),
    verify: (email, code) => adapt(() => auth.verifyEmail(email, code)),
    resend: (email, password) => adapt(() => auth.resendVerification(email, password)),
    checkUsername: checkUsernameAvailability,
    requestPasswordReset: async email => Number((await resetRequest('request', { email })).resend_after_seconds ?? 60),
    verifyPasswordReset: async (email, code) => {
      const data = await resetRequest('verify', { email, code })
      if (typeof data.reset_token !== 'string' || data.reset_token.length !== 64) throw new AuthFailure('requestFailed')
      return data.reset_token
    },
    resetPassword: async (email, reset_token, new_password) => { await resetRequest('complete', { email, reset_token, new_password }) },
    // 离开页面只丢弃浏览器内存凭证；服务端授权在消费、重发或 TTL 到期时失效。
    cancelPasswordReset: () => {},
  }
}
