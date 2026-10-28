// 生产 React 路由、真实浏览器事件；所有 API 被隔离夹具拦截，不修改用户草稿。
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_PATH})
const output = process.env.REVIEW_BROWSER_OUTPUT || '/tmp/scwiki147-human-review'
await mkdir(output, {recursive: true})
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const taskId = '9'.repeat(32), item = 'a'.repeat(64), requests = [], errors = []
const user = {id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active'}
const paper = {title: 'Field review isolated browser verification', year: 2024, authors: [], journal: 'PNAS', paper_type: 'theoretical', theoretical_subtype: 'calculation',
  superconductor_kind: 'conventional', key_finding: 'A ternary hydride has a high critical temperature.', material_families: []}
let decision, revision = 0, releaseFirstDetail, firstDetail = true, manualWrites = 0
const originalReason = '摘要支持当前概括，等待人工确认。'
const record = () => ({key: 'finding', item_key: item, field: 'paper.key_finding', fields: ['paper.key_finding'], label: '主要发现',
  current_value: paper.key_finding, required: true, status: decision?.action === 'approve' ? 'supported' : decision ? 'uncertain' : 'unchecked',
  reason: originalReason, ai_reason: originalReason, evidences: [], detail_ref: `r${revision}`, field_decision: decision,
  human_confirmed: decision?.action === 'approve', pending_review: !decision, human_modified: manual.changed})
const detail = () => ({record: {...record(), evidences: [{file_id: 'main', source_name: 'fixture.pdf', page_start: 1, quote: 'The ternary hydride exhibits a high critical temperature.'}]},
  review_token: `token${revision}`, can_approve: !manual.changed && decision?.action !== 'approve', source_state: 'available',
  approval_state: decision?.action === 'approve' ? 'human_approved' : manual.changed ? 'modification_required' : 'ready',
  approval_message: manual.changed ? '此字段已修改，请填写人工修改理由及证据说明，并完成大模型核对。' : ''})
let manual = {changed: false, reason: '', no_evidence_reason: '', items: []}
try {
  const context = await browser.newContext({viewport: {width: 1500, height: 1100}})
  await context.addInitScript(({user}) => {
    localStorage.setItem('auth_token', 'isolated'); localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh')
  }, {user})
  await context.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    requests.push({method: request.method(), path})
    const json = (body, status = 200) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify(body)})
    if (path === '/api/auth/me') return json({user})
    if (path.endsWith('/activity')) return json({ok: true})
    if (path === '/api/form-definitions') return json(definitions)
    if (path.startsWith('/api/form-definitions/')) return json(definitions.find(d => path.includes(d.definition_key)))
    if (path === '/api/classification-catalogs') return json({material_families: [], structure_families: [], material_dimensionalities: []})
    if (path === '/api/rag/space-groups') return json({space_groups: []})
    if (path.endsWith('/summary')) return json({version: 'draft-v1', records: [record()], needs_check: false})
    if (path.endsWith('/field-detail')) {
      if (new URL(request.url()).searchParams.get('history') === 'true') return json({history: []})
      if (firstDetail) { firstDetail = false; await new Promise(resolve => {releaseFirstDetail = resolve}) }
      return json(detail())
    }
    if (path.endsWith('/field-decision')) {
      const body = request.postDataJSON()
      if (body.action === 'approve' && manual.changed) return json({detail: {code: 'evidence_review_required',
        message: '此字段已修改，请填写人工修改理由及证据说明，并完成大模型核对。'}}, 409)
      assert.equal(body.review_token, `token${revision}`); assert.equal(body.item_key, item); assert.equal(body.reason, undefined)
      decision = {contract: 'field-review-v2', action: body.action, actor_user_id: 7, actor_name: 'fixture', occurred_at: new Date().toISOString()}
      revision++
      return json(detail())
    }
    if (path.endsWith('/manual-context')) return json({version: 'field-v1', record: record()})
    if (path.includes('/manual/')) {
      if (request.method() === 'PUT') { manualWrites++; const b = request.postDataJSON(); manual = {...manual, changed: true, reason: b.reason, no_evidence_reason: b.no_evidence_reason} }
      return json({ok: true, data: manual})
    }
    if (path.endsWith('/draft-state')) return json({version: 'draft-v1', draft: {paper, material_states: []}})
    if (path.endsWith('/draft')) { assert.equal(request.method(), 'GET'); return json({data: {paper, material_states: [], structure_candidates: []}}) }
    if (path === `/api/upload-tasks/${taskId}`) return json({data: {task_id: taskId, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5}})
    if (path.endsWith('/parsing')) return json({data: {status: 'ready', stage: 'ready', files: [], chunks: [], summary: {status: 'ready', completed: 1, total: 1}, next_poll_ms: null}})
    if (path === '/api/upload-tasks') return json({data: []})
    if (request.method() !== 'GET') throw new Error(`不应发出的写请求：${path}`)
    return json({items: [], total: 0})
  })
  const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
  await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}/upload/tasks/${taskId}`)
  const open = () => page.locator('[data-evidence-key="finding"]').first().click()
  await open()
  await page.getByText('正在加载此字段的原文依据…').waitFor()
  assert.equal(await page.getByText(/未找到可定位的论文原文依据/).count(), 0)
  releaseFirstDetail()
  await page.getByText('The ternary hydride exhibits a high critical temperature.').waitFor()
  await page.getByRole('button', {name: '人工审核通过', exact: true}).waitFor()
  assert.equal(await page.getByLabel('人工修改判断理由（必填）').count(), 0)
  await page.waitForFunction(() => { const d=document.querySelector('.evidence-review-drawer'); const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='人工审核通过'); return d && Math.abs(d.getBoundingClientRect().right-innerWidth)<2 && b && !b.disabled })
  await page.screenshot({path: `${output}/approval-sidebar.png`})
  await page.getByRole('button', {name: '人工审核通过', exact: true}).click()
  await page.getByRole('dialog').waitFor({state: 'hidden'})
  assert.equal(await page.locator('[data-evidence-problem="true"]').count(), 0)
  await open()
  assert.equal(await page.getByRole('button', {name: '人工审核通过', exact: true}).isDisabled(), true)
  assert.equal(await page.getByRole('button', {name: '人工审核不通过', exact: true}).isEnabled(), true)
  await page.waitForFunction(() => Math.abs(document.querySelector('.evidence-review-drawer').getBoundingClientRect().right - innerWidth) < 2)
  await page.locator('.evidence-review-drawer').screenshot({path: `${output}/approved-disabled-sidebar.png`})
  await page.getByLabel('关闭来源详情').click()
  await page.getByRole('dialog').waitFor({state: 'hidden'})
  await page.reload(); await open()
  await page.getByText('fixture ·', {exact: false}).waitFor()
  assert.equal(await page.getByRole('button', {name: '人工审核通过', exact: true}).isDisabled(), true)
  assert.equal(await page.getByRole('button', {name: '人工审核不通过', exact: true}).isEnabled(), true)
  await page.getByRole('button', {name: '人工审核不通过', exact: true}).click()
  await page.getByLabel('人工修改判断理由（必填）').waitFor()
  await page.getByLabel('人工修改判断理由（必填）').fill('原说明遗漏适用范围，补充说明。')
  await page.getByLabel('不提供证据', {exact: true}).check()
  await page.getByLabel('不提供证据的理由（必填）').fill('沿用已显示的原文，不新增附件。')
  await page.getByRole('button', {name: '保存', exact: true}).click()
  await page.getByText('已保存', {exact: true}).first().waitFor()
  assert.equal(manualWrites, 1)
  assert.equal(await page.getByRole('dialog').count(), 1, '保存应保留侧栏')
  await page.screenshot({path: `${output}/manual-save-sidebar.png`})
  manual = {changed: true, reason: '', no_evidence_reason: '', items: []}
  decision = undefined; revision++; paper.key_finding = 'Changed scientific finding'
  await page.reload(); await open()
  await page.getByText('此字段已修改，请填写人工修改理由及证据说明，并完成大模型核对。', {exact: true}).waitFor()
  assert.equal(await page.getByRole('button', {name: '人工审核通过', exact: true}).isEnabled(), true)
  await page.getByRole('button', {name: '人工审核通过', exact: true}).click()
  await page.waitForTimeout(200)
  assert.equal(decision, undefined)
  assert.equal(await page.getByRole('dialog').count(), 1)
  await page.screenshot({path: `${output}/modified-refusal-sidebar.png`})
  assert.equal(requests.filter(r => r.path.endsWith('/jobs') || r.path.endsWith('/submit-check')).length, 0)
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({passed: true, requests, manualWrites, errors}, null, 2))
  console.log(JSON.stringify({passed: true, output, manualWrites, modelJobs: 0}))
} finally { await browser.close() }
