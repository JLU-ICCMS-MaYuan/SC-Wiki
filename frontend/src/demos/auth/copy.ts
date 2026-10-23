import { authCopy } from '../../features/auth/copy'

// 仅独立 Demo 入口导入这些覆盖值，生产界面不包含演示账号或固定验证码。
export const authDemoCopy = {
  zh: {
    ...authCopy.zh,
    passwordHint: '至少 10 位字符',
    demoHint: '演示密码：demo123456；验证码：123456。数据仅在此页面内保留，刷新即重置。请勿填写真实密码。',
    codeSent: '演示验证码已准备好，输入 123456 即可体验；不会发送真实邮件。',
    codeNotSent: '该演示账号尚未验证，请先点击重新发送验证码。',
    resetDemoHint: '此处为演示：使用 researcher@example.com，验证码为 123456，不会发送真实邮件。',
    resetSuccessText: '演示账号的密码已修改。返回登录，试试你的新密码。',
    errors: {
      ...authCopy.zh.errors,
      credentials: '邮箱或密码不正确。可以使用下方演示账号重试。',
      invalidCode: '验证码不正确，请重新输入。演示验证码为 123456。',
    },
  },
  en: {
    ...authCopy.en,
    passwordHint: 'At least 10 characters',
    demoHint: 'Password: demo123456. Code: 123456. Demo data resets on refresh. Please do not enter a real password.',
    codeSent: 'Your demo code is ready: enter 123456. No real email will be sent.',
    codeNotSent: 'This demo account is unverified. Request a new code to continue.',
    resetDemoHint: 'Demo only: use researcher@example.com with code 123456. No real email will be sent.',
    resetSuccessText: 'Your demo password has changed. Return to login and try your new password.',
    errors: {
      ...authCopy.en.errors,
      credentials: 'Incorrect email or password. Try one of the demo accounts below.',
      invalidCode: 'Incorrect code. Please try again. The demo code is 123456.',
    },
  },
}
