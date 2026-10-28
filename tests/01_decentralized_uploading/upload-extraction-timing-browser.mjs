// 真实/upload页面，所有API隔离；计时夹具由生产状态转换生成。
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { preview } from '../../frontend/node_modules/vite/dist/node/index.js'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = fileURLToPath(new URL('../../', import.meta.url))
const output = process.env.TIMING_TEST_OUTPUT || '/tmp/scwiki170-browser-output'
const python = process.env.TIMING_TEST_PYTHON || 'python3'
const states = JSON.parse(execFileSync(python, ['-c', `
import json
from backend.ingest.upload_contracts import apply_state_changes, new_extraction_timing, public_task_state
state = dict(task_id='a'*32, filename='2012 CaH6--suppliment--王晖.pdf', status='queued', stage='queued', stage_index=1, stage_total=5, processing_status='processing', completed_chunks=0, total_chunks=0, extraction_timing=new_extraction_timing())
result = {'queued': public_task_state(state)}
for name, now, status in [('running',1800000000,'extracting'), ('paused',1800000030,'needs_role_review'), ('resume_queue',1800000100,'queued'), ('resumed',1800000200,'extracting'), ('ready',1800000375,'ready')]:
    state = apply_state_changes(state, now=now, status=status, stage=status)
    result[name] = public_task_state(state)
print(json.dumps(result))
`], { cwd: root, encoding: 'utf8' }))
await mkdir(output, { recursive: true })
const server = await preview({ configFile: false, root: `${root}frontend`, build: { outDir: 'static' },
  preview: { host: '127.0.0.1', port: 5197 } })
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const errors = [], checks = []
let activePage
try {
  for (const [width, language] of [[1440, 'zh'], [390, 'zh'], [390, 'en']]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } })
    await context.addInitScript(language => {
      localStorage.setItem('auth_token', 'isolated-test')
      localStorage.setItem('sc-wiki.language', language)
      localStorage.setItem('auth_user', JSON.stringify({ id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' }))
    }, language)
    let current = structuredClone(states.running), cancelled = 0
    const legacy = { ...states.ready, task_id: 'b'.repeat(32), filename: '历史记录.pdf', extraction_timing: null }
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
      if (path === '/api/upload-tasks') return json({ ok: true, data: [current, legacy] })
      if (path === `/api/upload-tasks/${current.task_id}/cancel` && req.method() === 'POST') {
        cancelled++; current = { ...states.ready, status: 'cancelled' }; return json({ ok: true })
      }
      if (path === '/api/auth/me') return json({ user: { id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' } })
      if (path === '/api/rag/llm/catalog') return json({ data: { items: [] } })
      if (path === '/api/rag/llm/current') return json({ data: { provider: 'fixture', model: 'fixture' } })
      if (path === '/api/community/notifications/unread') return json({ count: 0 })
      errors.push(`Unexpected API: ${req.method()} ${path}`)
      return route.fulfill({ status: 500, body: 'Unexpected isolated request' })
    })
    const page = await context.newPage()
    activePage = page
    page.setDefaultTimeout(10000)
    page.on('pageerror', error => errors.push(error.message))
    await page.clock.setFixedTime(new Date(1800000205000))
    console.log(`验证 ${width}px ${language}`)
    await page.goto(`${base}/upload`)
    const label = language === 'zh' ? '提取内容用时：' : 'Extraction time: '
    const text = (m, s) => label + (language === 'zh' ? `${m} 分 ${s} 秒` : `${m}m ${s}s`)
    await page.getByText(text(3, 25), { exact: true }).waitFor()
    const first = page.locator('.MuiCard-root').filter({ hasText: current.filename })
    const duration = first.getByText(new RegExp(label))
    const before = await duration.innerText()
    await page.clock.setFixedTime(new Date(1800000206000))
    await page.waitForTimeout(1100)
    assert.notEqual(await duration.innerText(), before, '运行时秒数增长')
    current = structuredClone(states.ready)
    await page.waitForTimeout(3300)
    await page.getByText(text(3, 25), { exact: true }).waitFor()
    await page.clock.setFixedTime(new Date(1800000216000))
    await page.waitForTimeout(1100)
    assert.equal(await duration.innerText(), text(3, 25), '自动读取终态并固定')
    await page.reload()
    await page.getByText(text(3, 25), { exact: true }).waitFor()
    assert.equal(await page.getByText(label + (language === 'zh' ? '未记录' : 'Not recorded'), { exact: true }).count(), 1)
    await first.getByRole('checkbox').check()
    assert(await first.getByRole('checkbox').isChecked())
    await first.getByRole('checkbox').uncheck()
    const link = first.getByRole('link')
    assert.equal(await link.getAttribute('target'), '_blank')
    assert.equal(await link.getAttribute('href'), `/upload/tasks/${current.task_id}`)
    const [titleBox, timeBox] = await Promise.all([link.boundingBox(), duration.boundingBox()])
    assert(timeBox.x >= 0 && timeBox.x + timeBox.width <= width + 1, '时长在可视范围内')
    if (width > 600) assert(Math.abs(titleBox.y - timeBox.y) < 12, '桌面标题旁显示')
    else assert(timeBox.y >= titleBox.y + titleBox.height, '窄屏换行')
    await page.screenshot({ path: `${output}/${language}-${width}.png`, fullPage: true })
    // 已完成任务暂停轮询，手动刷新模拟另一个标签页引起的角色恢复。
    const refresh = page.getByRole('button', { name: language === 'zh' ? '刷新' : 'Refresh', exact: true })
    current = { ...states.paused, filename: '非常长的论文文件名-'.repeat(12) + '.pdf' }
    await refresh.click()
    await page.getByText(text(0, 30), { exact: true }).waitFor()
    await page.clock.setFixedTime(new Date(1800000226000))
    await page.waitForTimeout(3300)
    assert.equal(await page.getByText(text(0, 30), { exact: true }).count(), 1)
    const timeBounds = await page.getByText(text(0, 30), { exact: true }).boundingBox()
    assert(timeBounds.x + timeBounds.width <= width + 1, '长文件名不挤掉用时')
    current = structuredClone(states.resumed)
    await page.waitForTimeout(3300)
    await page.getByRole('button', { name: language === 'zh' ? '取消' : 'Cancel', exact: true }).waitFor()
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: language === 'zh' ? '取消' : 'Cancel', exact: true }).click()
    await page.getByText(language === 'zh' ? '已取消' : 'Cancelled', { exact: true }).waitFor()
    assert.equal(cancelled, 1)
    checks.push({ width, language, live: true, frozen: true, reload: true, paused: true, legacy: true, layout: true, controls: true })
    await context.close()
  }
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ checks, output }))
} catch (error) {
  if (activePage && !activePage.isClosed()) {
    console.error(await activePage.locator('body').innerText())
    await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true })
  }
  console.error(errors)
  throw error
} finally {
  await browser.close()
  await new Promise(resolve => server.httpServer.close(resolve))
}
