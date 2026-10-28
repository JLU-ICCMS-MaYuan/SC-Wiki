// 生产上传页面与真实浏览器事件；API 隔离，验证宿主保存补丁和提交请求。
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const output = process.env.CANDIDATE_BROWSER_OUTPUT || '/tmp/scwiki169-browser'
await mkdir(output, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const task = '9'.repeat(32), item = 'a'.repeat(64), errors = [], results = []
const oldValue = '1. Search for stable ternary hydrides with higher Tc.\n2. Introduce scandium to tune the La–H system.'
const newValue = '1. Explore the composition space of ternary hydrides.\n2. Identify stable La–Sc–H compounds with high transition temperatures.\n3. Examine how scandium changes the electronic and vibrational properties.'
try {
  for (const width of [1500, 390]) {
    const requests = []
    let applied = false, generated = false, version = 1, jobCalls = 0, submitCalls = 0
    const user = { id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' }
    const paper = { title: 'Isolated La–Sc–H candidate verification', year: 2024, authors: ['Fixture author'], journal: 'PNAS',
      paper_type: 'theoretical', theoretical_subtype: 'calculation', superconductor_kind: 'conventional',
      research_motivation: oldValue, material_families: [{id: 1, name: 'Hydrides', name_zh: '氢基超导体'}] }
    const draft = () => ({paper, material_states: [{state_key: 's1', material: 'LaSc2H24', material_name: 'LaSc2H24',
      state_kind: 'theoretical', structure_optimization: 'classical_static', property_modules: [], tc_results: [], properties: [], calculation_context: {}, experimental_context: {}}], structure_candidates: [],
      generation_issues: [{field: 'paper.research_motivation', code: 'conflict', message: '已纠正角色；只保存新候选供人工比较', candidate: 'Legacy candidate must not appear at the top'}]})
    const reason = '本文讨论三元氢化物组成空间及引入 Sc 的动机，因此按研究目标重新归纳；不增加实验实现承诺。'
    const record = () => ({key: 'motivation', item_key: item, field: 'paper.research_motivation', fields: ['paper.research_motivation'], label: '研究驱动力',
      current_value: paper.research_motivation, status: 'supported', required: true, reason: applied ? reason : '保留现有两条动机',
      ai_reason: applied ? reason : '保留现有两条动机', evidences: [], detail_ref: `r${version}`, human_confirmed: true,
      field_decision: {contract: 'field-review-v2', action: 'approve', actor_user_id: 7, occurred_at: '2026-10-22T12:27:53Z'}})
    const candidate = () => generated && !applied ? { id: 'fresh', token: 'candidate-v1', values: {'': newValue}, explanation: reason,
      evidences: [], historical: false, can_apply: true } : null
    const detail = () => ({record: record(), review_token: 'review-token', source_state: 'available', can_approve: false, candidate: candidate()})
    const context = await browser.newContext({viewport: {width, height: 1100}})
    await context.addInitScript(user => { localStorage.setItem('auth_token', 'isolated'); localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh') }, user)
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname
      requests.push({method: request.method(), path})
      const json = body => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(body)})
      if (path === '/api/auth/me') return json({user})
      if (path.endsWith('/activity')) return json({ok: true})
      if (path === '/api/form-definitions') return json(definitions)
      if (path.startsWith('/api/form-definitions/')) return json(definitions.find(d => path.includes(d.definition_key)))
      if (path === '/api/classification-catalogs') return json({material_families: paper.material_families, structure_families: [], material_dimensionalities: []})
      if (path === '/api/rag/space-groups') return json({space_groups: []})
      if (path.endsWith('/preparation-progress')) return json({percent: 20})
      if (path.endsWith('/summary')) return json({version: `v${version}`, records: [record()], needs_check: false})
      if (path.endsWith('/field-detail')) return json(url.searchParams.get('history') === 'true' ? {history: []} : detail())
      if (path.endsWith('/jobs') && request.method() === 'POST') {
        const body = request.postDataJSON(); assert.equal(body.purpose, 'field'); assert.deepEqual(body.retry_keys, ['motivation'])
        jobCalls++; generated = true; version++
        return json({id: 'explicit-job', status: 'completed', version: `v${version}`, records: [record()]})
      }
      if (path.endsWith('/field-candidate/prepare')) {
        assert.equal(request.postDataJSON().candidate_token, 'candidate-v1')
        return json({preparation_id: 'prepared', patches: [{key: 'motivation', item_key: item, field: 'paper.research_motivation', values: {'': newValue}}]})
      }
      if (path.endsWith('/field-candidate/finalize')) {
        assert.equal(paper.research_motivation, newValue); assert.equal(request.postDataJSON().preparation_id, 'prepared')
        applied = true; version++; return json(detail())
      }
      if (path.endsWith('/draft-state')) return json({version: `v${version}`, draft: draft()})
      if (path === '/api/rag/evidence/draft' && request.method() === 'PATCH') {
        const body = request.postDataJSON(); assert.equal(body.expected_version, `v${version}`)
        assert.equal(body.changes.length, 1)
        assert.deepEqual(body.changes[0].path, ['paper', 'research_motivation'])
        assert.equal(body.changes[0].before, oldValue); assert.equal(body.changes[0].value, newValue)
        paper.research_motivation = newValue; version++; return json({version: `v${version}`, changed: true})
      }
      if (path.endsWith('/submit-check')) { submitCalls++; assert.ok(applied); return json({status: 'completed', version: `v${version}`, records: [record()]}) }
      if (path.endsWith('/submit')) return json({paper_id: 9999})
      if (path.endsWith('/draft')) return json({data: draft()})
      if (path === `/api/upload-tasks/${task}`) return json({data: {task_id: task, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5}})
      if (path.endsWith('/parsing')) return json({data: {status: 'ready', stage: 'ready', files: [], chunks: [], summary: {status: 'ready', completed: 1, total: 1}, next_poll_ms: null}})
      if (path === '/api/upload-tasks') return json({data: []})
      if (request.method() !== 'GET') throw new Error(`unexpected mutation ${path}`)
      return json({items: [], total: 0})
    })
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
    const url = `${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}/upload/tasks/${task}`
    await page.goto(url)
    const open = () => page.locator('[data-evidence-key="motivation"]').first().click()
    await open()
    await page.getByRole('button', {name: '大模型核对', exact: true}).click()
    await page.getByRole('dialog').waitFor({state: 'hidden'})
    await open()
    await page.getByRole('tab', {name: '字段设置'}).click()
    await page.getByRole('button', {name: '应用 AI 候选值'}).waitFor()
    assert.equal(await page.getByLabel('当前值', {exact: true}).inputValue(), oldValue)
    assert.equal(await page.getByText('Legacy candidate must not appear at the top').count(), 0)
    const drawer = page.locator('.evidence-review-drawer')
    await page.getByRole('button', {name: '应用 AI 候选值'}).scrollIntoViewIfNeeded()
    assert.equal(await drawer.evaluate(n => n.scrollWidth <= n.clientWidth), true)
    await drawer.screenshot({path: `${output}/candidate-${width}.png`})
    await page.getByRole('button', {name: '应用 AI 候选值'}).click()
    await drawer.waitFor({state: 'hidden'})
    assert.equal(paper.research_motivation, newValue)
    await page.reload(); await open()
    await page.getByRole('tab', {name: '字段设置'}).click()
    await page.getByText('暂无待应用候选。主动点击“大模型核对”后，可在这里查看新候选。').waitFor()
    assert.equal(await page.getByLabel('当前值', {exact: true}).inputValue(), newValue)
    await page.getByRole('button', {name: '关闭来源详情'}).click()
    await page.getByRole('button', {name: '提交审核', exact: true}).click()
    await page.waitForURL(/papers\/9999/, {timeout: 5000}).catch(async () => {
      await page.screenshot({path: `${output}/submit-failure-${width}.png`})
    })
    assert.equal(jobCalls, 1); assert.equal(submitCalls, 1)
    results.push({width, jobCalls, submitCalls, applied, requests})
    await context.close()
  }
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({results, errors}, null, 2))
  console.log(JSON.stringify({checks: results.map(({requests, ...r}) => r), errors}))
} finally { await browser.close() }
