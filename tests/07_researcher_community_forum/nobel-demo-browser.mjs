import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || '../../prototypes/account-center/node_modules/playwright/index.mjs')
const base = process.env.NOBEL_DEMO_URL || 'http://127.0.0.1:5174/nobel-demo.html'
const output = new URL('../../docs/specs/159-nobel-portrait-exhibition/assets/roster-validation/demo/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const results = {}
const angle = () => page.locator('.nobel-stage').getAttribute('data-angle').then(Number)
const choose = name => page.getByRole('button', { name, exact: true }).click()
async function scanFullTurn(viewportWidth) {
  await page.setViewportSize({ width: viewportWidth, height: 1100 })
  await choose('Onnes')
  await page.locator('.nobel-stage').evaluate(e => e.scrollIntoView({ block: 'start' }))
  const stage = await page.locator('.nobel-stage').boundingBox()
  const startAngle = await angle()
  const x = stage.x + stage.width / 2, y = stage.y + 10
  await page.mouse.move(x, y)
  await page.mouse.down()
  let minGap = Infinity
  // 指针捕获允许越过舞台边界；实际拖动两倍舞台宽度走完360度。
  for (let degrees = 0; degrees <= 360; degrees += 3) {
    await page.mouse.move(x + degrees * Math.max(stage.width, 360) / 180, y)
    const bounds = await page.locator('.nobel-face').evaluateAll(elements => elements
      .filter(e => getComputedStyle(e).visibility === 'visible' && Number(getComputedStyle(e).opacity) > 0)
      .map(e => {
        const rects = [e, e.querySelector('img'), e.querySelector('.nobel-person-copy')].map(node => node.getBoundingClientRect())
        return { left: Math.min(...rects.map(r => r.left)), right: Math.max(...rects.map(r => r.right)) }
      }).sort((a, b) => a.left - b.left))
    for (let i = 1; i < bounds.length; i++) {
      const gap = bounds[i].left - bounds[i - 1].right
      minGap = Math.min(minGap, gap)
      assert.ok(gap >= 12, `${viewportWidth}px / ${degrees}度 图片或文字遮挡: ${gap}`)
    }
  }
  assert.ok(Math.abs(await angle() - startAngle - 360) < 2, '全圈扫描必须实际转过360度')
  await page.mouse.up()
  await choose('Onnes')
  return { width: viewportWidth, samples: 121, minGap }
}
try {
  await page.goto(base)
  const before = await angle()
  await page.waitForTimeout(350)
  assert.ok(await angle() > before)
  const moving = await page.locator('.nobel-face[href$="person=onnes"]').boundingBox()
  await page.mouse.move(moving.x + moving.width / 2, moving.y + 100)
  await page.waitForTimeout(60)
  const frozen = await angle()
  await page.waitForTimeout(300)
  assert.equal(await angle(), frozen)
  await page.mouse.move(0, 0)
  await page.waitForTimeout(250)
  assert.ok(await angle() > frozen)
  results.motion = '自动旋转、真实鼠标悬停暂停、移开恢复通过'

  await choose('Onnes')
  const onnes = page.locator('.nobel-face[href$="person=onnes"]')
  const styles = await onnes.evaluate(e => ({ border: getComputedStyle(e).borderWidth, background: getComputedStyle(document.body).backgroundColor,
    filter: getComputedStyle(e.querySelector('img')).filter, mask: getComputedStyle(e.querySelector('img')).maskImage,
    image: e.querySelector('img').getAttribute('src'), headings: e.querySelectorAll('h2').length }))
  assert.equal(styles.border, '0px'); assert.equal(styles.background, 'rgb(255, 255, 255)')
  assert.equal(styles.filter, 'none'); assert.ok(styles.mask.includes('gradient'))
  assert.ok(styles.image.includes('/original/')); assert.equal(styles.headings, 1)
  assert.equal(await page.locator('.nobel-caption').count(), 0)
  assert.ok(Number(await onnes.getAttribute('data-scale')) > Number(await page.locator('.nobel-face[href$="person=cooper"]').getAttribute('data-scale')))
  await page.screenshot({ path: new URL('desktop.png', output).pathname, fullPage: true })
  results.visual = '白底、原照、无相框和滤镜、白色边缘融合；姓名资料在各自移动容器内；主位大于侧位'
  results.fullTurnSpacing = [await scanFullTurn(1440), await scanFullTurn(768), await scanFullTurn(390)]
  await page.setViewportSize({ width: 1440, height: 1100 })
  await choose('Onnes')

  let popups = 0
  page.on('popup', () => popups++)
  const rect = await onnes.boundingBox()
  const start = await angle()
  await page.mouse.move(rect.x + rect.width / 2, rect.y + 100)
  await page.mouse.down()
  await page.mouse.move(rect.x + rect.width / 2 + 140, rect.y + 100, { steps: 12 })
  await page.mouse.up()
  await page.waitForTimeout(100)
  assert.ok(await angle() > start)
  assert.equal(popups, 0)
  const movedTitle = await onnes.locator('h2').boundingBox()
  // 照片内部侧倾产生透视偏移；姓名应跟随照片所在的容器中心。
  const movedPhoto = await onnes.locator('.nobel-photo').boundingBox()
  assert.ok(Math.abs(movedTitle.x + movedTitle.width / 2 - movedPhoto.x - movedPhoto.width / 2) < 2)
  const stage = await page.locator('.nobel-stage').boundingBox()
  const afterRight = await angle()
  await page.mouse.move(stage.x + stage.width / 2, stage.y + 10)
  await page.mouse.down()
  await page.mouse.move(stage.x + stage.width / 2 - 160, stage.y + 10, { steps: 12 })
  await page.mouse.up()
  assert.ok(await angle() < afterRight)
  await page.mouse.move(0, 0)
  const released = await angle()
  await page.waitForTimeout(300)
  assert.ok(await angle() < released)
  results.drag = '头像按住右拖/背景左拖角度相反；释放沿最后方向自转；拖动不误开标签页；姓名跟随照片'

  await choose('Onnes')
  await onnes.evaluate(e => e.scrollIntoView({ block: 'center' }))
  const clickRect = await onnes.boundingBox()
  await page.mouse.move(clickRect.x + clickRect.width / 2, clickRect.y + 100)
  await page.waitForTimeout(60)
  const [popup] = await Promise.all([page.waitForEvent('popup'), onnes.click()])
  await popup.waitForLoadState()
  assert.equal(new URL(popup.url()).searchParams.get('person'), 'onnes')
  assert.equal(await popup.evaluate(() => window.opener === null), true)
  assert.equal(new URL(page.url()).searchParams.has('person'), false)
  await popup.close()
  results.popup = '普通点击仍打开独立标签页，opener为空'
  const hrefs = await page.locator('.nobel-face').evaluateAll(es => es.map(e => e.href))
  assert.equal(hrefs.length, 11)
  for (const url of hrefs) {
    await page.goto(url)
    await page.locator('.nobel-detail-portrait img').evaluate(img => img.decode())
    assert.ok((await page.locator('.nobel-detail-portrait img').getAttribute('src')).includes('/original/'))
    assert.equal(await page.locator('.nobel-biography section').count(), 4)
    for (const href of await page.locator('.nobel-citations a').evaluateAll(es => es.map(e => e.getAttribute('href')))) assert.equal(await page.locator(href).count(), 1)
  }
  await page.screenshot({ path: new URL('detail.png', output).pathname, fullPage: true })
  results.details = '11个详情页原照与段落引用锚点正常'

  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(base)
  const reducedAngle = await angle()
  await page.waitForTimeout(200)
  assert.equal(await angle(), reducedAngle)
  for (const name of ['Onnes','Bardeen','Cooper','Schrieffer','Giaever','Josephson','Bednorz','Müller','Abrikosov','Ginzburg','Leggett']) {
    await choose(name)
    const r = await page.locator('.nobel-face.is-selected').boundingBox()
    assert.ok(r && r.x >= 0 && r.x + r.width <= 390)
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: new URL('mobile.png', output).pathname, fullPage: true })
  await choose('Onnes')
  await page.locator('.nobel-face').first().focus()
  await page.keyboard.press('Tab')
  assert.ok((await page.locator('.nobel-face.is-selected').textContent()).includes('Bardeen'))
  results.accessibility = '390px无横向溢出；减少动态关闭自转；11人索引与键盘聚焦可用'

  const touch = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce' })
  await touch.goto(base)
  const cdp = await touch.context().newCDPSession(touch)
  const touchAngle = () => touch.locator('.nobel-stage').getAttribute('data-angle').then(Number)
  const r = await touch.locator('.nobel-stage').boundingBox()
  const y = r.y + 100
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 190, y }] })
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 270, y }] })
  await touch.waitForTimeout(60)
  const right = await touchAngle()
  assert.ok(right > 0)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 100, y }] })
  await touch.waitForTimeout(60)
  assert.ok(await touchAngle() < right)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] })
  assert.equal(await touch.locator('.nobel-stage').getAttribute('data-dragging'), 'false')
  await touch.getByRole('button', { name: 'Onnes', exact: true }).click()
  assert.equal(await touchAngle(), 0)
  await touch.close()
  results.touch = '真实触屏事件左右拖动、取消手势后恢复索引操作通过'
  assert.deepEqual(errors, [])
  await writeFile(new URL('browser.json', output), JSON.stringify({ date: '2026-10-23', base, results, errors }, null, 2) + '\n')
  console.log(results)
} finally { await browser.close() }
