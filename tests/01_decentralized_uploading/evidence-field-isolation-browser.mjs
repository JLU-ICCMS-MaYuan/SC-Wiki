// 真实页面组件 + 真实后端快照/派生逻辑与 MySQL 回滚存储；HTTP 适配和权限用户为隔离夹具。
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5198'
const artifacts = process.env.ARTIFACT_DIR || '/tmp/scwiki-evidence-isolation'
await mkdir(artifacts, { recursive: true })
const storage = spawn(process.env.PYTHON_BIN || 'python3', [new URL('./evidence-isolation-storage.py', import.meta.url).pathname], {
  stdio: ['pipe', 'pipe', 'inherit'], env: process.env,
})
const waiting = []
createInterface({ input: storage.stdout }).on('line', line => waiting.shift()?.resolve(JSON.parse(line)))
storage.on('exit', code => { for (const pending of waiting.splice(0)) pending.reject(new Error(`MySQL 存储桥退出：${code}`)) })
const call = command => new Promise((resolve, reject) => { waiting.push({ resolve, reject }); storage.stdin.write(JSON.stringify(command) + '\n') })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true })
const reports = []
try {
  for (const role of (process.env.SC_WIKI_BROWSER_ROLES || 'upload,revision,admin,superadmin').split(',')) {
    const draft = { paper: { id: 990109, title: 'US11 隔离验收', year: 2026, authors: [], paper_type: 'theoretical',
      journal: 'Fixture', review_status: 'pending', superconductor_kind: 'conventional', material_families: [{ id: 8, name: '氢基超导体' }] },
      material_states: [{ id: 1, state_key: 'isolation', material: 'LaSc2H24', material_name: 'Fixture hydride', element_count: 3,
        state_kind: 'theoretical', structure_optimization: 'classical_static', material_dimensionality: 'three_dimensional',
        reported_space_group_symbol: 'P6/mmm', reported_space_group_number: 191, crystal_system: 'hexagonal',
        pressure_value_gpa: 150, structure_families: [], property_modules: [], structures: [] }], structure_candidates: [] }
    if (process.env.SC_WIKI_PROPERTY_FIXTURE) draft.material_states[0].property_modules = JSON.parse(await readFile(process.env.SC_WIKI_PROPERTY_FIXTURE, 'utf8'))
    let stored = await call({ op: 'init', draft }), saves = 0, revisionVersion = 1, failNextSave = true
    const user = { id: 7, username: 'fixture', role: role === 'superadmin' ? 'superadmin' : role === 'admin' ? 'admin' : 'user',
      is_admin: ['admin', 'superadmin'].includes(role), is_superadmin: role === 'superadmin', is_approved: true, is_email_verified: true }
    const context = await browser.newContext({ viewport: { width: role === 'revision' ? 390 : 1440, height: 1000 } })
    await context.addInitScript(user => {
      localStorage.setItem('sc-wiki.language', 'zh'); localStorage.setItem('auth_token', 'fixture-only')
      localStorage.setItem('auth_user', JSON.stringify(user))
    }, user)
    await context.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname
      const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/form-definitions') return json(definitions)
      if (path === '/api/classification-catalogs') return json({ material_families: [{ id: 8, name: '氢基超导体' }], structure_families: [], material_dimensionalities: [] })
      if (path.endsWith('/space-groups')) return json({ space_groups: [{ number: 191, symbol: 'P6/mmm' }] })
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path.endsWith('/preflight')) { stored = await call({ op: 'read' }); return json(stored.preflight) }
      if (path.includes('/manual/')) return json({ ok: true, data: { changed: false, reason: '', items: [], history: [] } })
      if (path === '/api/admin/papers/990109') {
        if (request.method() === 'PUT') stored = await call({ op: 'save', draft: { ...stored.draft, paper: { ...stored.draft.paper, ...request.postDataJSON() } } })
        return json({ ...stored.draft.paper, material_states: stored.draft.material_states })
      }
      if (path.endsWith('/scientific-draft')) {
        if (failNextSave) { failNextSave = false; return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '隔离夹具首次保存失败' }) }) }
        stored = await call({ op: 'save', draft: { ...stored.draft, material_states: request.postDataJSON().material_states } }); saves++
        return json({ ok: true, data: { revision_bumped: false } })
      }
      if (path.endsWith('/revision-draft') || path.endsWith('/draft')) {
        if (request.method() === 'PUT') {
          if (failNextSave) { failNextSave = false; return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '隔离夹具首次保存失败' }) }) }
          const body = request.postDataJSON()
          stored = await call({ op: 'save', draft: body.draft || body }); saves++; revisionVersion++
        }
        return json({ ok: true, data: stored.draft, revision_id: 'fixture-revision', draft_version: revisionVersion })
      }
      if (path.endsWith('/jobs') && path.startsWith('/api/rag/evidence')) {
        // 空可选项触发自动扫描时仅返回已有快照，不运行模型。
        return json({ id: 'fixture-existing', status: 'completed' })
      }
      if (path.endsWith('/jobs/fixture-existing')) return json({ id: 'fixture-existing', status: 'completed', ...stored.preflight })
      assert(!path.endsWith('/review') && !path.endsWith('/submit'), `禁止真实提交/批准：${path}`)
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    if (role === 'admin' || role === 'superadmin') await page.goto(`${base}/admin/papers/990109/edit`)
    else {
      await page.goto(`${base}/login`)
      await page.evaluate(async role => {
        const { default: React } = await import('/node_modules/.vite/deps/react.js')
        const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
        const { LanguageProvider } = await import('/src/context/LanguageContext.tsx')
        const { default: Editor } = await import('/src/components/UploadTaskEditor.tsx')
        document.getElementById('root').hidden = true
        const host = document.createElement('main'); document.body.append(host)
        ReactDOM.createRoot(host).render(React.createElement(LanguageProvider, {}, React.createElement(Editor,
          { taskId: 'a'.repeat(32), ...(role === 'revision' ? { revisionPaperId: 990109 } : {}), onSubmitted() {} })))
      }, role)
    }
    await page.getByLabel('结构优化核处理', { exact: true }).waitFor()
    if (process.env.SC_WIKI_PROPERTY_FIXTURE) {
      for (const code of ['superconductive_properties', 'electronic_properties']) {
        const details = page.getByTestId('property-module-' + code).locator('details').first()
        if (await details.count() && !(await details.evaluate(el => el.open))) await details.locator(':scope > summary').click()
      }
    }
    const fields = ['element_count', 'reported_space_group_number', 'crystal_system', ...stored.preflight.records.filter(r => r.record_key && r.required !== false).map(r => r.field.replace('material_states[0].', ''))]
    const inspect = async stage => {
      const values = await page.evaluate(fields => fields.map(field => {
        const anchor = document.querySelector(`[data-issue-field="material_states[0].${field}"]`)
        const label = anchor?.querySelector('label')
        return { field, present: Boolean(anchor), red: Boolean(anchor?.querySelector('[data-evidence-problem="true"]') || anchor?.matches('[data-evidence-problem="true"]')),
          labelRed: label?.getAttribute('data-evidence-caption-problem') === 'true' }
      }), fields)
      if (process.env.SC_WIKI_PROPERTY_FIXTURE) {
        const properties = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="property-module-"] [data-evidence-key]')).map(caption => ({
          label: caption.textContent, red: caption.getAttribute('data-evidence-caption-problem') === 'true',
        })))
        assert(properties.length >= 8, `必须实际检查已渲染的物性字段：${JSON.stringify(properties)}`)
        assert(properties.every(item => !item.red), `${role}/${stage}: 物性字段被连带标红 ${JSON.stringify(properties)}`)
        values.push(...properties.map(item => ({field: item.label, present: true, red: item.red, labelRed: item.red})))
      }
      assert(values.every(value => !value.red && !value.labelRed), `${role}/${stage}: ${JSON.stringify(values)}`)
      const counter = await page.locator('[data-material-state-index="0"] .MuiChip-colorError').allTextContents()
      assert.deepEqual(counter, stage === 'initial' ? [] : ['1'], `${role}/${stage}: 仅真实修改的核处理计入问题`)
      reports.push({ role, stage, values, counter, saves })
    }
    await page.waitForTimeout(300)
    await inspect('initial')
    await page.getByLabel('结构优化核处理', { exact: true }).click()
    await page.getByRole('option', { name: '量子非谐优化（SSCHA）' }).click()
    await page.waitForTimeout(50); await inspect('edit')
    await page.waitForTimeout(1000); await inspect('waiting')
    if (role === 'admin' || role === 'superadmin') await page.getByRole('button', { name: '保存修改', exact: true }).click()
    else await page.waitForTimeout(4800)
    await page.waitForTimeout(400)
    assert.equal(saves, 0, `${role}: 首次保存应由夹具拒绝`)
    await inspect('save-failed')
    assert.equal(stored.draft.material_states[0].structure_optimization, 'classical_static')
    await page.getByRole('button', { name: role === 'admin' || role === 'superadmin' ? '保存修改' : '立即保存', exact: true }).click()
    await page.waitForTimeout(500)
    assert(saves > 0, `${role}: 必须发生保存并从 MySQL 读取`)
    assert.equal(stored.draft.material_states[0].structure_optimization, 'sscha')
    await inspect('saved')
    await page.locator('[data-issue-field="material_states[0].element_count"] label').click()
    try {
    await page.locator('.evidence-review-drawer').getByText('隔离夹具核验', { exact: false }).first().waitFor()
    } catch (error) { await writeFile(`${artifacts}/debug-preflight.json`, JSON.stringify(stored.preflight, null, 2)); await page.screenshot({path:`${artifacts}/debug.png`,fullPage:true}); throw error }
    assert.equal(stored.preflight.records.find(r => r.field.endsWith('.element_count')).decision.reason, '保留的人工说明')
    await page.getByLabel('关闭来源详情').click()
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${artifacts}/${role}.png`, fullPage: true })
    assert.deepEqual(errors, [])
    await context.close()
  }
  await writeFile(`${artifacts}/results.json`, JSON.stringify(reports, null, 2))
  console.log(JSON.stringify({ passed: reports.length, roles: 4, mysql: 'savepoint sessions; outer rollback', artifacts }))
} finally {
  await browser.close()
  storage.stdin.end(JSON.stringify({ op: 'close' }) + '\n')
}
