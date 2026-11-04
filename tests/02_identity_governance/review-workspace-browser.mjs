// 正式构建页面配隔离API；不写用户稿件，不以界面夹具替代数据库权限验收。
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { chromium } from '../../prototypes/account-center/node_modules/playwright/index.mjs'

const origin = process.env.FRONTEND_URL || 'http://127.0.0.1:5413'
const output = process.env.REVIEW_BROWSER_OUTPUT || '/tmp/scwiki213-browser'
await mkdir(output, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url)))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const reports = [], errors = []
const longTitle = 'Superconductive sodalite-like clathrate calcium hydride at high pressures with detailed superconducting properties and electron phonon coupling measurements under several experimental conditions'
const states = Array.from({ length: 14 }, (_, i) => ({ id: i + 1, state_key: 'state-' + i, material: 'CaH6', material_name: 'Calcium hydride',
  superconductor: { chemical_formula: 'CaH6' }, state_kind: 'theoretical', material_dimensionality: 'bulk',
  crystal_system: 'cubic', element_count: 2, reported_space_group_symbol: 'Im-3m', pressure_value_gpa: i ? 150 + i : 0,
  property_modules: [], structure_families: [], structures: [] }))
const paper = { id: 213, title: longTitle, year: 2012, journal: 'PNAS', doi: '10.1073/pnas.1118168109', authors: [],
  paper_type: 'review', superconductor_kind: 'unknown', material_families: [], material_states: states,
  review_status: 'approved', workflow_status: 'rejected', can_revise: true, review_comment: '请修订' }
const draft = { paper, material_states: states, structure_candidates: [] }
const items = Array.from({ length: 45 }, (_, i) => ({ ...paper, id: i + 1, title: i ? '检查论文 ' + (i + 1) : longTitle,
  workflow_status: 'pending', checked_status: 'approved', checked_at: '2026-11-04T00:00:00Z' }))

