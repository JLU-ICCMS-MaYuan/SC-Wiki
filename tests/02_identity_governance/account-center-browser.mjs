import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import { chromium } from '../../prototypes/account-center/node_modules/playwright/index.mjs'

// 渲染正式应用，接口用隔离响应验证前端契约；真实安全边界由 Go/SMTP 集成测试覆盖。
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const output = new URL('../../prototypes/account-center/qa/production/', import.meta.url)
await fs.mkdir(output, { recursive: true })
const screenshots = [], errors = [], calls = []
const paper = { id: 81, title: 'Superconductivity at 39 K in magnesium diboride', journal: 'Nature', year: 2001, doi: '10.1038/35065039', review_status: 'approved', created_at: '2026-10-23T08:00:00Z', checked_status: 'approved', checked_at: '2026-10-23T09:00:00Z' }
try {
  for (const role of ['user', 'admin', 'superadmin']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 })
    const user = { id: 7, username: 'researcher', email: 'researcher@example.test', role, is_admin: role !== 'user', is_superadmin: role === 'superadmin', is_approved: true, is_email_verified: true, account_status: 'active', username_change_allowed: false }
    let profile = { ...user, real_name: '研究者', affiliation: '吉林大学 · 物理学院', orcid: '', research_interests: ['高压超导', '第一性原理计算'], avatar_url: null }
    await context.addInitScript(({ user }) => { if (location.origin !== 'http://127.0.0.1:5173') return; localStorage.setItem('auth_token', 'isolated-browser-fixture'); localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh') }, { user })
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), method = request.method()
      const path = url.pathname
      calls.push({ role, path, method })
      let body = []
      if (path === '/api/auth/me') body = { user }
      else if (path === '/api/account/profile') {
        if (method === 'PATCH') profile = { ...profile, ...request.postDataJSON() }
        body = profile
      } else if (path === '/api/papers/my-uploads' || path === '/api/account/reviewed-papers') body = { items: [paper], total: 1 }
      else if (path === '/api/admin/papers/all') body = { items: [{ ...paper, review_status: 'pending' }], total: 1 }
      else if (path === '/api/superadmin/users') body = [user]
      else if (path === '/api/account/password-change-code') {
        assert.equal(request.postDataJSON().email, user.email)
        assert.equal(request.postDataJSON().current_password, 'OldPassword123!')
        body = { resend_after_seconds: 60, expires_in_seconds: 300 }
      } else if (path === '/api/account/change-password') {
        assert.equal(request.postDataJSON().code, '123456')
        return route.fulfill({ status: 204 })
      } else if (path === '/api/rag/llm/default-config') body = { data: { provider_name: 'local-test', model: 'fixture-model', base_url: '', api_key_configured: false, source: 'environment' } }
      else if (path.includes('unread')) body = { count: 0 }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    })
    context.on('page', tab => tab.on('pageerror', error => errors.push(error.message)))
    const page = await context.newPage()
    await page.goto('http://127.0.0.1:5173/account')
    await page.getByRole('button', { name: '修改资料', exact: true }).waitFor()
    assert.equal(await page.getByRole('textbox', { name: '真实姓名', exact: true }).count(), 0)
    await page.getByRole('button', { name: '修改资料', exact: true }).click()
    await page.getByLabel('所属机构', { exact: true }).fill('未保存的机构')
    await page.getByRole('button', { name: '取消', exact: true }).click()
    assert.equal(await page.getByText('未保存的机构', { exact: true }).count(), 0)
    await page.getByRole('button', { name: '修改资料', exact: true }).click()
    await page.getByLabel('所属机构', { exact: true }).fill('吉林大学 · 物理学院')
    await page.getByRole('button', { name: '保存资料', exact: true }).click()
    await page.getByRole('button', { name: '修改资料', exact: true }).waitFor()
    if (role !== 'user') {
      await page.getByRole('tab', { name: '待检查', exact: true }).click()
      await page.getByText(paper.title, { exact: true }).last().waitFor()
      await page.getByRole('tab', { name: '已检查记录', exact: true }).click()
    }
    if (role === 'superadmin') {
      for (const section of ['users', 'applications', 'charts', 'news', 'models', 'audit']) {
        const popupPromise = context.waitForEvent('page')
        await page.locator(`a[href="/superadmin?section=${section}"]`).click()
        const popup = await popupPromise
        await popup.waitForLoadState()
        await popup.locator('h4').waitFor()
        assert.equal(new URL(popup.url()).searchParams.get('section'), section)
        // 深链已展开目标模块，不出现工作台卡片墙。
        assert.equal(await popup.locator('.MuiCardActionArea-root').count(), 0)
        if (section === 'users') await popup.getByRole('tab', { name: '用户与权限' }).waitFor()
        if (section === 'models') await popup.getByText(/fixture-model/).waitFor()
        await popup.close()
      }
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: new URL(`${role}-desktop.png`, output).pathname, fullPage: true })
    screenshots.push(`${role}-desktop.png`)
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 })
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${role} overflow ${width}`)
      await page.locator('.account-security-toggle').click()
      await page.locator('.account-security .MuiCollapse-entered').waitFor()
      await page.getByLabel('当前密码', { exact: false }).fill('OldPassword123!')
      await page.getByLabel('账户绑定邮箱', { exact: false }).fill(user.email)
      if (width === 390) {
        await page.getByRole('button', { name: '验证并发送验证码', exact: true }).click()
        await page.getByLabel('邮箱验证码', { exact: false }).waitFor()
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${role} password overflow ${width}`)
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: new URL(`${role}-${width}.png`, output).pathname, fullPage: true })
      await page.locator('.account-security').screenshot({ path: new URL(`${role}-security-${width}.png`, output).pathname })
      await page.locator('.account-security-toggle').click()
    }
    await context.close()
  }
  assert.deepEqual(errors, [])
  const report = { screenshots, errors, requests: calls.length, limitation: '正式页面渲染与交互使用隔离 API 响应；后端安全及 SMTP 由真实处理器测试覆盖。' }
  await fs.writeFile(new URL('results.json', output), JSON.stringify(report, null, 2))
  console.log(report)
} finally { await browser.close() }
