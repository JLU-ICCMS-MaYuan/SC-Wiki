import { usernameValidationError } from '../../lib/username'

export interface DemoRegistration {
  email: string
  password: string
  username: string
  realName: string
}

export type DemoError = 'credentials' | 'unverified' | 'invalidUsername' | 'shortPassword'
  | 'taken' | 'invalidCode' | 'expired' | 'tooManyAttempts' | 'cooldown'

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
  const accounts = new Map<string, DemoAccount>([
    ['researcher@example.com', { email: 'researcher@example.com', password: DEMO_PASSWORD, username: 'researcher', realName: '', verified: true, sentAt: null, attempts: 0 }],
    ['unverified@example.com', { email: 'unverified@example.com', password: DEMO_PASSWORD, username: 'new_researcher', realName: '', verified: false, sentAt: null, attempts: 0 }],
  ])

  return {
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
