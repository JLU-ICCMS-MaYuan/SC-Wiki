// 完整上传页的真实浏览器交互；全部 API 隔离，不写业务服务。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output = process.env.UPLOAD_FILES_OUTPUT || '/tmp/scwiki179-browser'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const results = []
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1050 } })
    const user = { id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' }
    await context.addInitScript(user => {
      localStorage.setItem('auth_token', 'isolated-fixture')
      localStorage.setItem('auth_user', JSON.stringify(user))
      localStorage.setItem('sc-wiki.language', 'zh')
    }, user)
    const creations = [], uploads = [], errors = []
    let task = null
    await context.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname
      const json = data => route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
      if (path === '/api/auth/me') return json({ user })
      if (path === '/api/upload-tasks') {
        if (request.method() === 'POST') {
          const body = request.postDataJSON()
          creations.push(body)
          task = { task_id: '1'.repeat(32), filename: 'main-SI.pdf', status: 'queued',
            files: body.files.map((file, i) => ({ ...file, file_id: String(i), original_filename: file.filename })) }
          return json({ ok: true, data: task })
        }
        return json({ ok: true, data: [] })
      }
      if (path.includes('/files/') && request.method() === 'PUT') {
        uploads.push(path)
        return json({ ok: true })
      }
      if (task && path === '/api/upload-tasks/' + task.task_id) return json({ ok: true, data: task })
      if (request.method() !== 'GET') throw new Error('意外写请求：' + request.method() + ' ' + path)
      return json({ items: [], total: 0 })
    })
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5199') + '/upload')
    const area = name => page.getByRole('region', { name, exact: true })
    const payload = name => ({ name, mimeType: 'text/plain', buffer: Buffer.from(name) })
    await area('论文正文').waitFor()
    await area('补充材料').locator('input').setInputFiles([payload('si.pdf'), payload('correction.txt')])
    await page.getByRole('button', { name: '开始上传并解析', exact: true }).click()
    await page.getByRole('alert').filter({ hasText: '必须恰好选择一个正文' }).waitFor()
    assert.equal(creations.length, 0)
    const choose = area('论文正文').getByRole('button')
    await choose.focus()
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), choose.press('Enter')])
    await chooser.setFiles(payload('main-SI.pdf'))
    await area('论文正文').locator('input').setInputFiles(payload('second.pdf'))
    await page.getByRole('alert').filter({ hasText: '只能上传一个正文' }).waitFor()
    assert.equal(await area('论文正文').getByText('second.pdf', { exact: true }).count(), 0)
    await area('源数据文件').locator('input').setInputFiles(payload('misplaced.pdf'))
    await page.getByRole('alert').filter({ hasText: '结构格式' }).waitFor()
    await area('源数据文件').locator('input').setInputFiles([payload('cell.cif'), payload('POSCAR')])
    assert.equal(await page.getByRole('combobox').count(), 0)
    assert.equal(creations.length, 0, '选择不创建任务或调用模型')
    await page.getByRole('button', { name: '移除 si.pdf', exact: true }).click()
    assert.equal(await area('补充材料').getByText('si.pdf', { exact: true }).count(), 0)
    await area('补充材料').locator('input').setInputFiles(payload('si.pdf'))
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), '页面无横向溢出')
    await page.screenshot({ path: output + '/upload-' + width + '.png', fullPage: true })
    await page.getByRole('button', { name: '开始上传并解析', exact: true }).click()
    await page.waitForFunction(() => !document.body.textContent.includes('main-SI.pdf'))
    assert.equal(creations.length, 1)
    assert.equal(uploads.length, 5)
    assert.deepEqual(Object.fromEntries(creations[0].files.map(f => [f.filename, f.role])), {
      'main-SI.pdf': 'main', 'si.pdf': 'supplementary', 'correction.txt': 'supplementary',
      'cell.cif': 'attachment', POSCAR: 'attachment',
    })
    assert.equal(errors.length, 0, errors.join('\n'))
    results.push({ width, files: 5, creations: 1, uploads: uploads.length, role_confirmation_requests: 0,
      keyboard: true, wrong_area: true, duplicate_main: true, zero_selection_writes: true, overflow: false, errors })
    await context.close()
  }
  await writeFile(output + '/result.json', JSON.stringify(results, null, 2))
  console.log(JSON.stringify(results))
} finally { await browser.close() }
