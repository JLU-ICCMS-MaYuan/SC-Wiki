// 正式上传页面的浏览器回归；业务 API 全部隔离，不修改用户草稿。
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const output = process.env.GRAPH_TITLE_BROWSER_OUTPUT || '/tmp/scwiki173-browser'
await mkdir(output, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const task = '173'.padEnd(32, '0'), errors = [], results = []
const original = 'Superconductivity in compressed hydrides'
const updated = 'Electron phonon coupling in compressed hydrides'
try {
  for (const width of [1440, 390]) {
    let version = 1, saves = 0, submitChecks = 0, releaseSubmit
    const pendingSubmit = new Promise(resolve => { releaseSubmit = resolve })
    const user = { id: 7, username: 'isolated', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' }
    const paper = { title: 'Original paper title', knowledge_graph_title: original, year: 2026,
      authors: ['Fixture author'], journal: 'Fixture journal', paper_type: 'review',
      material_families: [{ id: 1, name: 'Hydrides', name_zh: '氢基超导体' }] }
    const draft = () => ({ paper, material_states: [], structure_candidates: [] })
    const record = () => ({ key: 'graph-title', item_key: 'a'.repeat(64), field: 'paper.knowledge_graph_title',
      label: '图谱科学标题', current_value: paper.knowledge_graph_title, status: 'uncertain',
      required: true, reason: '请核对标题与论文的核心贡献是否一致。', evidences: [] })
    const context = await browser.newContext({ viewport: { width, height: 1000 } })
    await context.addInitScript(user => {
      localStorage.setItem('auth_token', 'isolated'); localStorage.setItem('auth_user', JSON.stringify(user))
      localStorage.setItem('sc-wiki.language', 'zh')
    }, user)
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname
      const json = body => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path.endsWith('/activity')) return json({ ok: true })
      if (path === '/api/form-definitions') return json(definitions)
      if (path.startsWith('/api/form-definitions/')) return json(definitions.find(d => path.includes(d.definition_key)))
      if (path === '/api/classification-catalogs') return json({ material_families: paper.material_families, structure_families: [], material_dimensionalities: [] })
      if (path === '/api/rag/space-groups') return json({ space_groups: [] })
      if (path.endsWith('/summary')) return json({ version: `v${version}`, records: [record()], needs_check: false })
      if (path.endsWith('/field-detail')) return json({ record: record(), source_state: 'empty', review_token: 'fixture-token', history: [], candidate: null })
      if (path.endsWith('/draft-state')) return json({ version: `v${version}`, draft: draft() })
      if (path === '/api/rag/evidence/draft' && request.method() === 'PATCH') {
        const body = request.postDataJSON()
        assert.equal(body.expected_version, `v${version}`)
        assert.deepEqual(body.changes, [{ path: ['paper', 'knowledge_graph_title'], before: paper.knowledge_graph_title, value: updated }])
        paper.knowledge_graph_title = updated; version++; saves++
        return json({ changed: true, version: `v${version}` })
      }
      if (path.endsWith('/submit-check')) {
        submitChecks++; await pendingSubmit
        return json({ status: 'completed', version: `v${version}`, records: [record()] })
      }
      if (path.endsWith('/preparation-progress')) return json({ percent: 10 })
      if (path.endsWith('/draft')) return json({ data: draft() })
      if (path === `/api/upload-tasks/${task}`) return json({ data: { task_id: task, filename: 'isolated-title.pdf',
        processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
      if (path.endsWith('/parsing')) return json({ data: { status: 'ready', stage: 'ready', files: [], chunks: [],
        summary: { status: 'ready', completed: 1, total: 1 }, next_poll_ms: null } })
      if (path === '/api/upload-tasks') return json({ data: [] })
      if (request.method() !== 'GET') throw new Error(`Unexpected mutation: ${path}`)
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}/upload/tasks/${task}`)
    const field = page.locator('[data-issue-field="paper.knowledge_graph_title"]')
    const input = field.locator('input')
    await input.waitFor()
    assert.equal(await input.inputValue(), original)
    assert.equal(await field.getByText(/paper\.knowledge_graph_title/).isVisible(), true)
    await field.locator('label[role="button"]').waitFor()
    assert.equal(await page.locator('[data-evidence-fallback]').count(), 0)
    await field.scrollIntoViewIfNeeded()
    const box = await field.boundingBox()
    assert.ok(box.x >= 0 && box.x + box.width <= width + 1)
    await page.screenshot({ path: `${output}/form-${width}.png` })
    await field.locator('label').click()
    await page.getByRole('tab', { name: '来源核对' }).click()
    await page.getByText('请核对标题与论文的核心贡献是否一致。', { exact: true }).first().waitFor()
    await page.getByRole('tab', { name: '字段设置' }).click()
    assert.equal(await page.getByLabel('当前值', { exact: true }).inputValue(), original)
    await page.getByLabel('当前值', { exact: true }).fill(updated)
    await page.getByRole('button', { name: '应用修改', exact: true }).waitFor()
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent === '应用修改' && !button.disabled))
    await page.screenshot({ path: `${output}/settings-${width}.png` })
    await page.getByRole('button', { name: '应用修改', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'hidden' })
    assert.equal(await input.inputValue(), updated)
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/evidence/draft') && response.request().method() === 'PATCH'),
      page.getByRole('button', { name: '立即保存', exact: true }).click(),
    ])
    assert.equal(saves, 1)
    await page.reload()
    await input.waitFor()
    assert.equal(await input.inputValue(), updated)
    assert.equal(await page.locator('[data-issue-field="paper.title"] input').inputValue(), 'Original paper title')
    await page.getByRole('button', { name: '提交审核', exact: true }).click()
    await page.waitForFunction(() => document.querySelector('[data-issue-field="paper.knowledge_graph_title"] input')?.disabled)
    assert.equal(await input.isDisabled(), true)
    releaseSubmit()
    await page.waitForFunction(() => !document.querySelector('[data-issue-field="paper.knowledge_graph_title"] input')?.disabled)
    assert.equal(submitChecks, 1)
    results.push({ width, saves, submitChecks, value: paper.knowledge_graph_title, fallback: 0 })
    await context.close()
  }
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({ results, errors }, null, 2))
  console.log(JSON.stringify({ results, errors }))
} finally { await browser.close() }
