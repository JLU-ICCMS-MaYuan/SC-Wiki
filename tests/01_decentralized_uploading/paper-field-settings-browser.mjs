// 真实 React 路由与浏览器事件；HTTP 夹具隔离所有业务请求，不触碰用户草稿。
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5198'
const output = process.env.ARTIFACT_DIR || '/tmp/scwiki148-field-settings'
await mkdir(output, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const labels = { title: '标题', abstract: '摘要', summary: '总结', key_finding: '主要发现', research_motivation: '研究动机', keywords_tags: '关键词', methodology: '研究方法' }
const results = []
try {
  for (const role of ['upload', 'revision', 'admin', 'superadmin']) {
    const admin = ['admin', 'superadmin'].includes(role), taskId = '8'.repeat(32)
    const paper = { id: 148, title: 'Sidebar field settings fixture', authors: [], year: 2026, journal: 'Test', review_status: 'pending',
      abstract: 'Original abstract', summary: 'Original summary', key_finding: 'Original finding', research_motivation: 'Original motivation',
      keywords_tags: ['hydride', 'high pressure'], methodology: ['DFT', 'SSCHA'], paper_type: 'theoretical', superconductor_kind: 'conventional', material_families: [] }
    const draft = { paper, material_states: [], structure_candidates: [] }
    const requests = [], errors = [], patches = []
    let version = 1, failNextSave = true
    const records = () => Object.entries(labels).map(([field, label]) => ({ key: field, item_key: field, field: `paper.${field}`, label,
      current_value: paper[field], required: true, status: 'supported', reason: '隔离夹具：原文支持当前内容', evidences: [] }))
    const user = { id: 7, username: 'fixture', role: admin ? role : 'user', is_admin: admin, is_superadmin: role === 'superadmin', is_approved: true, is_email_verified: true, account_status: 'active' }
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    await context.addInitScript(user => {
      localStorage.setItem('auth_token', 'fixture'); localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh')
    }, user)
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname
      requests.push({ method: request.method(), path })
      const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path.endsWith('/activity')) return json({ ok: true })
      if (path === '/api/form-definitions') return json(definitions)
      if (path.startsWith('/api/form-definitions/')) return json(definitions.find(d => path.includes(d.definition_key)))
      if (path === '/api/classification-catalogs') return json({ material_families: [], structure_families: [], material_dimensionalities: [] })
      if (path.endsWith('/space-groups')) return json({ space_groups: [] })
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path === '/api/admin/papers/148') return json({ ...paper, keywords_tags: JSON.stringify(paper.keywords_tags), methodology: JSON.stringify(paper.methodology), material_states: [] })
      if (path.endsWith('/summary')) return json({ version: String(version), records: records(), needs_check: false })
      if (path.endsWith('/field-detail')) return json({ record: {}, history: [], source_state: 'empty', review_token: 'token', can_approve: true })
      if (path.endsWith('/draft-state')) return json({ staged: false, version: String(version), draft })
      if (path.endsWith('/manual-context')) return json({ version: String(version), record: records().find(r => r.item_key === request.postDataJSON()?.item_key) || records()[0] })
      if (path.includes('/manual/')) return json({ ok: true, data: { changed: false, reason: '', items: [], history: [] } })
      if (path === '/api/rag/evidence/draft' && request.method() === 'PATCH') {
        const body = request.postDataJSON()
        if (failNextSave) { failNextSave = false; return json({ detail: '隔离夹具：保存失败，请重试' }, 503) }
        assert.equal(body.expected_version, String(version))
        for (const change of body.changes) {
          assert.equal(change.path[0], 'paper'); assert.equal(change.path.length, 2)
          assert.deepEqual(change.before, paper[change.path[1]] ?? null, '保存前值必须与 canonical 草稿完全一致')
          if (change.remove) delete paper[change.path[1]]
          else paper[change.path[1]] = change.value
        }
        patches.push(body.changes); version++
        return json({ version: String(version), changed: true, draft_version: version })
      }
      if (path.endsWith('/revision-draft')) return json({ ok: true, data: draft, revision_id: 'revision-148', draft_version: version })
      if (path.endsWith('/draft')) { assert.equal(request.method(), 'GET'); return json({ data: draft }) }
      if (path === `/api/upload-tasks/${taskId}`) return json({ data: { task_id: taskId, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
      if (path.endsWith('/parsing')) return json({ data: { status: 'ready', stage: 'ready', files: [], chunks: [], summary: { status: 'ready', completed: 1, total: 1 }, next_poll_ms: null } })
      if (path === '/api/upload-tasks') return json({ data: [] })
      assert.equal(request.method(), 'GET', `非预期写请求 ${path}`)
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    const path = admin ? '/admin/papers/148/edit' : role === 'revision' ? '/papers/148/revise' : `/upload/tasks/${taskId}`
    await page.goto(base + path)
    const drawer = page.locator('.evidence-review-drawer')
    const open = async field => {
      await page.locator(`[data-issue-field="paper.${field}"] label[data-evidence-key]`).click()
      await drawer.getByRole('tab', { name: '字段设置' }).click()
      await drawer.getByLabel('字段名称（key）').waitFor()
    }
    for (const field of Object.keys(labels)) {
      await open(field)
      const expected = ['methodology', 'keywords_tags'].includes(field) ? (Array.isArray(paper[field]) ? paper[field] : JSON.parse(paper[field])).join('\n') : paper[field]
      assert.equal(await drawer.getByLabel('当前值', { exact: true }).inputValue(), expected)
      await drawer.getByRole('button', { name: '取消', exact: true }).click()
      await drawer.waitFor({ state: 'hidden' })
    }
    assert.equal(patches.length, 0)
    await open('methodology')
    await drawer.getByLabel('当前值', { exact: true }).fill('DFT\nSSCHA revised')
    await drawer.getByRole('tab', { name: '来源核对' }).click()
    assert.equal(await drawer.getByRole('button', { name: '人工审核通过', exact: true }).isDisabled(), true)
    assert.equal(await drawer.getByText('返回编辑当前值', { exact: true }).count(), 0)
    assert.equal(await drawer.getByText('返回修改记录', { exact: true }).count(), 0)
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 })
      // 等待抽屉进入视口；不通过 JS click 绕过点击位置问题。
      await page.waitForFunction(() => Math.abs(document.querySelector('.evidence-review-drawer').getBoundingClientRect().right - innerWidth) < 2)
      const boxes = await Promise.all(['人工审核不通过', '人工审核通过', '大模型核对'].map(name => drawer.getByRole('button', { name, exact: true }).boundingBox()))
      assert.ok(boxes.every(box => Math.abs(box.y - boxes[0].y) < 1), '三个按钮必须在同一行')
      assert.ok(await drawer.evaluate(el => el.scrollWidth <= el.clientWidth), '侧栏不能横向溢出')
      if (role === 'upload') await drawer.screenshot({ path: `${output}/actions-${width}.png` })
    }
    await page.setViewportSize({ width: 1440, height: 1000 })
    await drawer.getByRole('tab', { name: '历史记录' }).click()
    await drawer.getByRole('tab', { name: '字段设置' }).click()
    assert.equal(await drawer.getByLabel('当前值', { exact: true }).inputValue(), 'DFT\nSSCHA revised')
    await drawer.getByLabel('关闭来源详情').click()
    await page.getByRole('button', { name: '继续编辑', exact: true }).click()
    assert.equal(await drawer.getByLabel('当前值', { exact: true }).inputValue(), 'DFT\nSSCHA revised')
    await drawer.screenshot({ path: `${output}/${role}-settings.png` })
    await drawer.getByRole('button', { name: '应用修改', exact: true }).click()
    await drawer.waitFor({ state: 'hidden' })
    const save = page.getByRole('button', { name: admin ? '保存修改' : '立即保存', exact: true })
    await save.click()
    await page.getByText(/隔离夹具：保存失败/).first().waitFor()
    assert.equal(patches.length, 0)
    await save.click()
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].some(b => b.textContent === '正在保存'))
    await open('methodology')
    assert.equal(await drawer.getByLabel('当前值', { exact: true }).inputValue(), 'DFT\nSSCHA revised')
    assert.equal(patches.length, 1)
    assert.deepEqual(patches[0].map(c => c.path), [['paper', 'methodology']])
    assert.deepEqual(paper.methodology, ['DFT', 'SSCHA revised'])
    await page.reload(); await open('methodology')
    assert.equal(await drawer.getByLabel('当前值', { exact: true }).inputValue(), 'DFT\nSSCHA revised')
    const modelRequests = requests.filter(r => /\/(jobs|preflight|submit-check)$/.test(r.path)).length
    assert.equal(modelRequests, 0); assert.deepEqual(errors, [])
    results.push({ role, route: path, fields: Object.keys(labels), modelRequests, patches, errors, widths: [1440, 390, 320], saveRetry: true, reload: true })
    await context.close()
  }
  await writeFile(`${output}/results.json`, JSON.stringify({ passed: true, boundary: '真实前端路由；HTTP 保存与读取使用隔离内存夹具，未调用真实数据库或模型', results }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: true, roles: results.length, output }))
} finally { await browser.close() }
