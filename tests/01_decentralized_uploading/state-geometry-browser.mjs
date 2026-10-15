// 真实 React 路由/浏览器事件；API 使用隔离夹具，保存请求另交 SQLite 校验。
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
const output = process.env.PROPERTY_BROWSER_OUTPUT || '/tmp/scwiki94-browser'
await mkdir(output, { recursive: true })
const payloads = [], results = []
const taskId = '9'.repeat(32), itemKey = 'a'.repeat(64)
const custom = (code, key, name) => ({ record_key: key, module_code: code, record_type: 'property', property_code: 'custom', custom_property_key: key, definition_key: `record.${code}.custom`, definition_version: 1, name_raw: name, value_kind: 'number', value_raw: '2', value_number: 2, unit_raw: 'eV', payload: {} })
const tc = () => ({ record_key: 'tc', module_code: 'superconductive_properties', record_type: 'predicted_tc', property_code: 'tc', definition_key: 'record.superconductive_properties.predicted_tc.allen_dynes', definition_version: 1, method_code: 'allen_dynes', name_raw: 'critical temperature', value_kind: 'range', value_raw: '281–311', value_min: 281, value_max: 311, canonical_unit: 'K', unit_raw: 'K', payload: { calculation_conditions: { calculation_code: 'QE', k_grid: '12 x 12 x 12' }, parameters: { lambda_ep: 2.1, omega_log: 1200, extensions: [{ key: 'mu_star', value_kind: 'range', value_min: 0.1, value_max: 0.13, unit_raw: '1' }] } } })
try {
  for (const mode of ['upload', 'admin', 'readonly']) {
    const context = await browser.newContext({ viewport: { width: 1500, height: 1100 }, acceptDownloads: true })
    const user = { id: 7, username: 'fixture', role: 'admin', is_admin: true, is_approved: true, is_email_verified: true, account_status: 'active' }
    await context.addInitScript(({ user, taskId }) => { localStorage.setItem('auth_token', 'isolated-fixture'); localStorage.setItem('auth_user', JSON.stringify(user)); localStorage.setItem('sc-wiki.language', 'zh'); localStorage.setItem('scwiki_active_upload_task:7', taskId) }, { user, taskId })
    let states = [{ state_key: 'sample', material: 'LaSc2H24', material_name: '', element_count: 3, state_kind: 'theoretical', structure_optimization: 'sscha', reported_space_group_symbol: 'P6/mmm', reported_space_group_number: 191, pressure_value_gpa: 150, material_dimensionality: 'three_dimensional', crystal_system: 'hexagonal', structures: [], structure_families: [], property_modules: [
      ...[['electronic_properties', 'el', 'band gap'], ['dynamical_properties', 'dyn', 'phonon frequency']].map(([code, key, name]) => ({ module_key: key, module_code: code, definition_key: `module.${code}`, definition_version: 1, records: [custom(code, key, name)] })),
      { module_key: 'thermo', module_code: 'thermodynamical_properties', definition_key: 'module.thermodynamical_properties', definition_version: 1, records: [] },
      { module_key: 'sc', module_code: 'superconductive_properties', definition_key: 'module.superconductive_properties', definition_version: 1, records: [tc()] },
    ] }]
    let detail = { id: 990094, title: '四类物性统一表单隔离验收', year: 2026, authors: [], journal: 'Test', paper_type: 'theoretical', superconductor_kind: 'conventional', review_status: 'pending', material_families: [{ id: 8, name: '氢化物', status: 'confirmed' }], key_properties: [] }
    let version = 1, saves = 0, failSave = false, manualWrites = 0, reviewWrites = 0
    let manual = { changed: true, status: 'draft', reason: '', no_evidence_reason: '', items: [] }
    const evidence = () => ({ key: 'pressure', item_key: itemKey, state_key: 'sample', field: 'material_states[0].pressure_value_gpa', fields: ['material_states[0].pressure_value_gpa'], label: '压强', current_value: states[0].pressure_value_gpa, status: 'supported', reason: '旧原文核对', evidences: [], stale: version > 1 })
    const spectra = () => ({ version: `s${version}`, jobs: [], can_edit: mode !== 'readonly', can_review: false, items: [{ id: 'collection', version: 2, state_key: 'sample', stale: false, source: { source_name: 'fixture.pdf', pdf_page: 3 }, run: { id: 'run1', status: 'succeeded' }, review: {}, result: { curves: ['phonon_dos', 'alpha2f'].map((kind, index) => ({ id: index ? 'a2f' : 'dos', kind, unit: '1', projection: null, points: [{ frequency_thz: 1, observed_amplitude: 2, reconstructed_amplitude: 2, status: 'observed' }, { frequency_thz: 2, observed_amplitude: null, reconstructed_amplitude: 3, status: 'interpolated' }] })), quality: {}, candidates: {} } }] })
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/admin/papers/990094') { if (req.method() === 'PUT') detail = { ...detail, ...req.postDataJSON() }; return json({ ...detail, material_states: states }) }
      if (path === '/api/papers/990094') return json({ ...detail, material_states: states })
      if (path === '/api/form-definitions') return json(definitions)
      if (path.startsWith('/api/form-definitions/')) return json(definitions.find(item => path.includes(item.definition_key)))
      if (path === '/api/classification-catalogs') return json({ material_families: [{ id: 8, name: '氢化物' }], structure_families: [], material_dimensionalities: [] })
      if (path === '/api/rag/space-groups') return json({ space_groups: [] })
      if (path.endsWith('/preflight')) return json({ version: `v${version}`, records: [evidence()], needs_check: false })
      if (path.includes('/manual/')) {
        if (req.method() === 'PUT') { manualWrites++; const body = req.postDataJSON(); assert.equal(body.expected_version, `v${version}`); manual = { ...manual, reason: body.reason, no_evidence_reason: body.no_evidence_reason } }
        if (req.method() === 'POST') { manualWrites++; manual = { ...manual, items: [{ id: 'file', kind: 'text_file', filename: 'evidence.txt', source_description: 'evidence.txt' }] } }
        return json({ ok: true, data: manual })
      }
      if (path.endsWith('/scientific-draft') || path.endsWith('/draft')) {
        if (req.method() === 'GET') return json({ data: { paper: detail, material_states: states, structure_candidates: [] } })
        if (failSave) return json({ detail: '隔离保存失败' }, 500)
        const body = req.postDataJSON(); assert.equal(body.material_states[0].structure_optimization, 'sscha'); states = body.material_states; saves++; version++; payloads.push(body)
        return json({ ok: true, data: { revision_bumped: false } })
      }
      if (path === '/api/rag/spectra') return json(spectra())
      if (path.endsWith('/image')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aVn0AAAAASUVORK5CYII=', 'base64') })
      if (path.endsWith('/export')) return json(spectra().items[0])
      if (path === `/api/upload-tasks/${taskId}`) return json({ data: { task_id: taskId, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
      if (path === '/api/upload-tasks') return json({ data: [] })
      if (path.endsWith('/parsing')) return json({ data: { status: 'ready', stage: 'ready', files: [], chunks: [], summary: { status: 'ready', completed: 1, total: 1 }, next_poll_ms: null, partial_draft: { paper: detail, material_states: states } } })
      if (req.method() !== 'GET') { reviewWrites++; throw new Error(`不得发起额外写入: ${path}`) }
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    const expandModules = async (keyboard = false) => {
      const sections = page.locator('[data-property-module-section]')
      assert.equal(await sections.count(), 4)
      assert.equal(await page.getByLabel('上移模块', { exact: true }).count(), 0)
      assert.equal(await page.getByLabel('下移模块', { exact: true }).count(), 0)
      assert.deepEqual(await sections.evaluateAll(nodes => nodes.map(node => node.open)), [false, false, false, false], '四类模块初次挂载默认折叠')
      const first = sections.first().locator(':scope > summary')
      if (keyboard) {
        await first.focus(); await first.press('Enter')
        assert.deepEqual(await sections.evaluateAll(nodes => nodes.map(node => node.open)), [true, false, false, false], '键盘只展开当前模块')
        await first.press('Space')
        assert.equal(await sections.first().evaluate(node => node.open), false)
      }
      if (mode === 'admin' && keyboard) await page.locator('[data-state-key="sample"]').screenshot({ path: `${output}/property-modules-collapsed.png` })
      for (const section of await sections.all()) await section.locator(':scope > summary').click()
    }
    const start = mode === 'upload' ? '/upload' : mode === 'admin' ? '/admin/papers/990094/edit' : '/papers/990094'
    await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}${start}`)
    if (mode !== 'readonly') await page.getByRole('button', { name: '全部展开', exact: true }).click()
    await page.getByTestId('property-record-tc').waitFor({ state: 'attached' })
    const basics = page.locator('[data-material-basics]').first()
    assert.equal(await basics.locator('[data-material-identity-row] > *').count(), 7)
    if (mode !== 'readonly') {
      const identityTops = await basics.locator('[data-material-identity-row] > *').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().top))
      assert(Math.max(...identityTops) - Math.min(...identityTops) < 2, '首行七字段同排')
      const select = async (label, option) => { await basics.getByLabel(label, { exact: true }).click(); await page.getByRole('option', { name: option, exact: true }).click() }
      await select('结构优化核处理', '量子非谐优化（SSCHA）')
      await select('材料状态类型', '实验')
      assert.equal(await basics.getByLabel('结构优化核处理', { exact: true }).count(), 0)
      await basics.getByLabel('材料状态类型', { exact: true }).click()
      assert.equal(await page.getByRole('option', { name: '理论与实验', exact: true }).count(), 0)
      await page.getByRole('option', { name: '理论', exact: true }).click()
      assert.equal(await basics.getByLabel('结构优化核处理', { exact: true }).innerText(), '未说明')
      await select('结构优化核处理', '量子非谐优化（SSCHA）')
      const family = basics.getByLabel('结构家族', { exact: true })
      const height = () => family.evaluate(node => node.closest('.MuiInputBase-root').getBoundingClientRect().height)
      const emptyHeight = await height()
      for (let n = 0; n < 17; n++) { await family.fill(`Family-${n}-with-a-long-name`); await family.press('Enter') }
      assert.equal(await height(), emptyHeight, '17 个长标签不能增高')
      assert(await basics.locator('[data-family-tags]').evaluate(n => n.scrollWidth > n.clientWidth), '仅标签轨道横向溢出')
      assert.equal(await basics.locator('.MuiChip-root').count(), 17)
      await family.press('Backspace')
      assert.equal(await basics.locator('.MuiChip-root').count(), 16)
      assert.equal(await height(), emptyHeight)
      await page.setViewportSize({ width: 736, height: 1100 })
      assert.equal(await height(), emptyHeight)
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), '窄屏不撑宽页面')
      await page.setViewportSize({ width: 1500, height: 1100 })
      await basics.screenshot({ path: `${output}/${mode}-material-basics.png` })
      await basics.getByRole('button', { name: 'Clear', exact: true }).click()
      assert.equal(await basics.locator('.MuiChip-root').count(), 0)
      assert.equal(await height(), emptyHeight)
      results.push({ mode, familyHeight: emptyHeight, longTags: 17, threeRows: 'passed' })
    }
    if (mode !== 'readonly') {
      await page.getByLabel('压强 (GPa)', { exact: true }).fill('180')
      await page.getByRole('button', { name: '压强 (GPa)', exact: true }).click()
      const drawer = page.getByRole('dialog')
      await drawer.getByLabel('人工修改判断理由（必填）').fill('对照论文确认结构优化方法与压强')
      await drawer.getByLabel('提供证据', { exact: true }).check()
      await drawer.locator('input[type=file]').setInputFiles({ name: 'evidence.txt', mimeType: 'text/plain', buffer: Buffer.from('Structure optimization is SSCHA.') })
      await drawer.getByRole('button', { name: '保存并完成', exact: true }).click()
      await drawer.waitFor({ state: 'detached' })
      assert.equal(states[0].structure_optimization, 'sscha')
      assert(saves > 0)
      await page.reload()
      await page.getByRole('button', { name: '全部展开', exact: true }).click()
      assert.equal(await page.getByLabel('结构优化核处理', { exact: true }).innerText(), '量子非谐优化（SSCHA）')
    } else {
      assert.equal(await basics.getByText('量子非谐优化（SSCHA）', { exact: true }).count(), 1)
      await basics.screenshot({ path: `${output}/readonly-material-basics.png` })
    }
    assert.equal(reviewWrites, 0)
    assert.deepEqual(errors, [])
    results.push({ mode, saves, pageErrors: errors.length, result: 'passed' })
    console.log(JSON.stringify(results.at(-1)))
    await context.close()
  }
  await writeFile(`${output}/results.json`, JSON.stringify(results, null, 2))
  await writeFile(`${output}/saved-payloads.json`, JSON.stringify(payloads, null, 2))
} finally { await browser.close() }
