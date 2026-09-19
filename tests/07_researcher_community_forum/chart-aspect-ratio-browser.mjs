// Issue #111：使用真实页面与布局引擎，API 全部隔离，不写业务数据。
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = process.env.FRONTEND_URL || 'http://127.0.0.1:5191'
const artifacts = process.env.ARTIFACT_DIR || '/tmp/scwiki-111-artifacts'
await mkdir(artifacts, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(() => localStorage.setItem('sc-wiki.language', 'zh'))
const page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [], requests = [], measurements = []
page.on('pageerror', error => errors.push(error.message))
const families = [
  ['氢基超导体', 'Hydride'], ['铜基超导体', 'Cuprate'], ['铁基超导体', 'Iron-based'],
  ['镍基超导体', 'Nickelate'], ['无机硼碳氮基超导体', 'Inorganic boron-carbon-nitrogen'],
  ['有机超导体', 'Organic'], ['重费米子超导体', 'Heavy fermion'], ['单质超导体', 'Elemental'],
  ['用于验证窄屏图例换行的自定义超导材料家族', 'Custom superconducting material family with a long name'],
].map(([name, name_en], index) => ({ id: index + 1, name, name_zh: name, name_en }))
const point = { x: 120, y: 220, formula: 'Fixture-H', family_id: 1, family_ids: [1], type: 'experimental', year: 2000, paper_id: 99111 }
let empty = false
await context.route('**/api/**', async route => {
  const request = route.request(), url = new URL(request.url()), pathname = url.pathname
  requests.push({ method: request.method(), pathname })
  const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  if (pathname === '/api/classification-catalogs') return json({ material_families: families, structure_families: [], material_dimensionalities: [] })
  if (pathname.startsWith('/api/papers/stats/tc-')) {
    const field = url.searchParams.get('tc_field')
    if (field === 'mcmillan_tc') return json({ error: '隔离错误场景' }, 503)
    if (empty || field === 'anisotropic_eliashberg_tc') return json([])
    return json([{ ...point, x: pathname.endsWith('tc-year') ? 2000 : point.x }])
  }
  if (pathname === '/api/papers/99111') return json({ id: 99111, title: 'Issue 111 隔离论文', year: 2000, authors: [], key_properties: [], material_states: [] })
  return json({ items: [], total: 0 })
})

async function measure(label) {
  await page.waitForFunction(() => document.querySelectorAll('.recharts-cartesian-grid').length === 2)
  // 等待 ResizeObserver 和 React 完成本轮布局，不替换尺寸读取。
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  const result = await page.evaluate(() => {
    const rect = node => {
      const { x, y, width, height, bottom, right } = node.getBoundingClientRect()
      return { x, y, width, height, bottom, right }
    }
    const containers = [...document.querySelectorAll('.recharts-responsive-container')]
    const outOfBounds = [], overlappingTicks = []
    for (const container of containers) {
      const frame = rect(container)
      for (const text of container.querySelectorAll('.recharts-cartesian-axis text, .recharts-reference-line text')) {
        const box = rect(text)
        if (box.x < frame.x - 1 || box.right > frame.right + 1 || box.y < frame.y - 1 || box.bottom > frame.bottom + 1) {
          outOfBounds.push(text.textContent)
        }
      }
      const grid = rect(container.querySelector('.recharts-cartesian-grid'))
      for (const text of container.querySelectorAll('.recharts-reference-line text')) {
        if (rect(text).x < grid.x - 1) outOfBounds.push(`参考线标注越过纵轴: ${text.textContent}`)
      }
      for (const axis of container.querySelectorAll('.recharts-cartesian-axis')) {
        const ticks = [...axis.querySelectorAll('.recharts-cartesian-axis-tick-value')]
        for (let i = 1; i < ticks.length; i++) {
          const a = rect(ticks[i - 1]), b = rect(ticks[i])
          if (Math.min(a.right, b.right) > Math.max(a.x, b.x) && Math.min(a.bottom, b.bottom) > Math.max(a.y, b.y)) {
            overlappingTicks.push(`${ticks[i - 1].textContent}/${ticks[i].textContent}`)
          }
        }
      }
    }
    const clippedControls = [...document.querySelectorAll('main [role="combobox"], main [aria-pressed]')].filter(node => {
      const box = rect(node), card = node.closest('.MuiCard-root')
      if (!card) return false
      const bounds = rect(card)
      if (box.x < bounds.x || box.right > bounds.right + 1 || box.bottom > bounds.bottom + 1) return true
      for (let parent = node.parentElement; parent && parent !== card; parent = parent.parentElement) {
        if (['hidden', 'clip'].includes(getComputedStyle(parent).overflowY) && box.bottom > rect(parent).bottom + 1) return true
      }
      return false
    }).map(node => node.textContent)
    return { charts: containers.map(rect), grids: [...document.querySelectorAll('.recharts-cartesian-grid')].map(rect),
      overflow: document.documentElement.scrollWidth > window.innerWidth, outOfBounds, overlappingTicks, clippedControls }
  })
  for (const box of result.charts) assert.ok(Math.abs(box.height - box.width * 3 / 4) <= 1, `${label}: 期望 4:3，实际 ${box.width}×${box.height}`)
  const [left, right] = result.charts
  if (page.viewportSize().width >= 1200) {
    for (const key of ['y', 'bottom', 'width', 'height']) assert.ok(Math.abs(left[key] - right[key]) <= 1, `${label}: 两图 ${key} 不对齐`)
    for (const key of ['y', 'bottom']) assert.ok(Math.abs(result.grids[0][key] - result.grids[1][key]) <= 1, `${label}: 坐标网格 ${key} 不对齐`)
  } else assert.ok(right.y >= left.bottom, `${label}: 窄屏应单列`)
  assert.equal(result.overflow, false, `${label}: 页面横向溢出`)
  assert.deepEqual(result.outOfBounds, [], `${label}: 坐标或参考线文字裁切`)
  assert.deepEqual(result.overlappingTicks, [], `${label}: 坐标刻度重叠`)
  assert.deepEqual(result.clippedControls, [], `${label}: 控件或图例裁切`)
  measurements.push({ label, ...result })
  console.log(`通过 ${label}`)
  return result
}

try {
  for (const lang of ['zh', 'en']) {
    for (const width of [375, 768, 1440, 1920, 2560]) {
      await page.setViewportSize({ width, height: 1000 })
      await page.goto(`${origin}/share/charts`)
      await page.locator('.recharts-cartesian-grid').first().waitFor()
      // 每次导航从中文开始，再通过真实界面切换语言。
      if (lang === 'en') {
        const languageButton = page.getByRole('button', { name: '切换为英文', exact: true })
        if (await languageButton.count()) await languageButton.click()
        else {
          await page.getByRole('button', { name: '界面语言', exact: true }).click()
          await page.getByRole('menuitem', { name: '切换为英文', exact: true }).click()
        }
      }
      await measure(`${lang}-${width}`)
      await page.screenshot({ path: path.join(artifacts, `${lang}-${width}.png`), fullPage: true })
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${origin}/share/charts`)
  for (const width of [1199, 1200, 1920, 2560, 768, 375, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await measure(`resize-${width}`)
  }
  await measure('desktop-expanded')
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await measure('desktop-collapsed')
  await page.getByRole('button', { name: '展开侧栏', exact: true }).click()
  await measure('desktop-restored')

  const tc = page.getByRole('combobox', { name: 'Tc 字段', exact: true }).first()
  await tc.click()
  await page.getByRole('option', { name: 'Anisotropic Eliashberg Tc', exact: true }).click()
  await page.getByText('当前 Tc 字段暂无可公开数据点', { exact: true }).waitFor()
  await measure('different-fields-empty-pressure')
  await tc.click()
  await page.getByRole('option', { name: 'McMillan Tc', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(await page.locator('.recharts-responsive-container').count(), 1, '单图失败不影响另一张图')
  await tc.click()
  await page.getByRole('option', { name: 'Experimental Tc', exact: true }).click()
  await measure('error-recovered')

  await page.getByRole('combobox', { name: '材料家族', exact: true }).first().click()
  await page.getByRole('option', { name: '氢基超导体' }).click()
  await page.keyboard.press('Escape')
  await measure('family-filtered')
  await page.locator('main [role="button"][aria-pressed="false"]').first().click()
  await measure('family-restored')
  // 等值线也创建 Scatter，但使用空的 g；只定位真正数据点的可见路径。
  const symbol = page.locator('.recharts-scatter-symbol path').first()
  await symbol.hover()
  await page.locator('.recharts-tooltip-wrapper').filter({ hasText: 'Fixture-H' }).first().waitFor({ state: 'visible' })
  await symbol.click()
  await page.getByText('Issue 111 隔离论文', { exact: true }).waitFor()

  empty = true
  await page.goto(`${origin}/share/charts`)
  await measure('both-empty')
  await page.setViewportSize({ width: 375, height: 1000 })
  await measure('mobile-empty')
  assert.equal(await page.getByText('当前 Tc 字段暂无可公开数据点', { exact: true }).count(), 2)
  assert.equal(await page.getByText('室温 300 K', { exact: true }).count(), 2)
  assert.equal(await page.getByText('液氮 77 K', { exact: true }).count(), 2)
  assert.ok(await page.locator('polygon').count() >= 6, '压力背景仍存在')
  assert.equal(await page.locator('rect[fill="url(#tc-temperature-gradient)"]').count(), 1)
  assert.deepEqual(errors, [], '无浏览器异常')
  assert.ok(requests.every(request => request.method === 'GET'), '验收不应写 API')
  await writeFile(path.join(artifacts, 'results.json'), JSON.stringify({ measurements, errors, requests }, null, 2))
  console.log(JSON.stringify({ passed: measurements.length, artifacts }))
} catch (error) {
  await page.screenshot({ path: path.join(artifacts, 'failure.png'), fullPage: true })
  throw error
} finally {
  await browser.close()
}