async function contextFor(role, denied = false) {
  const user = { id: 7, username: 'isolated-213', email: 'isolated@example.test', role, is_approved: true,
    is_email_verified: true, account_status: 'active', real_name: '隔离界面验收', research_interests: [] }
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const calls = []
  await context.addInitScript(user => {
    localStorage.setItem('auth_token', 'isolated-browser-fixture')
    localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh')
  }, user)
  await context.route('**/api/**', async route => {
    const req = route.request(), u = new URL(req.url()), p = u.pathname
    calls.push({ path: p, query: u.search, method: req.method() })
    const json = body => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    if (denied && (/draft-state|open-workdraft|\/summary$/.test(p))) return route.fulfill({ status: 409, contentType: 'application/json',
      body: JSON.stringify({ detail: { code: 'manuscript_handed_off', message: '稿件已交出，当前没有编辑权；须由其他合法经手人正式退回' } }) })
    if (p === '/api/auth/me') return json({ user })
    if (p === '/api/rag/llm/catalog') return json({ data: { items: [] } })
    if (p === '/api/rag/llm/current') return json({ data: { provider_name: 'isolated', model: 'isolated', supports_vision: false } })
    if (p === '/api/account/profile') return json(user)
    if (p === '/api/account/admin-applications') return json([])
    if (p === '/api/papers/my-uploads') return json({ items: [], total: 0 })
    if (p === '/api/account/reviewed-papers' || p === '/api/admin/papers/all') {
      const offset = Number(u.searchParams.get('offset') || 0), limit = Number(u.searchParams.get('limit') || 20)
      return json({ items: items.slice(offset, offset + limit), total: 45 })
    }
    if (p === '/api/form-definitions') return json(definitions)
    if (p.startsWith('/api/form-definitions/')) return json(definitions.find(d => decodeURIComponent(p).includes(d.definition_key)) || {})
    if (p.includes('/classification-catalogs')) return json({ material_families: [], structure_families: [], material_dimensionalities: [] })
    if (p.endsWith('/space-groups')) return json({ space_groups: [] })
    if (/\/api\/(admin\/)?papers\/\d+$/.test(p)) return json(paper)
    if (p.endsWith('/revision-draft')) return json({ ok: true, data: draft, revision_id: 'a'.repeat(32), draft_version: 1 })
    if (p.endsWith('/open-workdraft')) return json({ write_epoch: 'isolated', revision: 1 })
    if (p.endsWith('/draft-state')) return json({ draft, staged: true, write_epoch: 'isolated', revision: 1 })
    if (p.endsWith('/draft-revision')) return json({ write_epoch: 'isolated', revision: 1 })
    if (p.endsWith('/summary')) return json({ version: 'isolated', records: [], needs_check: false })
    if (p.endsWith('/draft')) return json({ ok: true, data: draft })
    if (p.includes('/upload-tasks/') && p.endsWith('/parsing')) return json({ data: { status: 'ready', stage: 'ready', files: [], chunks: [], summary: { status: 'ready' }, next_poll_ms: null } })
    if (/\/upload-tasks\/[^/]+$/.test(p)) return json({ data: { task_id: '2'.repeat(32), filename: '隔离验收.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
    return json({ data: [], items: [], jobs: [], total: 0 })
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push({ role, message: error.message }))
  return { context, page, calls }
}

try {
  for (const role of ['user', 'admin', 'superadmin']) {
    const { context, page, calls } = await contextFor(role)
    await page.goto(origin + '/account')
    await page.getByRole('heading', { name: '他帮助 SC-Wiki 收录的论文', exact: true }).waitFor({timeout:5000}).catch(async error => { console.log(JSON.stringify({ errors, calls, body: (await page.locator('body').innerText()).slice(0, 2200), url: page.url() })); throw error })
    if (role !== 'user') {
      await page.getByText('检查论文 3', { exact: true }).waitFor()
      assert.equal(await page.getByText('检查论文 4', { exact: true }).count(), 0)
      assert.equal(await page.locator('[data-paper-list-scroll]').count(), 0)
      await page.getByRole('tab', { name: '待检查', exact: true }).click()
      await page.getByText('检查论文 3', { exact: true }).waitFor()
      assert.match(await page.getByRole('link', { name: '打开检查工作区', exact: true }).first().getAttribute('href'), /review_tab=pending/)
    }
    await page.screenshot({ path: output + '/account-' + role + '.png', fullPage: true })
    await page.goto(origin + '/papers/213')
    await page.getByRole('link', { name: '他帮助 SC-Wiki 收录的论文', exact: true }).waitFor()
    await page.getByRole('link', { name: '修改并重新提交', exact: true }).waitFor()
    const nav = page.getByRole('navigation', { name: '研究材料大纲', exact: true })
    await nav.getByRole('button', { name: '#1 · Im-3m · CaH₆ · 0 GPa', exact: true }).waitFor()
    await nav.getByRole('button', { name: /#14 ·/ }).click()
    await page.waitForFunction(() => { const target = document.querySelector('[data-state-key="state-13"]'); if (!target) return false; const rect = target.getBoundingClientRect(); return rect.top < innerHeight - 80 && rect.bottom > 80 })
    await nav.getByRole('button', { name: '收起研究材料大纲' }).click()
    assert.equal(await nav.getByRole('button', { name: /#14 ·/ }).count(), 0)
    await nav.getByRole('button', { name: '展开研究材料大纲' }).click()
    await page.setViewportSize({ width: 390, height: 844 })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    reports.push({ role, contribution_name: true, revision_entry: true, compact_page_size: role === 'user' ? null : 3, readonly_outline: true, zero_pressure: true, narrow_no_page_overflow: true })
    await context.close()
  }
  for (const tab of ['history', 'pending']) {
    const { context, page } = await contextFor('superadmin')
    await page.goto(origin + '/superadmin?section=papers&review_tab=' + tab)
    await page.getByText('检查论文 20', { exact: true }).waitFor()
    assert.equal(await page.getByText('检查论文 21', { exact: true }).count(), 0)
    const scroll = page.locator('[data-paper-list-scroll="true"]')
    assert.equal(await scroll.count(), 1)
    assert.ok(await scroll.evaluate(node => node.scrollHeight > node.clientHeight))
    if (tab === 'pending') {
      const title = page.getByText(longTitle, { exact: true })
      assert.ok((await title.boundingBox()).width > 300)
      await page.setViewportSize({ width: 1000, height: 900 })
      await title.hover()
      await page.getByRole('tooltip').waitFor()
      assert.equal(await page.getByRole('tooltip').innerText(), longTitle)
    }
    await page.screenshot({ path: output + '/workspace-' + tab + '.png', fullPage: true })
    reports.push({ workspace_tab: tab, page_size: 20, internal_scroll: true })
    await context.close()
  }
  for (const [role, path] of [['user', '/upload/tasks/' + '2'.repeat(32)], ['user', '/papers/213/revise'], ['admin', '/admin/papers/213/edit'], ['superadmin', '/admin/papers/213/edit']]) {
    const { context, page, calls } = await contextFor(role)
    await page.goto(origin + path)
    const nav = page.getByRole('navigation', { name: '研究材料大纲', exact: true })
    await nav.getByRole('button', { name: /#14 ·/ }).waitFor()
    await page.waitForTimeout(200)
    const count = calls.length
    await nav.getByRole('button', { name: /#14 ·/ }).click()
    await page.waitForFunction(() => { const target = document.querySelector('[data-state-key="state-13"]'); if (!target) return false; const rect = target.getBoundingClientRect(); return rect.top < innerHeight - 80 && rect.bottom > 80 })
    assert.deepEqual(calls.slice(count).filter(call => call.method !== 'GET' && !call.path.endsWith('/activity')), [])
    await page.screenshot({ path: output + '/outline-' + role + '-' + (path.includes('revise') ? 'revision' : path.includes('upload') ? 'upload' : 'admin') + '.png' })
    reports.push({ host: path, role, outline_jump: true, navigation_writes: 0 })
    await context.close()
  }
  const { context, page } = await contextFor('superadmin', true)
  await page.goto(origin + '/admin/papers/214/edit')
  const message = page.getByText('稿件已交出，当前账号没有编辑权。', { exact: true })
  await message.waitFor()
  await page.waitForTimeout(300)
  assert.equal(await message.count(), 1)
  assert.equal(await page.getByRole('button', { name: '提交审核', exact: true }).isDisabled(), true)
  await page.screenshot({ path: output + '/permission.png' })
  reports.push({ denied_message_count: 1, review_disabled: true })
  await context.close()
  assert.deepEqual(errors, [])
  await writeFile(output + '/report.json', JSON.stringify({ reports, errors }, null, 2))
  console.log(JSON.stringify({ cases: reports.length, errors }))
} finally { await browser.close() }
