// 实际四入口与浏览器原生剪贴板；全部业务接口隔离，不访问用户数据。
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const results = []
try {
  for (const mode of ['upload', 'revision', 'admin', 'superadmin']) {
    const context = await browser.newContext({ viewport: { width: mode === 'superadmin' ? 390 : 1440, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] })
    const user = { id: 7, username: 'fixture', role: ['admin', 'superadmin'].includes(mode) ? mode : 'user', is_approved: true, is_email_verified: true, account_status: 'active' }
    await context.addInitScript(({ user }) => {
      localStorage.setItem('auth_token', 'fixture-only')
      localStorage.setItem('auth_user', JSON.stringify(user))
      localStorage.setItem('sc-wiki.language', 'zh')
      localStorage.setItem('scwiki_active_upload_task:7', 'a'.repeat(32))
    }, { user })
    let version = 1, draftVersion = 1, fileID = 0
    let draft = { paper: { title: '原始标题', journal: '原始期刊', authors: [], corresponding_authors: [], co_first_authors: [], paper_type: 'experimental', superconductor_kind: 'unknown', material_families: [], keywords_tags: [], methodology: [] }, material_states: [], structure_candidates: [], classification_evidence: [], field_evidence: {} }
    const initial = structuredClone(draft.paper), saved = new Map(), requests = []
    const keys = { title: 'a'.repeat(64), journal: 'b'.repeat(64) }
    const record = field => ({ key: field, item_key: keys[field], field: `paper.${field}`, label: field === 'title' ? '标题' : '期刊', current_value: draft.paper[field], status: 'supported', reason: '隔离原文', evidences: [] })
    const manual = field => ({ changed: draft.paper[field] !== initial[field], status: 'draft', reason: '', no_evidence_reason: '', items: [], ...(saved.get(field) || {}) })
    const revisionResponse = () => ({ ok: true, data: draft, revision_id: 'b'.repeat(32), draft_version: draftVersion })
    await context.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname, method = request.method()
      requests.push({ path, method })
      const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/rag/llm/catalog') return json({ data: { items: [] } })
      if (path.includes('/manual/')) {
        const field = Object.keys(keys).find(field => path.includes(keys[field]))
        assert(field, path)
        if (path.endsWith('/files') && method === 'POST') {
          const body = request.postDataBuffer().toString('latin1')
          assert(body.includes(`\r\n\r\nv${version}\r\n`), '上传必须使用保存后版本')
          const name = /filename="([^"]+)"/.exec(body)?.[1]
          const value = manual(field)
          value.items.push({ id: String(++fileID), filename: name, source_description: name, kind: name.endsWith('.png') ? 'image' : 'pdf' })
          saved.set(field, value)
          return json({ ok: true, data: value })
        }
        if (method === 'PUT') {
          const body = request.postDataJSON()
          assert.equal(body.expected_version, `v${version}`)
          assert.notEqual(draft.paper[field], initial[field], '先保存主值')
          const value = { ...manual(field), reason: body.reason, no_evidence_reason: body.no_evidence_reason }
          saved.set(field, value)
          return json({ ok: true, data: value })
        }
        return json({ ok: true, data: manual(field) })
      }
      if (path.endsWith('/preflight')) return json({ version: `v${version}`, needs_check: false, records: [record('title'), record('journal')] })
      if (path.endsWith('/revision-draft')) {
        if (method === 'PUT') { draft = request.postDataJSON().draft; version++; draftVersion++ }
        return json(revisionResponse())
      }
      if (path.endsWith('/draft')) {
        if (method === 'PUT') { draft = request.postDataJSON(); version++ }
        return json({ ok: true, data: draft })
      }
      if (path === '/api/admin/papers/990138') {
        if (method === 'PUT') { draft.paper = { ...draft.paper, ...request.postDataJSON() }; version++ }
        return json({ ...draft.paper, id: 990138, year: 2026, review_status: 'pending', material_states: [] })
      }
      if (path.endsWith('/review-artifact')) return json({ data: {} })
      if (path === '/api/classification-catalogs') return json({ material_families: [], structure_families: [], material_dimensionalities: [] })
      if (path.endsWith('/space-groups')) return json({ space_groups: [] })
      if (path.endsWith('/parsing')) return json({ ok: true, data: { status: 'ready', next_poll_ms: null, files: [], chunks: [], summary: { status: 'ready', completed: 0, total: 0 } } })
      if (path === `/api/upload-tasks/${'a'.repeat(32)}`) return json({ ok: true, data: { task_id: 'a'.repeat(32), status: 'ready', processing_status: 'completed', filename: 'fixture.pdf', files: [], progress: 100, stage_index: 5, stage_total: 5 } })
      assert(!path.endsWith('/jobs') && !path.endsWith('/submit') && !path.endsWith('/review'), `不能调用模型、提交或批准：${path}`)
      return json({ items: [], total: 0, records: [], data: [] })
    })
    const page = await context.newPage(), errors = []
    page.setDefaultTimeout(10000)
    let navigations = 0
    const navigationURLs = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) { navigations++; navigationURLs.push(frame.url()) } })
    const url = mode === 'upload' ? '/upload' : mode === 'revision' ? '/papers/990138/revise' : '/admin/papers/990138/edit'
    await page.goto(origin + url)
    await page.locator('[data-issue-field="paper.title"]').first().waitFor()
    const initialNavigations = navigations
    const field = name => page.locator(`[data-issue-field="paper.${name}"]`).first()
    const open = async name => {
      await field(name).locator('label[role="button"]').click()
      await page.getByLabel('人工修改判断理由（必填）').waitFor()
      await page.waitForFunction(() => {
        const drawer = document.querySelector('.evidence-review-drawer')
        if (!drawer) return false
        const box = drawer.getBoundingClientRect()
        return box.left >= -1 && box.right <= innerWidth + 1
      })
    }
    const close = () => page.getByLabel('关闭来源详情').click()
    try { await field('title').locator('input,textarea').first().fill(`人工标题 ${mode}`) }
    catch (error) { console.error(JSON.stringify({ mode, requests, errors, body: await page.locator('body').innerText() })); throw error }
    await open('title')
    await page.getByLabel('人工修改判断理由（必填）').fill('标题理由必须保留')
    await page.getByLabel('不提供证据', { exact: true }).check()
    await page.getByLabel('不提供证据的理由（必填）').fill('切换选择也保留')
    await page.getByLabel('提供证据', { exact: true }).check()
    assert.equal(requests.filter(r => r.path.includes('/manual/') && r.method === 'PUT').length, 0)
    const zone = page.getByRole('region', { name: '人工证据拖拽与粘贴区域' })
    await page.evaluate(async () => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 8
      canvas.getContext('2d').fillRect(0, 0, 8, 8)
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    })
    await zone.focus()
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+V' : 'Control+V')
    await page.getByAltText('人工提供的截图').waitFor()
    await zone.evaluate(element => {
      const data = new DataTransfer()
      data.items.add(new File(['%PDF-1.4\nfixture'], 'fixture.pdf', { type: 'application/pdf' }))
      element.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }))
    })
    await page.getByText('待上传：fixture.pdf', { exact: true }).waitFor()
    const chooserPromise = page.waitForEvent('filechooser')
    await page.getByText('选择图片、文本或 PDF', { exact: true }).click()
    const chooser = await chooserPromise
    await chooser.setFiles([])
    await close()
    await field('journal').locator('input,textarea').first().fill(`人工期刊 ${mode}`)
    await open('journal')
    await page.getByLabel('人工修改判断理由（必填）').fill('期刊理由独立保存')
    await page.getByLabel('不提供证据', { exact: true }).check()
    await page.getByLabel('不提供证据的理由（必填）').fill('没有附件')
    await close()
    await open('title')
    assert.equal(await page.getByLabel('人工修改判断理由（必填）').inputValue(), '标题理由必须保留')
    await page.getByText('待上传：fixture.pdf', { exact: true }).waitFor()
    assert.equal(navigations, initialNavigations, `切换、选择文件与粘贴不能导航：${JSON.stringify(navigationURLs)}`)
    await page.getByRole('button', { name: '上传人工证据', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'hidden' })
    assert.equal(saved.get('title').items.length, 2)
    await open('journal')
    assert.equal(await page.getByLabel('人工修改判断理由（必填）').inputValue(), '期刊理由独立保存')
    await page.getByRole('button', { name: '保存人工修改说明', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'hidden' })
    assert.equal(navigations, initialNavigations)
    await page.reload()
    await open('title')
    assert.equal(await page.getByLabel('人工修改判断理由（必填）').inputValue(), '标题理由必须保留')
    await page.getByRole('button', { name: 'fixture.pdf', exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, '页面无横向溢出')
    assert.equal(await page.locator('.evidence-review-drawer').evaluate(el => el.scrollWidth > el.clientWidth + 1), false, '侧栏无横向溢出')
    assert.deepEqual(errors, [])
    if (process.env.ARTIFACT_DIR) { await fs.mkdir(process.env.ARTIFACT_DIR, { recursive: true }); await page.screenshot({ path: `${process.env.ARTIFACT_DIR}/${mode}.png` }) }
    results.push({ mode, browser: await browser.version(), width: mode === 'superadmin' ? 390 : 1440, nativeClipboard: true, dragDrop: true, fieldIsolation: true, savedReload: true, unexpectedNavigations: navigations - initialNavigations - 1 })
    await context.close()
  }
  console.log(JSON.stringify(results, null, 2))
} finally { await browser.close() }
