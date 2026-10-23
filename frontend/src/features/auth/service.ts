export interface Registration { email: string; password: string; username: string; realName: string }
export interface AuthService {
  login(email: string, password: string): Promise<unknown>
  register(form: Registration): Promise<void | { requiresEmailVerification: boolean; resendAfterSeconds?: number }>
  verify(email: string, code: string): Promise<void>
  resend(email: string, password: string): Promise<void | number>
  checkUsername?(username: string): Promise<{ available: boolean }>
  requestPasswordReset(email: string): Promise<void | number>
  verifyPasswordReset(email: string, code: string): Promise<string>
  resetPassword(email: string, grant: string, password: string): Promise<void>
  cancelPasswordReset(email: string): void
}

export class AuthFailure extends Error {
  constructor(message: string, public resendAfterSeconds = 0, public requiresEmailVerification = false) { super(message) }
}

export function passwordError(value: string): string | null {
  if ([...value].length < 10) return 'shortPassword'
  if (new TextEncoder().encode(value).length > 72) return 'passwordTooLong'
  return null
}
