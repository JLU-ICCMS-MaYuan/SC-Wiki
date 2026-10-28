// 配合evidence_progress_bridge.py；全部业务请求仅发往隔离的本机夹具。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js'
import react from '../../frontend/node_modules/@vitejs/plugin-react/dist/index.js'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = fileURLToPath(new URL('../../', import.meta.url))
const backend = process.env.PROGRESS_TEST_API || 'http://127.0.0.1:8198'
const output = process.env.PROGRESS_TEST_OUTPUT || '/tmp/scwiki168-browser-output'
await mkdir(output, { recursive: true })
const aliases = Object.fromEntries(['react', 'react-dom', '@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled', 'react-router-dom'].map(name => [name, `${root}frontend/node_modules/${name}`]))
const testPage = { name: 'isolated-progress-page', configureServer(server) {
  server.middlewares.use('/__progress', async (_req, res) => {
    res.setHeader('Content-Type', 'text/html')
    res.end(await server.transformIndexHtml('/__progress', '<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/tests/01_decentralized_uploading/evidence-progress-browser.tsx"></script></body></html>'))
  })
} }
const server = await createServer({ configFile: false, root, plugins: [react(), testPage], resolve: { alias: aliases },
  server: { host: '127.0.0.1', port: 5198, strictPort: false, proxy: { '/api': backend } } })
await server.listen()
const frontend = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const checks = [], errors = []
const control = async (path, body) => {
  const response = await fetch(backend + '/fixture/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  assert.equal(response.status, 200)
}
try {
  for (const [target, width, language] of [['upload', 1440, 'zh'], ['paper', 390, 'zh'], ['revision', 390, 'en']]) {
    await control('mode', { mode: 'normal' })
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${frontend}/__progress?target=${target}`)
    if (language === 'en') await page.getByText('English', { exact: true }).click()
    await page.getByRole('button', { name: '开始核对' }).click()
    const progress = page.getByRole('progressbar')
    const at = async value => {
      await page.waitForFunction(value => {
        const progress = document.querySelector('[role="progressbar"]')
        const bar = progress?.querySelector('.MuiLinearProgress-bar')
        if (!bar || progress.getAttribute('aria-valuenow') !== String(value)) return false
        const outer = progress.getBoundingClientRect(), inner = bar.getBoundingClientRect()
        return Math.abs((inner.right - outer.x) / outer.width * 100 - value) < .1
      }, value)
    }
    await at(0); await at(5)
    await page.screenshot({ path: `${output}/${target}-preparing.png` })
    await at(10); await at(20)
    await control('job', { status: 'running', completed_batches: 2, current_batch: 3 })
    await at(50)
    await page.getByText(language === 'en' ? 'Checked 2/5 source groups · 50%' : '已核对 2/5 组原文 · 50%').waitFor()
    const bounds = await progress.boundingBox()
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width)
    const dialog = page.getByRole('dialog')
    assert.equal(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth), true)
    await page.screenshot({ path: `${output}/${target}-50.png` })
    await control('job', { completed_batches: 5, current_batch: 0 })
    await at(95)
    await page.screenshot({ path: `${output}/${target}-95.png` })
    await control('job', { status: 'completed' })
    await at(100)
    await page.screenshot({ path: `${output}/${target}-100.png` })
    await page.locator('output').getByText('completed').waitFor()
    checks.push({ target, width, language, percentages: [0, 5, 10, 20, 50, 95, 100], overflow: false })
    await page.close()
  }
  const page = await browser.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${frontend}/__progress`)
  await page.getByRole('button', { name: '开始核对' }).click()
  await page.waitForFunction(() => document.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow') === '5')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await page.locator('output').getByText('stopped').waitFor()
  await control('mode', { mode: 'reused' })
  await page.getByRole('button', { name: '开始核对' }).click()
  await page.locator('output').getByText('completed').waitFor()
  checks.push({ cancelDuringPreparation: true, retryReusesResult: true })
  for (const mode of ['failed', 'stale']) {
    await control('mode', { mode })
    await page.getByRole('button', { name: '开始核对' }).click()
    await page.waitForFunction(() => document.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow') === '20')
    await page.evaluate(() => { window.sawComplete = false; window.progressObserver = new MutationObserver(() => { if (document.querySelector('[aria-valuenow="100"]')) window.sawComplete = true }); window.progressObserver.observe(document.body, { subtree: true, attributes: true, childList: true }) })
    await control('job', mode === 'failed' ? { status: 'failed', error: { message: '隔离模型失败' } } : { status: 'completed' })
    await page.locator('output').getByText('stopped').waitFor()
    assert.equal(await page.evaluate(() => { window.progressObserver.disconnect(); return window.sawComplete }), false)
    checks.push({ mode, falseCompletion: false })
  }
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({ checks, errors, limitation: '正式共用React组件与FastAPI进度/任务读取路由、真实隔离Redis；科学来源、排队和模型结果为受控夹具，不调用真实模型或用户数据库。' }, null, 2))
  console.log(JSON.stringify({ checks: checks.length, errors, output }))
} finally {
  await browser.close()
  await server.close()
}
