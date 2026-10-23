import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || '../../prototypes/account-center/node_modules/playwright/index.mjs')
const base = process.env.NOBEL_DEMO_URL || 'http://127.0.0.1:5174/nobel-demo.html'
const output = new URL('../../docs/specs/159-nobel-portrait-exhibition/assets/validation/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const results = {}
try {
  await page.goto(base)
  const ring = page.locator('.nobel-ring')
  const transform = () => ring.evaluate(e => getComputedStyle(e).transform)
  const before = await transform()
  await page.waitForTimeout(350)
  assert.notEqual(await transform(), before)
  // 动画中的元素不会满足 Playwright 的稳定性等待；按当前可见坐标移动真实指针。
  const movingFace = await page.locator('a[href$="person=onnes"].nobel-face').boundingBox()
  await page.mouse.move(movingFace.x + movingFace.width / 2, movingFace.y + movingFace.height / 2)
  assert.equal(await ring.evaluate(e => getComputedStyle(e).animationPlayState), 'paused')
  const frozen = await transform()
  await page.waitForTimeout(300)
  assert.equal(await transform(), frozen)
  await page.mouse.move(0, 0)
  await page.waitForTimeout(300)
  assert.notEqual(await transform(), frozen)
  results.motion = '旋转、肖像悬停暂停、移开恢复通过'
  await page.getByRole('button', { name: 'Onnes', exact: true }).click()
  await page.screenshot({ path: new URL('desktop.png', output).pathname, fullPage: true })
  const [popup] = await Promise.all([
    page.waitForEvent('popup'),
    page.locator('.nobel-face[href$="person=onnes"]').click(),
  ])
  await popup.waitForLoadState()
  assert.equal(new URL(popup.url()).searchParams.get('person'), 'onnes')
  assert.equal(await popup.evaluate(() => window.opener === null), true)
  assert.equal(new URL(page.url()).searchParams.has('person'), false)
  await popup.close()
  results.popup = '真实点击打开独立标签页，opener 为空，原展陈保持'
  const hrefs = await page.locator('.nobel-face').evaluateAll(es => es.map(e => e.href))
  assert.equal(hrefs.length, 12)
  for (const url of hrefs) {
    await page.goto(url)
    await page.locator('.nobel-detail-portrait img').evaluate(img => img.decode())
    assert.equal(await page.locator('.nobel-biography h1').count(), 1)
    assert.equal(await page.locator('.nobel-biography section').count(), 4)
    for (const href of await page.locator('.nobel-citations a').evaluateAll(es => es.map(e => e.getAttribute('href')))) {
      assert.equal(await page.locator(href).count(), 1)
    }
  }
  await page.screenshot({ path: new URL('detail.png', output).pathname, fullPage: true })
  results.details = '12 个详情页、头像解码及段落引用锚点通过（不代表外部来源内容全部核验）'
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(base)
  assert.equal(await ring.evaluate(e => getComputedStyle(e).animationName), 'none')
  for (const name of ['Onnes','Bardeen','Cooper','Schrieffer','Esaki','Giaever','Josephson','Bednorz','Müller','Abrikosov','Ginzburg','Leggett']) {
    await page.getByRole('button', { name, exact: true }).click()
    const selected = page.locator('.nobel-face.is-selected')
    const rect = await selected.boundingBox()
    assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= 390, `${name} 肖像需在移动端可见`)
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: new URL('mobile-reduced-motion.png', output).pathname, fullPage: true })
  results.mobile = '390px 窄屏无页面横向溢出，减少动态关闭旋转，索引可选全部12人'
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(base)
  await page.locator('.nobel-face').first().focus()
  assert.equal(await page.locator('.nobel-caption h2').textContent().then(x => x.includes('Onnes')), true)
  await page.keyboard.press('Tab')
  assert.equal(await page.locator('.nobel-caption h2').textContent().then(x => x.includes('Bardeen')), true)
  results.keyboard = 'Tab 可按人物顺序聚焦、定格并更新说明'
  assert.deepEqual(errors, [])
  await writeFile(new URL('browser.json', output), JSON.stringify({ date: '2026-10-23', base, results, errors }, null, 2) + '\n')
  console.log(results)
} finally {
  await browser.close()
}
