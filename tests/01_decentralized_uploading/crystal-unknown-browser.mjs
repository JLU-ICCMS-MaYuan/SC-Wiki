// Issue #105：真实两入口与 Chromium 事件，全部 API 使用隔离夹具，禁止业务数据写入。
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
const taskId = '5'.repeat(32)
const groupFields = ['reported_space_group_symbol', 'reported_space_group_number']
try {
  for (const mode of ['admin', 'superadmin', 'upload']) {
    const user = { id: 7, username: 'fixture', role: mode === 'upload' ? 'user' : mode, is_admin: mode !== 'upload',
      is_approved: true, is_email_verified: true, account_status: 'active' }
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    await context.addInitScript(({ user, taskId }) => {
      localStorage.setItem('auth_token', 'fixture-only')
      localStorage.setItem('auth_user', JSON.stringify(user))
      localStorage.setItem('sc-wiki.language', 'zh')
      localStorage.setItem('scwiki_active_upload_task:7', taskId)
    }, { user, taskId })
    let states = [0, 1].map(i => ({ state_key: `fixture-105-${i}`, material: 'Sn', material_name: `样品 ${i + 1}`,
      element_count: 1, state_kind: 'experimental', material_dimensionality: 'three_dimensional',
      crystal_system: i ? 'cubic' : 'unknown', reported_space_group_symbol: 'Fm-3m', reported_space_group_number: 225,
      property_modules: [], structures: [], structure_families: [],
    }))
    let detail = { id: 990105, title: '隔离晶系联动验收', year: 2026, authors: [], paper_type: 'experimental',
      journal: 'Test', superconductor_kind: 'conventional', review_status: 'pending', key_properties: [],
      material_families: [{ id: 8, name: '单质超导体', status: 'confirmed' }] }
    let failSave = true, saves = 0
    const payloads = [], errors = [], forbidden = []
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/admin/papers/990105') {
        if (req.method() === 'PUT') detail = { ...detail, ...req.postDataJSON() }
        return json({ ...detail, material_states: states })
      }
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path === '/api/classification-catalogs') return json({ material_families: [{ id: 8, name: '单质超导体' }], structure_families: [], material_dimensionalities: [] })
      if (path === '/api/rag/space-groups') return json({ space_groups: [{ number: 225, symbol: 'Fm-3m' }, { number: 139, symbol: 'I4/mmm' }] })
      if (path === '/api/rag/llm/current') return json({})
      if (path.endsWith('/preflight')) return json({ version: `fixture-${saves}`, records: [], needs_check: true })
      if (path.endsWith('/scientific-draft') || path.endsWith('/draft')) {
        if (req.method() === 'GET') return json({ data: { paper: detail, material_states: states, structure_candidates: [] } })
        payloads.push(req.postDataJSON())
        if (failSave) return json({ detail: '隔离保存失败' }, 500)
        states = req.postDataJSON().material_states
        saves++
        return json({ ok: true, data: mode === 'upload' ? req.postDataJSON() : { revision_bumped: false } })
      }
      if (path === `/api/upload-tasks/${taskId}`) return json({ data: { task_id: taskId, filename: 'fixture.pdf', processing_status: 'succeeded', stage: 'ready', stage_index: 5, stage_total: 5 } })
      if (path === '/api/upload-tasks') return json({ data: [] })
      if (path.endsWith('/parsing')) return json({ data: { status: 'ready', stage: 'ready', files: [], chunks: [],
        summary: { status: 'ready', completed: 1, total: 1 }, next_poll_ms: null, partial_draft: { paper: detail, material_states: states } } })
      if (path.endsWith('/jobs') || path.endsWith('/review') || path.endsWith('/proposals')) forbidden.push(path)
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}${mode === 'upload' ? '/upload' : '/admin/papers/990105/edit'}`)
    await page.getByRole('button', { name: '全部展开', exact: true }).click()
    const crystal = page.getByRole('combobox', { name: '晶系', exact: true }).first()
    const symbol = page.getByRole('combobox', { name: '空间群符号', exact: true }).first()
    const number = page.getByLabel('空间群号', { exact: true }).first()
    const save = page.getByRole('button', { name: mode === 'upload' ? '立即保存' : '保存修改', exact: true })
    const assertEmpty = async () => {
      assert.equal(await crystal.innerText(), '未知')
      assert.equal(await symbol.inputValue(), '')
      assert.equal(await number.inputValue(), '')
      assert.equal(await page.getByLabel('空间群号', { exact: true }).nth(1).inputValue(), '225')
    }
    // 载入时不清洗；同值选择必须生效。
    assert.equal(await crystal.innerText(), '未知')
    assert.equal(await symbol.inputValue(), 'Fm-3m')
    await crystal.click()
    await page.getByRole('option', { name: '未知', exact: true }).click()
    await assertEmpty()
    // 先输入一个标准编号，再用键盘选择未知。
    await number.fill('139')
    assert.equal(await crystal.innerText(), '四方')
    assert.equal(await symbol.inputValue(), 'I4/mmm')
    await crystal.focus()
    await crystal.press('ArrowDown')
    await page.getByRole('option', { name: '未知', exact: true }).focus()
    await page.keyboard.press('Enter')
    await assertEmpty()
    // 自由输入刚失焦、晶系仍为未知：键盘重复选择不得复活本地缓存。
    await symbol.fill('stale-symbol')
    await crystal.focus()
    await crystal.press('ArrowDown')
    await page.getByRole('option', { name: '未知', exact: true }).focus()
    await page.keyboard.press('Enter')
    await symbol.click()
    await symbol.press('Tab')
    await assertEmpty()
    const saveResponse = () => page.waitForResponse(r => /\/(scientific-draft|draft)$/.test(new URL(r.url()).pathname) && r.request().method() === 'PUT')
    const [failed] = await Promise.all([saveResponse(), save.click()])
    assert.equal(failed.status(), 500)
    assert.equal(saves, 0)
    await assertEmpty()
    failSave = false
    const [saved] = await Promise.all([saveResponse(), save.click()])
    assert.equal(saved.status(), 200)
    assert(saves > 0)
    for (const body of payloads) {
      assert.equal(body.material_states[0].crystal_system, 'unknown')
      for (const field of groupFields) assert.equal(body.material_states[0][field], null)
      assert.equal(body.material_states[1].reported_space_group_number, 225)
    }
    await page.reload()
    await page.getByRole('button', { name: '全部展开', exact: true }).click()
    await assertEmpty()
    // 清空后仍允许主动选择已知空间群。
    await symbol.fill('I4')
    await page.getByRole('option', { name: 'I4/mmm', exact: true }).click()
    assert.equal(await crystal.innerText(), '四方')
    assert.equal(await number.inputValue(), '139')
    assert.deepEqual(errors, [])
    assert.deepEqual(forbidden, [])
    console.log(JSON.stringify({ mode, repeatSelection: 'passed', keyboard: 'passed', saveRetryReload: 'passed', saves }))
    await context.close()
  }
} finally { await browser.close() }
