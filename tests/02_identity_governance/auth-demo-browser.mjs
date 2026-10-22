// 独立浏览器上下文，只操作演示入口；绝不调用真实认证接口。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
const output = process.env.ARTIFACT_DIR || '/tmp/scwiki151-auth-demo'
await mkdir(output, { recursive: true })
const report = { layouts: [], flows: [], animation: {}, apiRequests: [], errors: [] }
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
const page = await context.newPage()
page.on('pageerror', error => report.errors.push(error.message))
await page.route('**/api/**', route => { report.apiRequests.push(route.request().url()); return route.abort() })
const shot = async name => page.screenshot({ path: `${output}/${name}.png`, fullPage: true })
const noOverflow = async (name, width, height) => {
  const dims = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
  assert(dims.scroll <= dims.client + 1, `${name}: horizontal overflow ${JSON.stringify(dims)}`)
  report.layouts.push({ name, width, height, ...dims })
  await shot(name)
}

try {
  await page.goto(`${base}/auth-demo.html`)
  await page.getByRole('heading', { name: '欢迎回到超导维基' }).waitFor()
  await page.evaluate(() => localStorage.setItem('auth_token', 'untouched-session'))
  for (const [width, height] of [[1440, 900], [768, 1024], [390, 844], [320, 720]]) {
    await page.setViewportSize({ width, height })
    await noOverflow(`login-zh-${width}`, width, height)
    await page.getByRole('tab', { name: '注册', exact: true }).click()
    await noOverflow(`register-zh-${width}`, width, height)
    await page.getByRole('tab', { name: '登录', exact: true }).click()
  }
  await page.getByRole('button', { name: 'English', exact: true }).click()
  for (const [width, height] of [[1440, 900], [768, 1024], [390, 844], [320, 720]]) {
    await page.setViewportSize({ width, height })
    await noOverflow(`login-en-${width}`, width, height)
    await page.getByRole('tab', { name: 'Sign up', exact: true }).click()
    await noOverflow(`register-en-${width}`, width, height)
    await page.getByRole('tab', { name: 'Log in', exact: true }).click()
  }
  await page.getByRole('button', { name: '中文', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 900 })

  // 键盘标签切换与可见焦点。
  await page.getByRole('tab', { name: '登录', exact: true }).focus()
  await page.keyboard.press('ArrowRight')
  assert.equal(await page.getByRole('tab', { name: '注册', exact: true }).getAttribute('aria-selected'), 'true')
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'tab-register')
  await page.keyboard.press('Tab')
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'demo-username')
  report.flows.push('键盘标签切换、Tab 进入表单')

  await page.getByLabel('公开用户名', { exact: true }).fill('demo_researcher')
  await page.getByLabel('邮箱', { exact: true }).fill('new@example.com')
  await page.getByLabel('密码', { exact: true }).fill('password123')
  await page.getByRole('button', { name: '显示密码', exact: true }).click()
  assert.equal(await page.getByLabel('密码', { exact: true }).getAttribute('type'), 'text')
  await page.getByRole('button', { name: '隐藏密码', exact: true }).click()
  await page.getByRole('button', { name: '创建账号', exact: true }).click()
  await page.getByRole('heading', { name: '验证你的邮箱' }).waitFor()
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'auth-title')
  assert(await page.getByRole('button', { name: /秒后重新发送/ }).isDisabled())
  await page.getByLabel('6 位验证码').fill('000000')
  await page.getByRole('button', { name: '验证邮箱', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '验证码不正确' }).waitFor()
  await shot('verification-error')
  await page.getByLabel('6 位验证码').fill('123456')
  await page.getByRole('button', { name: '验证邮箱', exact: true }).click()
  await page.getByRole('heading', { name: '准备好，开始探索。' }).waitFor()
  await shot('registration-success')
  report.flows.push('注册、密码显隐、验证码错误恢复、冷却、验证成功')

  await page.getByRole('button', { name: '返回演示入口' }).click()
  await shot('entry')
  await page.getByRole('button', { name: '上传页登录入口' }).click()
  assert(page.url().endsWith('?from=upload'))
  await page.getByRole('button', { name: '返回上传' }).waitFor()
  await page.getByLabel('邮箱', { exact: true }).fill('researcher@example.com')
  await page.getByLabel('密码', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '邮箱或密码不正确' }).waitFor()
  await page.getByLabel('密码', { exact: true }).fill('demo123456')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('heading', { name: '欢迎回来，研究者。' }).waitFor()
  report.flows.push('上传入口跳转、登录错误恢复和成功')

  await page.getByRole('button', { name: '返回演示入口' }).click()
  await page.getByRole('button', { name: '侧栏登录入口' }).click()
  await page.getByLabel('邮箱', { exact: true }).fill('unverified@example.com')
  await page.getByLabel('密码', { exact: true }).fill('demo123456')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('heading', { name: '验证你的邮箱' }).waitFor()
  await page.getByRole('button', { name: '重新发送验证码', exact: true }).click()
  await page.getByText('演示验证码已准备好，输入 123456 即可体验；不会发送真实邮件。').waitFor()
  await page.getByRole('button', { name: 'English', exact: true }).click()
  assert(await page.getByRole('button', { name: /Resend in/ }).isDisabled())
  await page.setViewportSize({ width: 390, height: 844 })
  await noOverflow('verification-en-390', 390, 844)
  await page.getByRole('button', { name: '中文', exact: true }).click()
  await page.getByLabel('6 位验证码').fill('123456')
  await page.getByRole('button', { name: '验证邮箱', exact: true }).click()
  await page.getByRole('heading', { name: '欢迎回来，研究者。' }).waitFor()
  report.flows.push('未验证邮箱恢复、模拟重发、倒计时跨语言保留')

  await page.goto(`${base}/auth-demo.html`)
  await page.setViewportSize({ width: 1440, height: 900 })
  const puck = page.getByTestId('superconductor-puck')
  await puck.waitFor()
  const paused = await puck.getAttribute('transform')
  await page.waitForTimeout(180)
  assert.equal(await puck.getAttribute('transform'), paused)
  report.animation.reducedMotionStartsPaused = true
  await page.getByRole('button', { name: '播放动画', exact: true }).click()
  const phases = []
  const transforms = []
  for (let i = 0; i < 5; i++) {
    phases.push(Number(await puck.getAttribute('data-phase')))
    transforms.push(await puck.getAttribute('transform'))
    if (i < 4) await page.waitForTimeout(4200)
  }
  assert(new Set(transforms).size === 5)
  assert(phases.some((phase, i) => i > 0 && phase < phases[i - 1]))
  report.animation.fullCyclePhases = phases
  report.animation.fullCycleTransforms = transforms
  await page.getByRole('button', { name: '暂停动画', exact: true }).click()
  const stop = await puck.getAttribute('transform')
  await page.waitForTimeout(200)
  assert.equal(await puck.getAttribute('transform'), stop)
  await shot('desktop-orbit')
  report.animation.pause = true
  await page.getByRole('button', { name: '播放动画', exact: true }).click()
  await page.waitForTimeout(100)
  assert.notEqual(await puck.getAttribute('transform'), stop)

  // 自动化中注入可见性事件验证处理器；不冒充操作系统后台标签的实测。
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: true }); document.dispatchEvent(new Event('visibilitychange')) })
  await page.waitForTimeout(80)
  const hidden = await puck.getAttribute('transform')
  await page.waitForTimeout(180)
  assert.equal(await puck.getAttribute('transform'), hidden)
  await page.evaluate(() => { delete document.hidden; document.dispatchEvent(new Event('visibilitychange')) })
  await page.waitForTimeout(100)
  assert.notEqual(await puck.getAttribute('transform'), hidden)
  report.animation.visibilityEventInjection = '暂停及恢复通过；未验证真实操作系统标签后台状态'

  assert.equal(await page.evaluate(() => localStorage.getItem('auth_token')), 'untouched-session')
  assert.deepEqual(report.apiRequests, [])
  assert.deepEqual(report.errors, [])
  report.flows.push('原有认证存储保持、零 API 请求、无页面异常')
  await writeFile(`${output}/results.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally {
  await browser.close()
}
