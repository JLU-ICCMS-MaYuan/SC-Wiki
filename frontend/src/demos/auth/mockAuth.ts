import { usernameValidationError } from '../../lib/username'

export interface DemoRegistration {
  email: string
  password: string
  username: string
  realName: string
}

export type DemoError = 'credentials' | 'unverified' | 'invalidUsername' | 'shortPassword'
  | 'taken' | 'invalidCode' | 'expired' | 'tooManyAttempts' | 'cooldown' | 'passwordMismatch'

interface DemoAccount extends DemoRegistration {
  verified: boolean
  sentAt: number | null
  attempts: number
}

export const DEMO_PASSWORD = 'demo123456'
export const DEMO_CODE = '123456'
const pause = () => new Promise<void>(resolve => window.setTimeout(resolve, 450))
const fail = (key: DemoError): never => { throw new Error(key) }
const normalize = (email: string) => email.trim().toLowerCase()

// 每个页面实例独立；没有 fetch、token、本地认证存储或邮件发送。
export function createDemoAuth() {
  const resets = new Map<string, { sentAt: number; attempts: number; consumed: boolean; grant: string | null; authorizedAt: number }>()
  let resetSequence = 0
  const accounts = new Map<string, DemoAccount>([
    ['researcher@example.com', { email: 'researcher@example.com', password: DEMO_PASSWORD, username: 'researcher', realName: '', verified: true, sentAt: null, attempts: 0 }],
    ['unverified@example.com', { email: 'unverified@example.com', password: DEMO_PASSWORD, username: 'new_researcher', realName: '', verified: false, sentAt: null, attempts: 0 }],
  ])

  return {
    async requestPasswordReset(email: string) {
      await pause()
      const key = normalize(email), previous = resets.get(key)
      if (previous && Date.now() - previous.sentAt < 60_000) return fail('cooldown')
      // 未知邮箱也返回统一反馈；是否存在账号不能从发送反馈判断。
      resets.set(key, { sentAt: Date.now(), attempts: 0, consumed: false, grant: null, authorizedAt: 0 })
    },
    async verifyPasswordReset(email: string, code: string) {
      await pause()
      const key = normalize(email), challenge = resets.get(key)
      if (!challenge || challenge.consumed || Date.now() - challenge.sentAt >= 300_000) return fail('expired')
      if (challenge.attempts >= 5) return fail('tooManyAttempts')
      if (code !== DEMO_CODE || !accounts.get(key)?.verified) { challenge.attempts++; return fail('invalidCode') }
      challenge.consumed = true
      challenge.grant = `demo-reset-${++resetSequence}`
      challenge.authorizedAt = Date.now()
      return challenge.grant
    },
    async resetPassword(email: string, grant: string, newPassword: string) {
      await pause()
      const key = normalize(email), challenge = resets.get(key), account = accounts.get(key)
      if (!account || !grant || !challenge?.grant || challenge.grant !== grant || Date.now() - challenge.authorizedAt >= 300_000) return fail('expired')
      if (newPassword.length < 10) return fail('shortPassword')
      account.password = newPassword
      challenge.grant = null
    },
    cancelPasswordReset(email: string) {
      const challenge = resets.get(normalize(email))
      if (challenge) challenge.grant = null
    },
    async login(email: string, password: string) {
      await pause()
      const account = accounts.get(normalize(email))
      if (!account || account.password !== password) return fail('credentials')
      if (!account.verified) return fail('unverified')
    },
    async register(form: DemoRegistration) {
      await pause()
      if (usernameValidationError(form.username)) return fail('invalidUsername')
      if (form.password.length < 10) return fail('shortPassword')
      const email = normalize(form.email)
      if (accounts.has(email) || [...accounts.values()].some(item => item.username === form.username)) return fail('taken')
      accounts.set(email, { ...form, email, verified: false, sentAt: Date.now(), attempts: 0 })
    },
    async verify(email: string, code: string) {
      await pause()
      const account = accounts.get(normalize(email))
      if (!account || account.sentAt === null || Date.now() - account.sentAt >= 300_000) return fail('expired')
      if (account.attempts >= 5) return fail('tooManyAttempts')
      if (code !== DEMO_CODE) { account.attempts++; return fail('invalidCode') }
      account.verified = true
      account.sentAt = null
    },
    async resend(email: string) {
      await pause()
      const account = accounts.get(normalize(email))
      if (!account) return fail('credentials')
      if (account.sentAt !== null && Date.now() - account.sentAt < 60_000) return fail('cooldown')
      account.sentAt = Date.now()
      account.attempts = 0
    },
  }
}
