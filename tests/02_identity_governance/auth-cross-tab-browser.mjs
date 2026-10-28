import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fixture = JSON.parse(await readFile(process.env.AUTH_FIXTURE_FILE || '/tmp/scwiki171-auth-fixture.json', 'utf8'))
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5179'
const output = process.env.ARTIFACT_DIR || '/tmp/scwiki171-auth-browser'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
context.setDefaultTimeout(10000)
const report = { scenarios: [], rounds: [], authRequests: {}, meLatencyMs: [], errors: [], environment: { database: fixture.database, cache: fixture.cache, browser: await browser.version() } }
let hold = null
await context.addInitScript(() => {
  window.__authDocument = Math.random()
  window.__authStorageEvents = 0
  window.addEventListener('storage', event => {
    if (event.key?.startsWith('auth_')) window.__authStorageEvents += 1
  })
})
await context.route('**/api/**', async route => {
  const url = new URL(route.request().url())
  if (url.pathname.startsWith('/api/auth/')) {
    report.authRequests[url.pathname] = (report.authRequests[url.pathname] || 0) + 1
    const started = performance.now()
    const delayed = hold && url.pathname === '/api/auth/me' && route.request().frame().page() === hold.page ? hold : null
    if (delayed) hold = null
    const response = await route.fetch({ url: fixture.url + url.pathname + url.search })
    if (url.pathname === '/api/auth/me') report.meLatencyMs.push(Math.round(performance.now() - started))
    if (delayed) {
      delayed.captured()
      await delayed.release
      await route.fulfill(delayed.status ? { status: delayed.status, json: { error: 'injected expired session' } } : { response })
    } else await route.fulfill({ response })
  } else {
    // 仅隔离与认证无关的业务请求；所有认证请求使用真实 Go 处理器。
    await route.fulfill({ json: { items: [], tasks: [], total: 0, count: 0, categories: [], data: { items: [], provider_name: 'Test', model: 'fixture', source: 'server' }, sources: [] } })
  }
})

