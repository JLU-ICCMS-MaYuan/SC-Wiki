// 真实页面和输入事件；全部 API 拦截为隔离夹具，成功保存的请求可交给 SQLite 往返测试。
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
const payloads = []
const taskId = '9'.repeat(32)
const makeRecord = (key, predicted = false) => ({
  record_key: key, module_code: 'superconductive_properties', record_type: predicted ? 'predicted_tc' : 'measured_tc',
  property_code: 'tc', definition_key: `record.superconductive_properties.${predicted ? 'predicted_tc.allen_dynes' : 'measured_tc.resistivity'}`,
  definition_version: 1, name_raw: 'critical temperature', method_code: predicted ? 'allen_dynes' : 'resistivity',
  value_kind: 'number', value_raw: predicted ? '' : 'wrong 3.78 mK', unit_raw: 'mK', canonical_unit: 'K', value_number: 3.78,
  payload: predicted ? { calculation_conditions: {}, parameters: {} } : { experimental_conditions: { description: 'Four-probe measurement' } },
})
try {
  for (const mode of ['admin', 'superadmin', 'upload']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] })
    const user = { id: 7, username: 'fixture', role: mode === 'superadmin' ? mode : 'admin', is_admin: true, is_approved: true, is_email_verified: true, account_status: 'active' }
    await context.addInitScript(({ user, taskId }) => {
      localStorage.setItem('auth_token', 'fixture-only'); localStorage.setItem('auth_user', JSON.stringify(user))
      localStorage.setItem('sc-wiki.language', 'zh'); localStorage.setItem('scwiki_active_upload_task:7', taskId)
    }, { user, taskId })
    let states = [false, true].map((_, i) => ({
      state_key: `state-${i}`, material: 'Sn', material_name: `样品 ${i + 1}`, element_count: 1,
      state_kind: 'experimental', material_dimensionality: 'three_dimensional', crystal_system: 'tetragonal',
      structures: [], structure_families: [], property_modules: [{
        module_key: `module-${i}`, module_code: 'superconductive_properties', definition_key: 'module.superconductive_properties', definition_version: 1,
        records: [makeRecord(i ? 'tc-measured' : 'tc-predicted', !i)],
      }],
    }))
    let detail = { id: 990094, title: '隔离 Tc 紧凑布局验收', year: 2026, authors: [], journal: 'Test', paper_type: 'experimental', superconductor_kind: 'conventional', review_status: 'pending', material_families: [{ id: 8, name: '单质超导体', status: 'confirmed' }], key_properties: [] }
    const current = () => states[1].property_modules[0].records[0]
    let version = 1, accepted, failSave = false, readOnly = false, saves = 0, writes = 0, loads = 0
    const evidence = () => ({ key: 'tc', item_key: 'tc', state_key: 'state-1', module_key: 'module-1', record_key: 'tc-measured',
      field: 'material_states[1].property_modules[0].records[0]', fields: ['material_states[1].property_modules[0].records[0].value_number'],
      label: '测量 Tc', current_value: current(), status: 'uncertain', reason: '需要人工核对', evidences: [],
      stale: version > 1, ...(accepted ? { proposal_draft: accepted } : {}),
    })
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (req.method() === 'PUT') writes++
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/admin/papers/990094') {
        if (req.method() === 'PUT') detail = { ...detail, ...req.postDataJSON() }
        return json({ ...detail, material_states: states })
      }
      if (path === '/api/form-definitions') return json(definitions)
      if (path.startsWith('/api/form-definitions/')) return json(definitions.find(d => path.includes(d.definition_key)))
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path === '/api/classification-catalogs') return json({ material_families: [{ id: 8, name: '单质超导体' }], structure_families: [], material_dimensionalities: [] })
      if (path === '/api/rag/space-groups') return json({ space_groups: [] })
      if (path === '/api/rag/llm/current') return json({})
      if (path.endsWith('/preflight')) return json({ version: `v${version}`, records: mode === 'upload' ? [] : [evidence()], needs_check: true })
      if (path.endsWith('/scientific-draft') || path.endsWith('/draft')) {
        if (req.method() === 'GET') return json({ data: { paper: detail, material_states: states, structure_candidates: [] } })
        if (failSave) return json({ detail: '隔离保存失败' }, 500)
        const body = req.postDataJSON()
        states = body.material_states; saves++; version++; accepted = undefined
        payloads.push(body)
        return json({ ok: true, data: { revision_bumped: false } })
      }
      if (path.endsWith('/proposals')) {
        accepted = req.postDataJSON(); assert.equal(accepted.expected_version, `v${version}`)
        return json({ draft: accepted })
      }
      if (path === `/api/upload-tasks/${taskId}`) return json({ data: { task_id: taskId, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
      if (path === '/api/upload-tasks') return json({ data: [] })
      if (path.endsWith('/parsing')) return json({ data: { status: readOnly ? 'reading' : 'ready', stage: 'ready', files: [], chunks: [], summary: { status: 'ready', completed: 1, total: 1 }, next_poll_ms: null, partial_draft: { paper: detail, material_states: states } } })
      assert(!path.endsWith('/jobs') && !path.endsWith('/review'), '本次操作不得调用 AI 或正式批准')
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) loads++ })
    await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}${mode === 'upload' ? '/upload' : '/admin/papers/990094/edit'}`)
    await page.getByRole('button', { name: '全部展开', exact: true }).click()
    const card = page.getByTestId('property-record-tc-measured')
    const input = card.getByLabel('Tc 值', { exact: true })
    await input.waitFor()
    const save = page.getByRole('button', { name: mode === 'upload' ? '立即保存' : '保存修改', exact: true })
    assert.equal(await card.getByLabel('原始值', { exact: true }).count(), 0)
    assert.equal(await card.getByText('原始记录', { exact: true }).count(), 0)
    assert.equal(await card.getByLabel('数值', { exact: true }).count(), 0)
    // 改变实际卡片内容宽度，验证容器断点，而非只比较 CSS 源码。
    for (const [width, columns] of [[700, 4], [640, 4], [500, 2], [400, 2], [350, 1]]) {
      await card.evaluate((el, width) => { el.style.boxSizing = 'content-box'; el.style.width = `${width}px` }, width)
      const layout = await card.getByTestId('tc-core-row').evaluate(el => ({ columns: getComputedStyle(el).gridTemplateColumns.split(' ').length, width: el.clientWidth, scroll: el.scrollWidth }))
      assert.equal(layout.columns, columns, `${mode} ${width}px 列数`)
      assert(layout.scroll <= layout.width + 1, '核心行不得溢出')
      const row = await card.getByTestId('tc-core-row').boundingBox()
      const conditions = await card.getByLabel('实验 Conditions').evaluate(el => ({ width: el.closest('.MuiFormControl-root').getBoundingClientRect().width }))
      assert(Math.abs(row.width - conditions.width) < 3, '实验条件占满整行')
    }
    await card.evaluate(el => { el.style.width = ''; el.style.boxSizing = '' })
    if (process.env.TC_SCREENSHOT && mode === 'admin') await card.screenshot({ path: process.env.TC_SCREENSHOT })
    await input.click(); assert.equal(await page.getByRole('dialog').count(), 0)
    await input.press('ControlOrMeta+A'); await input.pressSequentially('0.003')
    assert.equal(await input.inputValue(), '0.003')
    await input.fill('1e-')
    const beforeInvalid = writes
    await save.click(); await page.waitForTimeout(100)
    assert.equal(writes, beforeInvalid, '非法输入不得发起保存请求')
    assert.equal(await input.inputValue(), '1e-')
    await page.evaluate(() => navigator.clipboard.writeText('4.25'))
    await input.click(); await input.press('ControlOrMeta+A'); await input.press('ControlOrMeta+V')
    assert.equal(await input.inputValue(), '4.25')
    await card.getByRole('checkbox', { name: '代表结果' }).check()
    if (mode !== 'upload') {
      await input.evaluate(el => el.scrollIntoView({ block: 'center' }))
      await page.waitForTimeout(400)
      const top = (await input.boundingBox()).y, initialLoads = loads
      await card.getByRole('button', { name: 'Tc 值', exact: true }).click()
      assert((await page.getByRole('dialog').innerText()).includes('"value_number": 4.25'), '核对侧栏显示当前 Tc')
      const reason = page.getByLabel('人工核对理由')
      await reason.fill('依据原文核对当前 Tc，以更正后的值为准')
      failSave = true
      await page.getByRole('button', { name: '完成', exact: true }).click()
      await page.getByText(/当前编辑尚未保存成功/).waitFor()
      assert.equal(await reason.inputValue(), '依据原文核对当前 Tc，以更正后的值为准')
      failSave = false
      await page.getByRole('button', { name: '完成', exact: true }).click()
      await page.getByRole('dialog').waitFor({ state: 'detached' })
      await page.waitForTimeout(450)
      assert.equal(accepted.accepted, true)
      assert.equal(loads, initialLoads)
      assert(Math.abs((await input.boundingBox()).y - top) < 4, '完成核对后页面位置保持')
    } else {
      await Promise.all([page.waitForResponse(r => r.url().endsWith('/draft') && r.request().method() === 'PUT'), save.click()])
    }
    assert.equal(current().value_number, 4.25)
    assert.equal(current().value_raw, '4.25'); assert.equal(current().unit_raw, 'K')
    assert.equal(current().is_representative, true)
    assert.equal(states[0].property_modules[0].records[0].value_number, 3.78)
    await page.reload(); await page.getByRole('button', { name: '全部展开', exact: true }).click(); await input.waitFor()
    assert.equal(await input.inputValue(), '4.25')
    await input.fill('')
    const beforeClear = writes
    await save.click(); await page.waitForTimeout(100)
    assert.equal(writes, beforeClear)
    await input.fill('0')
    await Promise.all([page.waitForResponse(r => /\/(scientific-draft|draft)$/.test(r.url()) && r.request().method() === 'PUT'), save.click()])
    assert.equal(current().value_number, 0)
    assert.equal(current().value_raw, '0')
    await card.getByRole('combobox', { name: '值类型' }).click()
    await page.getByRole('option', { name: '范围', exact: true }).click()
    await card.getByLabel('下界', { exact: true }).fill('2')
    await card.getByLabel('上界', { exact: true }).fill('5')
    await Promise.all([page.waitForResponse(r => /\/(scientific-draft|draft)$/.test(r.url()) && r.request().method() === 'PUT'), save.click()])
    assert.equal(current().value_number, null); assert.equal(current().value_min, 2); assert.equal(current().value_max, 5)
    assert.equal(current().value_raw, '2–5')
    await page.reload(); await page.getByRole('button', { name: '全部展开', exact: true }).click()
    assert.equal(await card.getByLabel('下界', { exact: true }).inputValue(), '2')
    assert.equal(await card.getByLabel('上界', { exact: true }).inputValue(), '5')
    assert.equal(await card.getByText('原始记录', { exact: true }).count(), 0)
    if (mode === 'upload') {
      readOnly = true
      await page.reload(); await card.getByLabel('下界', { exact: true }).waitFor()
      assert.equal(await card.getByLabel('下界', { exact: true }).isDisabled(), true)
      assert.equal(await card.getByLabel('原始值', { exact: true }).count(), 0)
    }
    assert.deepEqual(errors, [])
    console.log(JSON.stringify({ mode, saves, layoutAndSave: 'passed', pageErrors: errors.length }))
    await context.close()
  }
  if (process.env.TC_BROWSER_PAYLOADS) await writeFile(process.env.TC_BROWSER_PAYLOADS, JSON.stringify(payloads))
} finally { await browser.close() }
