import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
const out = process.env.ARTIFACT_DIR || '/tmp/scwiki151-auth-compact'
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const page = await browser.newPage({ reducedMotion: 'reduce' })
const result = { desktop: [], smallScreens: [], animation: [], requests: [], errors: [] }
page.on('pageerror', error => result.errors.push(error.message))
// 此测试只验证布局，不发送真实注册或找回请求。
await page.route('**/api/**', route => { result.requests.push(route.request().url()); return route.abort() })
const measure = () => page.evaluate(() => ({ height: innerHeight, width: innerWidth, scrollHeight: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth }))
try {
  await page.goto(`${base}/auth`)
  await page.getByRole('heading', { name: '欢迎回到超导维基' }).waitFor()
  for (const lang of ['zh', 'en']) {
    if (lang === 'en') await page.getByRole('button', { name: 'English', exact: true }).click()
    const tabs = lang === 'zh' ? ['登录', '注册'] : ['Log in', 'Sign up']
    for (const [width, height] of [[1920, 840], [1440, 760], [1366, 650], [1280, 720], [1024, 768]]) {
      await page.setViewportSize({ width, height })
      for (const tab of tabs) {
        await page.getByRole('tab', { name: tab, exact: true }).click()
        await page.evaluate(() => window.scrollTo(0, 0))
        const metrics = await measure()
        const submit = await page.locator('.sc-submit').boundingBox()
        result.desktop.push({ lang, tab, ...metrics, submitBottom: submit.y + submit.height })
        assert(metrics.scrollHeight <= height + 1, `${lang}/${tab}/${width}x${height}: page ${metrics.scrollHeight}px`)
        assert(metrics.scrollWidth <= width + 1)
        assert(submit.y >= 0 && submit.y + submit.height <= height, '提交按钮必须完整处于视口')
        if (width === 1440 || width === 1366) await page.screenshot({ path: `${out}/${lang}-${tab === tabs[0] ? 'login' : 'register'}-${width}.png`, fullPage: true })
      }
    }
  }
  await page.getByRole('button', { name: '中文', exact: true }).click()
  for (const [width, height] of [[390, 844], [320, 720], [1024, 480]]) {
    await page.setViewportSize({ width, height })
    await page.getByRole('tab', { name: '注册', exact: true }).click()
    await page.getByLabel('用户名', { exact: true }).fill('root')
    await page.getByLabel('邮箱', { exact: true }).focus()
    await page.getByRole('alert').waitFor()
    await page.locator('.sc-science summary').click()
    const metrics = await measure()
    assert(metrics.scrollWidth <= width + 1, '短屏不可横向溢出')
    // 实际键盘前进到提交按钮，浏览器必须能够将其滚入可视区。
    await page.getByLabel('真实姓名（可选）', { exact: true }).focus()
    await page.keyboard.press('Tab')
    assert(await page.locator('.sc-submit').evaluate(el => document.activeElement === el))
    const box = await page.locator('.sc-submit').boundingBox()
    assert(box.y >= 0 && box.y + box.height <= height + 1, '短屏提交按钮必须可通过键盘到达')
    result.smallScreens.push({ ...metrics, submitVisibleAfterTab: true })
    await page.screenshot({ path: `${out}/register-error-${width}x${height}.png`, fullPage: true })
    await page.getByLabel('用户名', { exact: true }).fill('')
    await page.locator('.sc-science summary').click()
  }
  await page.setViewportSize({ width: 1366, height: 650 })
  await page.getByRole('tab', { name: '登录', exact: true }).click()
  await page.getByRole('button', { name: '忘记密码？', exact: true }).click()
  await page.getByRole('heading', { name: '找回你的账号' }).waitFor()
  assert((await measure()).scrollHeight <= 651)
  await page.screenshot({ path: `${out}/forgot-password-1366.png`, fullPage: true })
  await page.getByRole('button', { name: '返回登录', exact: true }).click()
  await page.getByRole('button', { name: '播放动画', exact: true }).click()
  for (let i = 0; i < 7; i++) {
    await page.waitForTimeout(2000)
    const metrics = await measure()
    assert(metrics.scrollHeight <= 651 && metrics.scrollWidth <= 1367, '完整绕行时也不应产生桌面滚动条')
    result.animation.push({ ...metrics, transform: await page.getByTestId('superconductor-puck').getAttribute('transform') })
  }
  await page.getByRole('button', { name: '暂停动画', exact: true }).click()
  assert.deepEqual(result.requests, [])
  assert.deepEqual(result.errors, [])
  await writeFile(`${out}/results.json`, JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
} finally { await browser.close() }
