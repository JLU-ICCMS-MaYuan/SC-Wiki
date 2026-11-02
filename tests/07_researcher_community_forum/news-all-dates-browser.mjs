// 真实Go列表+SQLite固定数据，覆盖跨周/月/年和无日期条目的连续浏览。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output = process.env.NEWS_BROWSER_OUTPUT || '/tmp/news153-all-browser'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const context = await browser.newContext({ viewport: { width: 1500, height: 1100 } })
await context.addInitScript(() => localStorage.setItem('sc-wiki.language', 'zh'))
const requests = [], errors = []
await context.route('**/api/**', async route => {
  const url = new URL(route.request().url())
  if (url.pathname === '/api/news/feed') {
    assert(!url.searchParams.has('week') && !url.searchParams.has('period'))
    requests.push({ kind: url.searchParams.get('kind'), page: url.searchParams.get('page'), size: url.searchParams.get('page_size') })
    const response = await context.request.get((process.env.NEWS_BROWSER_API || 'http://127.0.0.1:8187') + url.pathname + url.search)
    assert.equal(response.status(), 200)
    return route.fulfill({ json: await response.json() })
  }
  return route.fulfill({ json: url.pathname === '/api/news' ? [] : {} })
})
const page = await context.newPage()
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5187') + '/news')
  const feed = page.locator('[aria-labelledby="news-feed-heading"]')
  const preprints = page.locator('section[aria-label="预印本"]')
  await preprints.getByRole('heading', { name: 'preprint fixture 0', exact: true }).waitFor()
  assert(!/本周|历史更多|返回本周/.test(await feed.innerText()))
  assert.equal(await preprints.locator('h4').count(), 5)
  assert(await preprints.innerText().then(text => text.includes('2026-11-01') && text.includes('2026-10（仅提供月份）')))
  assert(await preprints.getByTestId('news-classification').count() === 5)
  await preprints.getByRole('button', { name: '下一页', exact: true }).click()
  await preprints.getByRole('heading', { name: 'preprint fixture 5', exact: true }).waitFor()
  assert.equal(await preprints.locator('h4').count(), 2)
  assert((await preprints.innerText()).includes('2025 年'))
  assert((await preprints.innerText()).includes('日期未提供'))
  assert(await preprints.getByRole('button', { name: '下一页', exact: true }).isDisabled())
  assert.equal(await page.getByRole('heading', { name: 'news fixture 0', exact: true }).count(), 1)
  assert.equal(await page.getByRole('heading', { name: 'journal_article fixture 0', exact: true }).count(), 1)
  await preprints.getByRole('button', { name: '上一页', exact: true }).click()
  await preprints.getByRole('heading', { name: 'preprint fixture 0', exact: true }).waitFor()
  await preprints.getByRole('heading', { name: 'preprint fixture 0', exact: true }).click()
  assert.equal(await page.locator('.MuiDrawer-paper').getByRole('link').count(), 1)
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.locator('.MuiDrawer-paper').waitFor({ state: 'hidden' })
  await feed.screenshot({ path: output + '/desktop.png' })
  await page.setViewportSize({ width: 390, height: 900 })
  await page.waitForTimeout(400)
  assert(await feed.evaluate(node => node.scrollWidth <= node.clientWidth))
  await feed.screenshot({ path: output + '/mobile.png' })
  assert.deepEqual(errors, [])
  const result = { passed: true, independentPagination: true, allDatePrecisions: true, noWeekNavigation: true, labelsAndDetail: true, mobileFeedOverflow: false, requests, errors }
  await writeFile(output + '/results.json', JSON.stringify(result, null, 2))
  console.log(result)
} finally { await browser.close() }
