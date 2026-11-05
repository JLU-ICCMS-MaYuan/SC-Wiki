// 正式构建配本机真实只读接口；凭证仅从进程环境读取，不保存、不执行提交或审核。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium } from '../../prototypes/account-center/node_modules/playwright/index.mjs'

const origin = process.env.FRONTEND_URL || 'http://127.0.0.1:5474'
const apiOrigin = process.env.REVIEW_API_URL || 'http://127.0.0.1:8080'
const output = process.env.REVIEW_BROWSER_OUTPUT || '/tmp/scwiki214-browser'
const users = JSON.parse(process.env.SCWIKI_REVIEW_BROWSER_USERS || '{}')
const title = 'Superconductive sodalite-like clathrate calcium hydride at high pressures'
const doi = '10.1073/pnas.1118168109'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const checks = [], errors = [], writes = []
await mkdir(output, { recursive: true })

async function open(role, width = 1440) {
  const credential = users[role]
  const context = await browser.newContext({ viewport: { width, height: 1000 } })
  await context.addInitScript(credential => {
    localStorage.setItem('sc-wiki.language', 'zh')
    if (credential) {
      localStorage.setItem('auth_token', credential.token)
      localStorage.setItem('auth_user', JSON.stringify(credential.user))
    }
  }, credential)
  await context.route('**/api/**', async route => {
    const request = route.request()
    if (request.method() !== 'GET') {
      writes.push({ role, method: request.method(), path: new URL(request.url()).pathname })
      return route.abort()
    }
    const url = new URL(request.url())
    const headers = { ...request.headers() }
    if (credential) headers.authorization = 'Bearer ' + credential.token
    try {
      const response = await route.fetch({ url: apiOrigin + url.pathname + url.search, headers })
      await route.fulfill({ response })
    } catch {
      errors.push({ role, message: '只读接口转发失败', path: url.pathname })
      await route.abort().catch(() => {})
    }
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push({ role, message: error.message }))
  return { page, context }
}

try {
  for (const role of ['admin', 'superadmin']) {
    const { page, context } = await open(role)
    await page.goto(origin + '/' + role + '?section=papers&review_tab=history')
    await page.getByLabel('搜索标题、DOI 或期刊').fill(doi)
    await page.getByRole('button', { name: '搜索', exact: true }).click()
    await page.getByText('没有匹配记录，请更换关键词或筛选条件。').waitFor()
    assert.equal(await page.getByText(title, { exact: true }).count(), 0)
    await page.getByRole('tab', { name: '待检查', exact: true }).click()
    await page.getByText(title, { exact: true }).waitFor()
    assert.equal(await page.getByText(title, { exact: true }).count(), 1)
    await page.screenshot({ path: output + '/' + role + '-pending.png', fullPage: true })
    checks.push({ role, checkedCount: 0, pendingCount: 1 })
    await context.unrouteAll({ behavior: 'wait' })
    await context.close()
  }
  for (const [role, width] of [['user', 1440], ['user', 390], ['superadmin', 1440], ['anonymous', 1440]]) {
    const { page, context } = await open(role, width)
    await page.goto(origin + '/papers/1208')
    await page.getByRole('heading', { name: '论文详情', exact: true }).waitFor()
    const authorized = role !== 'anonymous'
    await page.getByText('审核状态: ' + (authorized ? '待审核' : '审核完成'), { exact: true }).first().waitFor()
    assert.equal(await page.getByText('当前展示旧批准版；修订稿通过审核后更新公开内容。', { exact: true }).count(), authorized ? 1 : 0)
    // 材料状态内仍有各自的化学式；只移除正文卡片旁遗留的摘要卡片。
    assert.equal(await page.getByText('基础信息', { exact: true }).evaluate(node =>
      node.closest('.MuiCard-root').parentElement.querySelectorAll(':scope > .MuiCard-root').length), 1)
    assert.equal(await page.getByText('关键词', { exact: true }).count(), 0)
    assert.equal(await page.getByRole('link', { name: '修改并重新提交', exact: true }).count(), 0)
    assert.ok(await page.getByText(title, { exact: true }).count() > 0)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
    await page.screenshot({ path: output + '/' + role + '-detail-' + width + '.png', fullPage: true })
    checks.push({ role, width, status: authorized ? 'pending' : 'approved', oldCard: false })
    if (role === 'user' && width === 1440) {
      await page.getByRole('button', { name: '切换为英文', exact: true }).click()
      await page.getByText('Review status: Pending review', { exact: true }).first().waitFor()
      assert.equal(await page.getByText('The previously approved version is shown. Public content will update after the revision is approved.', { exact: true }).count(), 1)
    }
    await context.unrouteAll({ behavior: 'wait' })
    await context.close()
  }
  assert.deepEqual(errors, [])
  assert.deepEqual(writes, [])
  await writeFile(output + '/checks.json', JSON.stringify({ checks, errors, writes }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, errors, writes }))
} finally {
  await browser.close()
}
