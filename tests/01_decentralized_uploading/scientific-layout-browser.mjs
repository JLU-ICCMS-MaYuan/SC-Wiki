// 正式组件的浏览器验收；所有接口均拦截为示例，绝不写真实论文。
import assert from 'node:assert/strict'
import { readFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5191'
const artifacts = process.env.ARTIFACT_DIR || '/tmp/scwiki-scientific-layout'
await mkdir(artifacts, { recursive: true })
const definitions = JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json', import.meta.url), 'utf8'))
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const poscar = (size, element = 'Sn') => `${element}\n1.0\n${size} 0 0\n1 4 0\n0.5 0.25 6\n${element}\n2\nDirect\n0 0 0\n0.25 0.5 0.75\n`
const cif = `data_Sn
_cell_length_a 5
_cell_length_b 5
_cell_length_c 5
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
Sn1 Sn 0 0 0
Sn2 Sn 0.25 0.5 0.75
`
const candidate = (id, size) => ({ candidate_id: `structure_${id}`, material_state_ref: 'material_states[0]', status: 'confirmed', confirmation: 'confirmed', validation: { structure_hash: `hash-${id}`, atom_count: 2, elements: ['Sn'] }, sources: [{ filename: `Sn-${id}.cif` }], representations: { conventional: { cif: { text: cif }, poscar: { text: poscar(size) } }, primitive: { cif: { text: cif.replaceAll('_cell_length_a 5', '_cell_length_a 3') }, poscar: { text: poscar(3) } } } })
let candidates = [candidate(1, 5), candidate(2, 7)]
let states = ['Sn', 'Sn', 'Pb', 'SnHg'].map((material, i) => ({ state_key: `state-${i}`, material_name: material, material, state_kind: i < 3 ? 'experimental' : 'unknown', material_dimensionality: 'three_dimensional', crystal_system: 'unknown', structure_families: [], property_modules: [], structures: i ? [] : candidates.map((c, j) => ({ id: j + 1, structure_text: cif, structure_format: 'cif', source_locator: c.sources[0].filename })) }))
let paper = { id: 990103, title: '隔离布局验收示例', year: 2026, authors: [], journal: 'Fixture', paper_type: 'experimental', superconductor_kind: 'conventional', review_status: 'pending', material_families: [{ id: 8, name: '单质超导体' }], research_materials: ['outdated'], material_relations: JSON.stringify([{ material: 'Sn', relation: '研究样品的结构及输运性质，并比较不同条件下的结果。'.repeat(12), page: 3, quote: 'fixture evidence', evidence: { file_id: 'main' } }]) }
let savedDraft, submits = 0, scientificSaves = 0
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(() => {
  localStorage.setItem('sc-wiki.language', 'zh')
  localStorage.setItem('auth_token', 'fixture-only')
  localStorage.setItem('auth_user', JSON.stringify({ id: 7, username: 'fixture', role: 'admin', is_admin: true, is_approved: true, is_email_verified: true }))
})
await context.route('**/api/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  if (path === '/api/auth/me') return json({ user: { id: 7, username: 'fixture', role: 'admin', is_admin: true, is_approved: true, is_email_verified: true } })
  if (path === '/api/form-definitions') return json(definitions)
  if (path === '/api/classification-catalogs') return json({ material_families: [{ id: 8, name: '单质超导体' }], structure_families: [], material_dimensionalities: [] })
  if (path.endsWith('/space-groups')) return json({ space_groups: [] })
  if (path.endsWith('/preflight')) return json({ version: 'v1', records: [], needs_check: false })
  if (path.endsWith('/review-artifact')) return json({ data: {} })
  if (path.endsWith('/representations')) { const id = Number(path.split('/').at(-2)); return json({ data: candidates.find(c => c.candidate_id === `structure_${id}`) }) }
  if (path === '/api/admin/papers/990103') {
    if (request.method() === 'PUT') {
      assert(!Object.hasOwn(request.postDataJSON(), 'research_materials'), '材料汇总不能先于科学数据事务保存')
      paper = { ...paper, ...request.postDataJSON() }
    }
    return json({ ...paper, material_states: states })
  }
  if (path.endsWith('/scientific-draft')) {
    const body = request.postDataJSON(); states = body.material_states; scientificSaves++
    paper.research_materials = [...new Set(states.map(s => s.material_name || s.material).filter(Boolean))]
    return json({ ok: true, data: { revision_bumped: false } })
  }
  if (path.endsWith('/draft')) {
    if (request.method() === 'PUT') { savedDraft = request.postDataJSON(); paper = { ...paper, ...savedDraft.paper }; states = savedDraft.material_states; candidates = savedDraft.structure_candidates }
    return json({ ok: true, data: savedDraft || { paper, material_states: states, structure_candidates: candidates } })
  }
  if (path.endsWith('/submit')) { submits++; return json({ ok: true, paper_id: paper.id, review_status: 'pending' }) }
  assert(!path.endsWith('/jobs') && !path.endsWith('/review'), '不得请求 AI 或正式审核')
  return json({ items: [], total: 0 })
})
const page = await context.newPage(), errors = []
page.on('pageerror', e => errors.push(e.message))
const noOverflow = async () => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), '页面横向溢出')
async function mount(mode, data) {
  await page.goto(`${base}/login`)
  await page.evaluate(async ({ mode, data }) => {
    const { default: React } = await import('/node_modules/.vite/deps/react.js')
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
    const { LanguageProvider } = await import('/src/context/LanguageContext.tsx')
    const { default: Component } = await import(mode === 'upload' ? '/src/components/UploadTaskEditor.tsx' : '/src/components/PaperEditView.tsx')
    document.getElementById('root').style.display = 'none'
    const host = document.createElement('main'); host.style.cssText = 'max-width:1200px;margin:auto;padding:16px;box-sizing:border-box'; document.body.append(host)
    ReactDOM.createRoot(host).render(React.createElement(LanguageProvider, {}, React.createElement(Component, mode === 'upload' ? { taskId: 'a'.repeat(32), draftOverride: data, onSubmitted() {} } : { paper: data, onBack() {} })))
  }, { mode, data })
}
try {
  await mount('upload', { paper, material_states: states, structure_candidates: candidates })
  await page.getByRole('table', { name: '晶格矩阵', exact: true }).waitFor()
  assert.equal(await page.getByLabel('材料状态类型', { exact: true }).count(), 4)
  const layout = page.locator('[data-crystal-layout]').first()
  const columns = await layout.locator(':scope > div').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').map(Number.parseFloat))
  assert.equal(columns.length, 2); assert(Math.abs(columns[0] - columns[1]) < 1)
  await layout.scrollIntoViewIfNeeded()
  const canvas = layout.locator('canvas').first()
  await page.waitForTimeout(500)
  const pixels = await canvas.evaluate(el => {
    const copy = document.createElement('canvas'); copy.width = el.width; copy.height = el.height
    const ctx = copy.getContext('2d'); ctx.drawImage(el, 0, 0)
    const { data } = ctx.getImageData(0, 0, copy.width, copy.height)
    let colored = 0
    for (let i = 0; i < data.length; i += 4) if (data[i + 3] && Math.max(data[i], data[i + 1], data[i + 2]) - Math.min(data[i], data[i + 1], data[i + 2]) > 25) colored++
    return colored
  })
  assert(pixels > 100, `模型非空像素: ${pixels}`)
  const before = await canvas.screenshot()
  await layout.getByRole('button', { name: '旋转结构', exact: true }).click()
  assert(!before.equals(await canvas.screenshot()), '旋转必须改变画布')
  await layout.getByRole('button', { name: '放大结构', exact: true }).click()
  await layout.getByRole('button', { name: '重置视角', exact: true }).click()
  const panel = page.locator('[data-scientific-structure]').first()
  await panel.getByRole('combobox', { name: '结构格式' }).click()
  await page.getByRole('option', { name: 'POSCAR', exact: true }).click()
  await layout.getByRole('table', { name: '晶格矩阵', exact: true }).getByText('7.0000', { exact: true }).waitFor()
  const atoms = layout.getByRole('table', { name: '原子位置（2）' })
  assert((await atoms.innerText()).includes('0.7500'))
  await layout.getByRole('button', { name: '直角坐标 (Å)' }).click()
  assert((await atoms.innerText()).includes('2.6250'))
  await panel.getByRole('combobox', { name: '晶胞表示' }).click()
  await page.getByRole('option', { name: '原胞', exact: true }).click()
  await layout.getByRole('table', { name: '晶格矩阵', exact: true }).getByText('3.0000', { exact: true }).waitFor()
  await page.waitForTimeout(300)
  await layout.screenshot({ path: `${artifacts}/desktop.png` })
  await panel.getByRole('combobox').first().click()
  await page.getByRole('option', { name: 'Sn-1.cif', exact: true }).click()
  assert.equal(await panel.getAttribute('data-structure-id'), 'structure_1')
  await panel.getByRole('combobox', { name: '晶胞表示' }).click()
  await page.getByRole('option', { name: '惯用胞', exact: true }).click()
  await layout.getByRole('table', { name: '晶格矩阵', exact: true }).getByText('5.0000', { exact: true }).waitFor()
  await page.getByRole('button', { name: '全部折叠', exact: true }).click()
  await page.getByRole('button', { name: 'Sn · #2', exact: true }).click()
  assert.equal(await page.locator('[data-material-state-index="1"] [data-state-toggle]').getAttribute('aria-expanded'), 'true')
  await page.getByRole('button', { name: '全部展开', exact: true }).click()
  await page.getByLabel('论文与该材料的关系', { exact: true }).fill('保存后保留证据来源')
  await page.getByLabel('材料名', { exact: true }).first().fill('Pure tin')
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/draft')), page.getByRole('button', { name: '立即保存', exact: true }).click()])
  assert.equal(savedDraft.paper.material_relations[0].quote, 'fixture evidence')
  assert(savedDraft.paper.research_materials.includes('Pure tin'))
  await page.getByRole('button', { name: '提交审核', exact: true }).click()
  await page.waitForTimeout(300)
  assert.equal(submits, 1)
  await page.goto(`${base}/admin/papers/990103/edit`)
  await page.getByLabel('材料名', { exact: true }).first().fill('Reviewed tin')
  await page.getByLabel('论文与该材料的关系', { exact: true }).fill('管理员修改关系')
  await page.getByLabel('材料状态类型', { exact: true }).first().click()
  await page.getByRole('option', { name: '理论与实验', exact: true }).click()
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/scientific-draft')), page.getByRole('button', { name: '保存修改', exact: true }).click()])
  assert.equal(scientificSaves, 1)
  assert.equal(JSON.parse(paper.material_relations)[0].quote, 'fixture evidence')
  assert.equal(states[0].state_kind, 'mixed')
  assert(paper.research_materials.includes('Reviewed tin'))
  await page.reload()
  await page.getByLabel('材料名', { exact: true }).first().waitFor()
  assert.equal(await page.getByLabel('材料名', { exact: true }).first().inputValue(), 'Reviewed tin')
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 }); await page.waitForTimeout(200)
    await noOverflow()
    await page.locator('[data-crystal-layout]').first().scrollIntoViewIfNeeded()
    const grid = await page.locator('[data-crystal-layout] > div').first().evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length)
    assert.equal(grid, 1)
    await page.locator('[data-crystal-layout]').first().screenshot({ path: `${artifacts}/mobile-${width}.png` })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mount('detail', { ...paper, material_states: states })
  await page.getByText('管理员修改关系', { exact: true }).waitFor()
  assert.equal(await page.getByRole('textbox').count(), 0)
  assert.equal(await page.getByText('理论与实验', { exact: true }).count(), 1)
  await noOverflow()
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    await noOverflow()
  }
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ result: 'passed', pixels, submits, scientificSaves, screenshots: artifacts }))
} finally { await browser.close() }