const users = [
  { email: 'sync171a@example.test', username: 'SyncAlice171', password: 'BrowserPassword171!' },
  { email: 'sync171b@example.test', username: 'SyncBob171', password: 'BrowserPassword171!' },
]
async function register(user) {
  const post = (path, body) => fetch(fixture.url + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const registered = await post('/api/auth/register', user)
  // 同一隔离夹具内允许重复运行测试；已有测试用户保持有效。
  if (registered.status === 409) return
  assert.equal(registered.status, 202)
  const mail = await fetch(fixture.url + '/__fixture/mail?email=' + encodeURIComponent(user.email)).then(r => r.json())
  const verified = await post('/api/auth/verify-email', { email: user.email, code: mail.code })
  assert.equal(verified.status, 200)
}
const pages = []
const account = page => page.getByRole('button', { name: '打开账户菜单', exact: true })
const guest = page => page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: '登录', exact: true })
const signedIn = (selected, user) => Promise.all(selected.map(async page => {
  await account(page).waitFor({ timeout: 2000 })
  await page.getByRole('navigation', { name: '主导航' }).getByText(user.username, { exact: true }).waitFor({ timeout: 2000 })
}))
const signedOut = selected => Promise.all(selected.map(page => guest(page).waitFor({ timeout: 2000 })))
async function login(user) {
  await guest(pages[0]).click()
  await pages[0].getByLabel('邮箱', { exact: true }).fill(user.email)
  await pages[0].getByLabel('密码', { exact: true }).fill(user.password)
  await pages[0].getByRole('button', { name: '登录', exact: true }).click()
  await account(pages[0]).waitFor()
}
async function logout(page = pages[0]) {
  await account(page).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()
}
async function checkIdentity(user) {
  for (const page of pages) {
    const identity = await page.evaluate(async () => {
      const { api } = await import('/src/lib/api.ts')
      const result = await api.get('/api/auth/me')
      return { id: result.user.id, username: result.user.username }
    })
    assert.equal(identity.username, user.username)
  }
}
try {
  for (const user of users) await register(user)
  for (let i = 0; i < 5; i++) {
    const page = await context.newPage()
    page.on('pageerror', error => report.errors.push(error.message))
    pages.push(page)
  }
  await Promise.all(pages.map((page, i) => page.goto(base + [
    '/news',
    '/search?elements=La,H&source=sync#keep',
    '/news?tab=background#keep',
    '/auth?returnTo=%2Fsearch%3Fsource%3Dreturn%23kept',
    '/auth?returnTo=https%3A%2F%2Fevil.test',
  ][i])))
  await pages[1].getByPlaceholder('如 LaH10').fill('LaH10')
  const initialDocument = await pages[1].evaluate(() => window.__authDocument)
  const businessUrl = pages[1].url()
  // 第一次登录验证已打开的两个登录页自动回跳，且不接受外站地址。
  await login(users[0])
  await signedIn(pages, users[0])
  await pages[3].waitForURL(base + '/search?source=return#kept')
  await pages[4].waitForURL(base + '/news')
  await checkIdentity(users[0])
  report.scenarios.push('五页真实认证与原生 storage 分发；两登录页安全自动回跳；各页通用 API 使用一致身份')

  for (let round = 1; round <= 10; round++) {
    const exitStart = performance.now()
    await logout()
    await signedOut(pages)
    const logoutMs = Math.round(performance.now() - exitStart)
    const started = performance.now()
    const user = users[round % 2]
    await login(user)
    const syncStart = performance.now()
    await signedIn(pages, user)
    report.rounds.push({ round, logoutMs, loginIncludingFormMs: Math.round(performance.now() - started), synchronizationAfterSourceMs: Math.round(performance.now() - syncStart) })
    await checkIdentity(user)
    assert.equal(pages[1].url(), businessUrl)
    assert.equal(await pages[1].getByPlaceholder('如 LaH10').inputValue(), 'LaH10')
    assert.equal(await pages[1].evaluate(() => window.__authDocument), initialDocument)
  }
  report.scenarios.push('五页连续十轮退出/登录与账号交替；普通业务页 URL、输入及文档实例保留')

  // 冻结真实浏览器页面，在其恢复后核对最终会话。
  const cdp = await context.newCDPSession(pages[2])
  await pages[0].bringToFront()
  await cdp.send('Page.setWebLifecycleState', { state: 'frozen' })
  await logout()
  await signedOut(pages.filter((_, i) => i !== 2))
  await login(users[1])
  await signedIn(pages.filter((_, i) => i !== 2), users[1])
  const resumed = performance.now()
  await cdp.send('Page.setWebLifecycleState', { state: 'active' })
  await pages[2].bringToFront()
  await signedIn([pages[2]], users[1])
  report.resumeMs = Math.round(performance.now() - resumed)
  assert(report.resumeMs < 2000)
  await cdp.detach()
  report.scenarios.push('真实 CDP 冻结后台页，其他页退出重登后恢复，在两秒内识别新账号')

  for (const status of [null, 401]) {
    let captured, release
    const capturedPromise = new Promise(resolve => { captured = resolve })
    const releasePromise = new Promise(resolve => { release = resolve })
    hold = { page: pages[2], captured, release: releasePromise, status }
    await pages[2].reload()
    await capturedPromise
    await logout()
    await signedOut(pages)
    await login(users[0])
    await signedIn(pages, users[0])
    release()
    // 等待所拦截的旧响应实际抵达浏览器并完成处理。
    await pages[2].waitForTimeout(150)
    await signedIn(pages, users[0])
    await checkIdentity(users[0])
    report.scenarios.push(status ? '故障注入：旧 /me 401 不得清除新会话' : '真实旧 /me 成功响应迟到，不得恢复旧用户')
  }
  assert.equal(report.authRequests['/api/auth/login'], 14, '其他标签页不得额外发起登录')
  assert(await pages[1].evaluate(() => window.__authStorageEvents) > 0)
  assert.deepEqual(report.errors, [])
  await pages[1].screenshot({ path: output + '/five-tabs-synchronized.png', fullPage: true })
  report.result = 'passed'
} catch (error) {
  report.result = 'failed'
  report.failure = error.stack
  throw error
} finally {
  await writeFile(output + '/results.json', JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
  await browser.close()
}
