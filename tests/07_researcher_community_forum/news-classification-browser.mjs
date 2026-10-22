// 实际 React 路由；先读取隔离 MySQL 的 Go 响应，再以布局夹具覆盖三栏长标签边界。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output = process.env.NEWS_BROWSER_OUTPUT || '/tmp/news153-browser'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const context = await browser.newContext({ viewport: { width: 1500, height: 1200 } })
await context.addInitScript(() => { if (!localStorage.getItem('sc-wiki.language')) localStorage.setItem('sc-wiki.language', 'zh') })
const failures = [], results = []
let fixture = false
const feedURL = process.env.NEWS_BROWSER_API || 'http://127.0.0.1:8183'
const response = await context.request.get(`${feedURL}/api/news/feed`)
assert.equal(response.status(), 200)
const baseline = await response.json()
assert.equal(baseline.items[0].theoretical_subtype, 'calculation')
assert.equal(baseline.items[0].material_families[0].name_zh, '氢基超导体')
const families = Array.from({ length: 17 }, (_, id) => ({ id: id + 1, name_zh: `材料家族${id + 1}的较长名称`, name_en: `Long material family name ${id + 1}` }))
await context.route('**/api/**', async route => {
  const url = new URL(route.request().url())
  if (url.pathname === '/api/news/feed') {
    if (!fixture) {
      const upstream = await context.request.get(feedURL + url.pathname + url.search)
      return route.fulfill({ status: upstream.status(), json: await upstream.json() })
    }
    const kind = url.searchParams.get('kind'), page = Number(url.searchParams.get('page'))
    const items = Array.from({ length: 5 }, (_, index) => ({ ...baseline.items[0], id: `${kind}-${index}`, kind,
      display_kind: kind, content_type: '', title: `${kind} ${page}-${index} A long superconductivity research title covering experimental discovery and theoretical interpretation`,
      paper_type: index === 3 ? 'review' : index === 4 ? null : index === 2 ? 'experimental' : 'theoretical',
      theoretical_subtype: index < 2 ? index === 0 ? 'theory' : 'method' : null,
      material_families: index === 4 ? [] : index === 0 ? families : families.slice(0, 1),
      authors: ['A long author name', 'A second author'], journal: 'A journal with a long name',
    }))
    return route.fulfill({ json: { items, total: 11, page, page_size: 5, sources: [] } })
  }
  return route.fulfill({ json: url.pathname === '/api/news' ? [] : {} })
})
const page = await context.newPage()
page.on('pageerror', error => failures.push(error.message))
try {
  await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5183'}/news`)
  await page.getByRole('heading', { name: '中文超导标题 0' }).waitFor()
  assert(await page.getByTestId('news-classification').count() === 5)
  results.push({ scenario: 'Python→MySQL→Go→React', labels: await page.getByTestId('news-classification').first().innerText() })
  fixture = true
  for (const width of [1500, 1024, 736, 390, 320]) {
    await page.setViewportSize({ width, height: 1200 })
    await page.reload()
    await page.getByRole('heading', { name: /^preprint 1-0/ }).waitFor()
    await page.getByTestId('news-classification').first().waitFor()
    await page.waitForTimeout(150)
    const checks = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('li')].filter(node => node.querySelector('h4'))
      return {
        overflow: document.documentElement.scrollWidth > innerWidth,
        cards: cards.length,
        clipped: cards.flatMap(node => {
          const bounds = node.getBoundingClientRect()
          return [...node.querySelectorAll('h4, [data-testid="news-classification"], .MuiTypography-caption')].filter(child => child.getBoundingClientRect().bottom > bounds.bottom + 1).map(child => child.textContent)
        }),
        counters: [...document.querySelectorAll('[data-testid="news-classification"] > div:first-child .MuiChip-label')].filter(node => /^\+\d+$/.test(node.textContent)).map(node => node.textContent),
      }
    })
    assert.equal(checks.overflow, false, `page overflow at ${width}`)
    assert.equal(checks.cards, 15)
    assert.deepEqual(checks.clipped, [], `clipped card content at ${width}`)
    assert(checks.counters.length >= 3)
    await page.getByRole('heading', { name: '超导快讯与最新论文' }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${output}/labels-${width}.png`, fullPage: true })
    await page.getByRole('heading', { name: /^preprint 1-0/ }).click()
    const drawer = page.locator('.MuiDrawer-paper')
    assert.equal(await drawer.locator('[data-testid="news-classification"] .MuiChip-root').count(), 19)
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    results.push({ width, ...checks, drawerLabels: 19 })
  }
  await page.setViewportSize({ width: 1500, height: 1200 })
  await page.getByRole('button', { name: '下一页' }).nth(1).click()
  await page.getByRole('heading', { name: /^preprint 2-0/ }).waitFor()
  assert.equal(await page.getByRole('heading', { name: /^news 1-0/ }).count(), 1)
  assert.equal(await page.getByRole('heading', { name: /^journal_article 1-0/ }).count(), 1)
  await page.evaluate(() => localStorage.setItem('sc-wiki.language', 'en'))
  await page.setViewportSize({ width: 1024, height: 1200 })
  await page.reload()
  await page.getByRole('heading', { name: /^preprint 1-0/ }).waitFor()
  await page.getByRole('heading', { name: /^preprint 1-0/ }).click()
  const englishLabels = await page.locator('.MuiDrawer-paper [data-testid="news-classification"]').innerText()
  assert(englishLabels.includes('Theory and mechanism'))
  assert(englishLabels.includes('Long material family name 17'))
  await page.getByRole('button', { name: 'Close', exact: true }).click()
  await page.screenshot({ path: `${output}/labels-en-1024.png`, fullPage: true })
  results.push({ scenario: 'English labels and family names', fullFamilies: true })
  assert.deepEqual(failures, [])
  await writeFile(`${output}/results.json`, JSON.stringify({ results, independentPagination: true, failures }, null, 2))
  console.log(JSON.stringify({ results, independentPagination: true, failures }))
} finally { await browser.close() }
