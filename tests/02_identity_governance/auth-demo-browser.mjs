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

  // 找回密码仅从登录按钮进入，不提前显示新密码表单。
  await page.goto(`${base}/auth-demo.html`)
  await page.setViewportSize({ width: 1440, height: 900 })
  assert.equal(await page.getByLabel('新密码', { exact: true }).count(), 0)
  await page.getByRole('button', { name: '忘记密码？', exact: true }).click()
  await shot('reset-email-1440')
  await page.getByLabel('邮箱', { exact: true }).fill('researcher@example.com')
  await page.getByRole('button', { name: '发送验证码', exact: true }).click()
  await page.getByRole('heading', { name: '验证你的身份' }).waitFor()
  assert.equal(await page.getByLabel('新密码', { exact: true }).count(), 0)
  await page.getByLabel('6 位验证码').fill('000000')
  await page.getByRole('button', { name: '验证邮箱', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '验证码不正确' }).waitFor()
  await page.getByLabel('6 位验证码').fill('123456')
  await page.getByRole('button', { name: '验证邮箱', exact: true }).click()
  await page.getByRole('heading', { name: '设置新密码' }).waitFor()
  await page.getByLabel('新密码', { exact: true }).fill('changedPassword123')
  await page.getByLabel('确认新密码', { exact: true }).fill('differentPassword123')
  await page.getByRole('button', { name: '确认修改密码', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '两次输入的密码不一致' }).waitFor()
  await shot('reset-password-error-1440')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'English', exact: true }).click()
  await noOverflow('reset-password-en-390', 390, 844)
  await page.getByRole('button', { name: '中文', exact: true }).click()
  await page.getByLabel('确认新密码', { exact: true }).fill('changedPassword123')
  await page.getByRole('button', { name: '确认修改密码', exact: true }).click()
  await page.getByRole('heading', { name: '密码已更新' }).waitFor()
  await page.getByRole('button', { name: '返回登录', exact: true }).click()
  await page.getByLabel('密码', { exact: true }).fill('demo123456')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '邮箱或密码不正确' }).waitFor()
  await page.getByLabel('密码', { exact: true }).fill('changedPassword123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('heading', { name: '欢迎回来，研究者。' }).waitFor()
  report.flows.push('忘记密码入口、错误验证码、验证后设密、确认不一致、旧密码拒绝和新密码登录')

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
    if (i < 4) await page.waitForTimeout(3300)
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

  assert.equal(await page.locator('.sc-form-section').evaluate(el => getComputedStyle(el).borderLeftWidth), '0px')
  const push = async () => {
    const position = await puck.evaluate(el => {
      const point = el.ownerSVGElement.createSVGPoint()
      const p = point.matrixTransform(el.getScreenCTM())
      return { x: p.x, y: p.y }
    })
    await page.mouse.move(position.x, position.y)
    assert.equal(await puck.evaluate(el => getComputedStyle(el).cursor), 'grab')
    await page.mouse.down()
    assert.equal(await puck.evaluate(el => getComputedStyle(el).cursor), 'grabbing')
    await page.mouse.up()
    await page.waitForTimeout(40)
  }
  assert.equal(await puck.getAttribute('data-period'), '12000')
  await push()
  assert(Number(await puck.getAttribute('data-period')) < 12000)
  for (let i = 0; i < 12; i++) await push()
  assert.equal(await puck.getAttribute('data-period'), '1000')
  await push()
  assert.equal(await puck.getAttribute('data-period'), '1000')
  report.animation.speedCap = '初始 12000ms；点击加速；重复点击上限 1000ms'
  const cycleSamples = []
  for (let i = 0; i < 16; i++) {
    cycleSamples.push(await puck.evaluate(el => ({ time: performance.now(), phase: Number(el.getAttribute('data-phase')) })))
    if (i < 15) await page.waitForTimeout(80)
  }
  let turns = 0
  for (let i = 1; i < cycleSamples.length; i++) turns += (cycleSamples[i].phase - cycleSamples[i - 1].phase + 1) % 1
  const measuredPeriod = (cycleSamples.at(-1).time - cycleSamples[0].time) / turns
  assert(measuredPeriod > 900 && measuredPeriod < 1100, `Measured max-speed period: ${measuredPeriod}ms`)
  report.animation.measuredMaxSpeedPeriodMs = measuredPeriod

  const initialAngle = Number(await puck.getAttribute('data-phase')) * Math.PI * 2
  const targetAngle = (initialAngle + Math.PI / 2) % (Math.PI * 2)
  const trackPoint = await page.locator('.sc-orbit').evaluate((svg, angle) => {
    const point = svg.createSVGPoint()
    point.x = 360 + 244 * Math.cos(angle); point.y = 245 + 98 * Math.sin(angle)
    const result = point.matrixTransform(svg.getScreenCTM())
    return { x: result.x, y: result.y }
  }, targetAngle)
  await page.mouse.click(trackPoint.x, trackPoint.y)
  await page.locator('.sc-stop-marker').waitFor()
  assert.equal(await page.locator('.sc-track-control').evaluate(el => getComputedStyle(el).outlineStyle), 'none')
  assert.notEqual(await puck.getAttribute('data-period'), 'stopped')
  await page.waitForFunction(() => document.querySelector('[data-testid="superconductor-puck"]')?.getAttribute('data-period') === 'stopped')
  // 浏览器鼠标事件可能量化 clientX/Y；实际停靠必须精确匹配点击产生的标记。
  const markerTransform = await page.locator('.sc-stop-marker').getAttribute('transform')
  const [markerX, markerY] = markerTransform.match(/[-\d.]+/g).map(Number)
  const selectedAngle = (Math.atan2((markerY - 245) / 98, (markerX - 360) / 244) + Math.PI * 2) % (Math.PI * 2)
  const stoppedAngle = Number(await puck.getAttribute('data-phase')) * Math.PI * 2
  assert(Math.abs(stoppedAngle - selectedAngle) < 0.00001)
  assert(Math.abs(Math.atan2(Math.sin(selectedAngle - targetAngle), Math.cos(selectedAngle - targetAngle))) < .02)
  report.animation.stopCoordinates = { requested: targetAngle, selected: selectedAngle, stopped: stoppedAngle }
  const atTarget = await puck.getAttribute('transform')
  await page.waitForTimeout(200)
  assert.equal(await puck.getAttribute('transform'), atTarget)
  await shot('parked-with-vapor-1440')
  await push()
  assert.equal(await puck.getAttribute('data-period'), '20000')
  assert.equal(await page.locator('.sc-stop-marker').count(), 0)
  await push()
  assert(Number(await puck.getAttribute('data-period')) < 20000)
  report.animation.trackStopRestart = '真实鼠标选择前方目标、到点精确停靠；重新推动 20000ms，继续点击加速'
  const fog = page.locator('.sc-vapor > g').first()
  const fogBefore = await fog.getAttribute('transform')
  await page.waitForTimeout(200)
  assert.notEqual(await fog.getAttribute('transform'), fogBefore)
  await shot('interactive-orbit-1440')
  await page.getByRole('button', { name: '暂停动画', exact: true }).click()
  const frozenFog = await fog.getAttribute('transform')
  await page.waitForTimeout(160)
  assert.equal(await fog.getAttribute('transform'), frozenFog)
  report.animation.vapor = '白雾随动画时钟扩散；暂停冻结'

  const fieldCheck = await page.locator('.sc-field-lines path').evaluateAll(paths => {
    let intrusions = 0
    for (const path of paths) {
      const length = path.getTotalLength()
      for (let i = 0; i <= 300; i++) {
        const p = path.getPointAtLength(length * i / 300)
        if (Math.abs(p.x) < 42 && p.y > -26 && p.y < 34) intrusions++
      }
    }
    return { paths: paths.length, intrusions }
  })
  assert.equal(fieldCheck.paths, 8)
  assert.equal(fieldCheck.intrusions, 0)
  assert.equal(await page.locator('.sc-vapor-trail > g').count(), 28)
  assert.equal(await page.locator('.sc-vapor-local > g').count(), 16)
  report.animation.meissnerFieldGeometry = fieldCheck
  report.animation.vaporLayers = { trail: 28, local: 16 }

  assert.equal(await page.evaluate(() => localStorage.getItem('auth_token')), 'untouched-session')
  assert.deepEqual(report.apiRequests, [])
  assert.deepEqual(report.errors, [])
  report.flows.push('原有认证存储保持、零 API 请求、无页面异常')
  await writeFile(`${output}/results.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally {
  await browser.close()
}
