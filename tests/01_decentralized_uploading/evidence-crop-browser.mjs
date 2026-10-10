// 真实浏览器组件验收：只截获区域接口，不访问或修改论文记录。
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH,
  args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
const artifacts = process.env.ARTIFACT_DIR || '/tmp/scwiki-109-crops'
const pixel = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
await mkdir(artifacts, { recursive: true })
try {
  for (const role of ['upload', 'admin', 'superadmin']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    await context.route('**/api/**', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(
      route.request().url().endsWith('/region')
        ? { status: 'located', dpi: 300, pdf_page: 1, parser: { name: 'text', mode: 'legacy_text' },
            crops: [{ image: `data:image/png;base64,${pixel}`, width: 1200, height: 400,
              pdf_page: 1, highlights: [[0.1, 0.2, 0.5, 0.1]] }] }
        : { ok: true, items: [] }) }))
    const page = await context.newPage()
    await page.goto(`${base}/login`)
    await page.evaluate(async target => {
      const { default: React } = await import('/node_modules/.vite/deps/react.js')
      const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
      const { LanguageProvider } = await import('/src/context/LanguageContext.tsx')
      const { EvidenceRegion } = await import('/src/components/EvidenceRegion.tsx')
      document.getElementById('root').style.display = 'none'
      const host = document.createElement('main')
      host.style.cssText = 'width: min(480px, 100vw); margin-left: auto; padding: 12px;'
      document.body.append(host)
      ReactDOM.createRoot(host).render(React.createElement(LanguageProvider, {},
        React.createElement(EvidenceRegion, { target, source: { file_id: 'main', source_name: 'main.pdf',
          quote: 'Tc reaches 200 K at 150 GPa.' } })))
    }, { target: role === 'upload' ? 'upload' : 'paper', target_id: 'fixture' })
    await page.getByRole('button', { name: '查看原 PDF 区域' }).click()
    await page.getByText(/300 DPI/).waitFor()
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 })
      const button = page.getByRole('button', { name: '点击放大 PDF 局部证据' })
      const scroll = button.locator('..')
      const dimensions = await scroll.evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth }))
      assert(dimensions.scroll > dimensions.client, `${role}/${width}: 原始尺寸应可横向滚动`)
      assert.equal(await button.locator('img').evaluate(image => Math.round(image.getBoundingClientRect().width)), 1200)
      await button.click()
      const dialog = page.getByRole('dialog', { name: /main.pdf/ })
      await dialog.waitFor()
      await page.screenshot({ path: `${artifacts}/${role}-${width}.png` })
      await dialog.getByRole('button', { name: '点击缩回 PDF 局部证据' }).last().click()
      await dialog.waitFor({ state: 'detached' })
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    }
    console.log(JSON.stringify({ role, widths: [1440, 390, 320], result: 'passed' }))
    await context.close()
  }
} finally {
  await browser.close()
}
