// 真实共享组件与审核路由；接口全部隔离，不读写真实论文或调用 AI。
import assert from 'node:assert/strict'
import { readFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5191'
const artifacts = process.env.ARTIFACT_DIR || '/tmp/scwiki-structure-compact'
await mkdir(artifacts, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const cif = (count, length = 12) => `data_Sn
_cell_length_a ${length}
_cell_length_b 12
_cell_length_c 12
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
${Array.from({ length: count }, (_, i) => `Sn${i + 1} Sn ${(i % 4) / 4} ${(Math.floor(i / 4) % 4) / 4} ${Math.floor(i / 16) / 4}`).join('\n')}
`
const candidates = [1, 64].map((count, i) => ({ candidate_id: `structure_${i + 1}`, material_state_ref: 'material_states[0]', status: 'confirmed', confirmation: 'confirmed', validation: { structure_hash: `hash-${i + 1}`, atom_count: count, elements: ['Sn'] }, sources: [{ filename: `Sn-${count}.cif` }], representations: { conventional: { cif: { text: cif(count) } }, primitive: { cif: { text: cif(count, 11) } } } }))
const states = [{ state_key: 'sn', material_name: 'Sn', material: 'Sn', state_kind: 'experimental', material_dimensionality: 'three_dimensional', crystal_system: 'unknown', structure_families: [], property_modules: [], structures: candidates.map((c, i) => ({ id: i + 1, structure_text: cif(i ? 64 : 1), structure_format: 'cif', source_locator: c.sources[0].filename })) }]
const paper = { id: 990103, title: '结构附件隔离验收示例', year: 2026, authors: [], paper_type: 'experimental', superconductor_kind: 'conventional', review_status: 'pending', material_families: [], material_relations: [] }
const records = candidates.map((c, i) => ({ key: `structure-${i + 1}`, item_key: `structure-${i + 1}`, state_key: 'sn', field: `material_states[0].structures[${i}]`, structure_hash: c.validation.structure_hash, label: '晶体结构与晶格参数', status: 'uncertain', current_value: '示例结构', reason: '示例来源待确认', evidences: [] }))
try {
  for (const mode of ['upload', 'admin']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    const user = { id: 7, username: 'fixture', role: 'admin', is_admin: true, is_approved: true, is_email_verified: true }
    await context.addInitScript(user => {
      localStorage.setItem('sc-wiki.language', 'zh')
      localStorage.setItem('auth_token', 'fixture-only')
      localStorage.setItem('auth_user', JSON.stringify(user))
    }, user)
    const writes = []
    await context.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname
      if (!['GET', 'HEAD'].includes(request.method())) writes.push(path)
      const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/form-definitions') return json(definitions)
      if (path === '/api/classification-catalogs') return json({ material_families: [], structure_families: [], material_dimensionalities: [] })
      if (path.endsWith('/space-groups')) return json({ space_groups: [] })
      if (path.endsWith('/preflight')) return json({ version: 'v1', needs_check: true, records })
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path.endsWith('/representations')) return json({ data: candidates[Number(path.split('/').at(-2)) - 1] })
      if (path === '/api/admin/papers/990103') return json({ ...paper, material_states: states })
      if (path.endsWith('/draft')) return json({ ok: true, data: { paper, material_states: states, structure_candidates: candidates } })
      assert(!path.endsWith('/jobs') && !path.endsWith('/review'), '禁止请求 AI 或正式审核')
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${base}/${mode === 'admin' ? 'admin/papers/990103/edit' : 'login'}`)
    if (mode === 'upload') await page.evaluate(async draft => {
      const { default: React } = await import('/node_modules/.vite/deps/react.js')
      const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
      const { LanguageProvider } = await import('/src/context/LanguageContext.tsx')
      const { default: UploadTaskEditor } = await import('/src/components/UploadTaskEditor.tsx')
      document.getElementById('root').style.display = 'none'
      const host = document.createElement('main'); host.style.cssText = 'max-width:1200px;margin:auto;padding:16px;box-sizing:border-box'; document.body.append(host)
      ReactDOM.createRoot(host).render(React.createElement(LanguageProvider, {}, React.createElement(UploadTaskEditor, { taskId: 'a'.repeat(32), draftOverride: draft, onSubmitted() {} })))
    }, { paper, material_states: states, structure_candidates: candidates })
    const attachment = page.locator('[data-structure-attachment]').first()
    const panel = attachment.locator('[data-scientific-structure]')
    const layout = panel.locator('[data-crystal-layout]')
    const toggle = attachment.locator('button[aria-expanded]')
    const canvas = layout.locator('canvas').first()
    await layout.getByRole('table', { name: '原子位置（64）', exact: true }).waitFor()
    await canvas.scrollIntoViewIfNeeded()
    await page.waitForTimeout(500)
    const writesBefore = writes.length
    const dimensions = () => layout.evaluate(el => {
      const rect = selector => { const box = el.querySelector(selector).getBoundingClientRect(); return { width: box.width, height: box.height, bottom: box.bottom } }
      return { model: rect('[data-crystal-model]'), data: rect('[data-crystal-data]'), canvas: rect('canvas') }
    })
    const large = await dimensions()
    assert.equal(large.model.height, 400); assert.equal(large.data.height, 400)
    assert.equal(large.canvas.height, 400)
    assert(Math.abs(large.model.width - large.data.width) < 1)
    assert(Math.abs(large.model.bottom - large.data.bottom) < 1)
    assert.equal(await layout.locator('[data-structure-legend]').count(), 0)
    assert(await layout.locator('[data-crystal-data]').evaluate(el => el.scrollHeight > el.clientHeight))
    const pixels = await canvas.evaluate(el => {
      const copy = document.createElement('canvas'); copy.width = el.width; copy.height = el.height
      const ctx = copy.getContext('2d'); ctx.drawImage(el, 0, 0)
      const { data } = ctx.getImageData(0, 0, copy.width, copy.height)
      let colored = 0
      for (let i = 0; i < data.length; i += 4) if (data[i + 3] && Math.max(data[i], data[i + 1], data[i + 2]) - Math.min(data[i], data[i + 1], data[i + 2]) > 25) colored++
      return colored
    })
    assert(pixels > 100, `模型非空像素 ${pixels}`)
    const imageBefore = await canvas.screenshot()
    await layout.getByRole('button', { name: '旋转结构', exact: true }).click()
    assert(!imageBefore.equals(await canvas.screenshot()), '旋转应改变画布')
    await layout.getByRole('button', { name: '放大结构', exact: true }).click()
    // 工具条失焦后再比较，排除按钮焦点样式。
    await toggle.focus()
    await page.waitForTimeout(300)
    const rotated = await canvas.evaluate(el => ({ view: el._3dmol_viewer.getView(), image: el.toDataURL() }))
    const canvasHandle = await canvas.elementHandle()
    await toggle.press('Enter')
    assert.equal(await toggle.getAttribute('aria-expanded'), 'false')
    assert.equal(await canvas.isVisible(), false)
    assert.equal(await canvasHandle.evaluate(el => el.isConnected), true)
    assert((await attachment.boundingBox()).height < 170, '收起后必须紧凑')
    const source = panel.getByRole('button', { name: 'Sn-64.cif', exact: true })
    await source.waitFor()
    await source.click()
    await page.getByRole('dialog').waitFor()
    await page.keyboard.press('Escape')
    await page.getByRole('dialog').waitFor({ state: 'detached' })
    await page.waitForTimeout(400)
    assert(await source.evaluate(el => el === document.activeElement), '关闭核对应返回原文件入口')
    await toggle.focus(); await toggle.press('Space')
    await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(300)
    const reopened = await canvas.evaluate(el => ({ view: el._3dmol_viewer.getView(), image: el.toDataURL() }))
    assert.deepEqual(reopened.view, rotated.view, '重开应保留缩放与视角')
    assert.equal(reopened.image, rotated.image, '重开后的模型像素应保持不变')
    await panel.getByRole('combobox').first().click()
    await page.getByRole('option', { name: 'Sn-1.cif', exact: true }).click()
    await layout.getByRole('table', { name: '原子位置（1）', exact: true }).waitFor()
    const small = await dimensions()
    assert.equal(small.model.width, large.model.width); assert.equal(small.model.height, large.model.height)
    assert.equal(small.data.width, large.data.width); assert.equal(small.data.height, large.data.height)
    await panel.getByRole('combobox', { name: '晶胞表示' }).click()
    await page.getByRole('option', { name: '原胞', exact: true }).click()
    await layout.getByRole('table', { name: '晶格矩阵', exact: true }).getByText('11.0000', { exact: true }).waitFor()
    await layout.getByRole('button', { name: '直角坐标 (Å)' }).click()
    await toggle.click(); await toggle.click()
    assert.equal(await panel.getAttribute('data-structure-id'), 'structure_1')
    assert.equal(await layout.getByRole('button', { name: '直角坐标 (Å)' }).getAttribute('aria-pressed'), 'true')
    assert((await panel.getByRole('combobox', { name: '晶胞表示' }).innerText()).includes('原胞'))
    await attachment.screenshot({ path: `${artifacts}/${mode}-desktop.png` })
    await toggle.click()
    await attachment.screenshot({ path: `${artifacts}/${mode}-collapsed.png` })
    await toggle.click()
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 })
      await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(300)
      const mobile = await dimensions()
      assert.equal(mobile.model.height, 280); assert.equal(mobile.data.height, 400)
      assert.equal(mobile.canvas.height, 280)
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), '页面横向溢出')
      await attachment.screenshot({ path: `${artifacts}/${mode}-mobile-${width}.png` })
      await toggle.focus(); await toggle.press('Enter'); await toggle.press('Space')
      assert.equal(await toggle.getAttribute('aria-expanded'), 'true')
    }
    await page.waitForTimeout(1500)
    assert.equal(writes.length, writesBefore, '折叠及查看操作不应保存或使核对失效')
    assert.deepEqual(errors, [])
    console.log(JSON.stringify({ mode, large, small, pixels, writes: writes.length, errors }))
    await context.close()
  }
} finally { await browser.close() }
