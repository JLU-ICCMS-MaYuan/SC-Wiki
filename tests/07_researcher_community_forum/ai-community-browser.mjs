import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE)
const fixture = JSON.parse(await readFile(process.env.COMMUNITY_BROWSER_FIXTURE, 'utf8'))
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const base = process.env.COMMUNITY_BASE_URL, out = process.env.COMMUNITY_ARTIFACT_DIR
const checks = [], errors = []
try {
  for (const [name, identity] of Object.entries(fixture.users)) {
    const context = await browser.newContext({ viewport: { width: 1360, height: 1000 } })
    await context.addInitScript(user => {
      if (user) { localStorage.setItem('auth_token', user.token); localStorage.setItem('auth_user', JSON.stringify(user.user)) }
      if (!localStorage.getItem('sc-wiki.language')) localStorage.setItem('sc-wiki.language', 'zh')
    }, identity)
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
    await page.goto(`${base}/share/discussions`)
    await page.getByRole('heading', { name: 'AI 学术讨论', exact: true }).waitFor()
    if (name !== 'superadmin') {
      assert.equal(await page.getByRole('button', { name: 'AI 随机提问' }).count(), 0)
      assert.equal(await page.getByRole('button', { name: '发起问题' }).count(), 0)
    } else {
      await page.getByRole('button', { name: 'AI 随机提问' }).waitFor()
      await page.getByRole('button', { name: 'AI 随机提问' }).click()
      await page.getByText('生成任务 · 等待生成').first().waitFor()
      checks.push('超级管理员随机提问创建真实后台批次')
    }
    await page.goto(`${base}/share/discussions/${fixture.question_id}`)
    await page.getByRole('heading', { name: fixture.question_title, exact: true }).waitFor()
    await page.getByText('AI 生成', { exact: true }).first().waitFor()
    assert.equal(await page.getByRole('textbox').count(), 0)
    assert.equal(await page.getByRole('button', { name: '举报', exact: true }).count(), 0)
    if (name !== 'superadmin') assert.equal(await page.getByRole('button', { name: '重新生成', exact: true }).count(), 0)
    else {
      await page.getByRole('button', { name: '编辑', exact: true }).first().click()
      await page.getByRole('textbox', { name: '内容' }).fill('浏览器人工修订：保留明确的物理解释与证据边界。')
      await page.getByRole('button', { name: '保存', exact: true }).click()
      await page.getByText('AI 生成，超级管理员修订', { exact: true }).waitFor()
      checks.push('超级管理员通过真实 Go API 修订答案并显示标记')
    }
    await page.screenshot({ path: `${out}/${name}-desktop.png`, fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    assert.equal(overflow, false, `${name}: narrow overflow`)
    await page.screenshot({ path: `${out}/${name}-mobile.png`, fullPage: true })
    await page.evaluate(() => localStorage.setItem('sc-wiki.language', 'en')); await page.reload()
    await page.getByText('AI generated', { exact: true }).first().waitFor()
    checks.push(`${name}: 桌面/窄屏/英文/只读或管理权限通过`)
    await context.close()
  }
  assert.deepEqual(errors, [])
  await writeFile(`${out}/browser.json`, JSON.stringify({ checks, errors }, null, 2))
  console.log(`PASS browser ${checks.length} checks`)
} finally { await browser.close() }
