// 真实 Go + MySQL + Redis 验收；账号和论文仅来自一次性隔离夹具。
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.COMMUNITY_BASE_URL
const fixture = JSON.parse(await readFile(process.env.COMMUNITY_BROWSER_FIXTURE, 'utf8'))
const artifacts = process.env.COMMUNITY_ARTIFACT_DIR
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
const errors = [], checks = [], retiredRequests = []
const check = name => { checks.push(name); console.log(`PASS ${name}`) }
try {
  const pages = []
  for (const identity of fixture.users) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } })
    await context.addInitScript(identity => {
      localStorage.setItem('auth_token', identity.token)
      localStorage.setItem('auth_user', JSON.stringify(identity.user))
      localStorage.setItem('sc-wiki.language', 'zh')
    }, identity)
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    page.on('request', request => { if (request.url().includes('danmaku')) retiredRequests.push(request.url()) })
    pages.push(page)
  }
  const [alice, bob, moderator] = pages
  const commentsOnly = async page => {
    await page.getByRole('textbox', { name: /评论|Comment/ }).waitFor()
    assert.equal(await page.getByRole('textbox').count(), 1, 'detail should have one comment composer')
    assert.equal(await page.getByTestId('danmaku-stage').count(), 0)
    assert.equal(await page.getByRole('switch', { name: /显示弹幕|Show messages/ }).count(), 0)
    assert.equal(await page.getByRole('button', { name: /历史弹幕|Message history/ }).count(), 0)
  }
  const createFrom = async (page, textbox, content) => {
    await textbox.fill(content)
    const response = page.waitForResponse(r => r.url() === `${base}/api/community/entries` && r.request().method() === 'POST')
    await textbox.locator('xpath=ancestor::form').getByRole('button', { name: '发布', exact: true }).click()
    const result = await response
    assert.equal(result.status(), 201, await result.text())
    return result.json()
  }
  const api = async (index, method, resource, body) => {
    const response = await pages[index].request.fetch(base + '/api/community' + resource, { method, headers: { Authorization: `Bearer ${fixture.users[index].token}` }, ...(body ? { data: body } : {}) })
    assert.ok(response.ok(), `${method} ${resource}: ${response.status()} ${await response.text()}`)
    return response.status() === 204 ? null : response.json()
  }

  await alice.goto(base + '/share/discussions')
  await alice.getByRole('heading', { name: '讨论', exact: true }).waitFor()
  assert.equal(await alice.getByRole('button', { name: '排行榜', exact: true }).count(), 1)
  assert.equal(await alice.getByRole('button', { name: 'Tc~X 演变', exact: true }).count(), 1)
  await alice.getByRole('button', { name: '发起问题', exact: true }).click()
  await alice.getByRole('textbox', { name: /问题标题/ }).fill('Hg 体系如何理解临界温度？')
  const question = await createFrom(alice, alice.getByRole('textbox', { name: /问题补充/ }), '讨论 **实验条件** 与 $T_c$ 的关系。')
  await alice.waitForURL(`**/share/discussions/${question.id}`)
  await bob.goto(base + `/share/discussions/${question.id}`)
  const answer = await createFrom(bob, bob.getByRole('textbox', { name: /内容/ }).first(), '需要同时考虑 **压强** 和测量条件。$T_c=4.2\,K$')
  await alice.reload()
  const answerCard = alice.locator(`#entry-${answer.id}`)
  await alice.getByRole('textbox', { name: /内容/ }).first().fill('点赞后仍应保留的答案草稿')
  await answerCard.getByRole('textbox', { name: /评论/ }).fill('点赞后仍应保留的评论草稿')
  await answerCard.getByRole('button', { name: /^赞同/ }).click()
  await alice.locator(`#entry-${answer.id}`).getByRole('button', { name: /已赞同 1/ }).waitFor()
  assert.equal(await alice.getByRole('textbox', { name: /内容/ }).first().inputValue(), '点赞后仍应保留的答案草稿')
  assert.equal(await answerCard.getByRole('textbox', { name: /评论/ }).inputValue(), '点赞后仍应保留的评论草稿')
  check('voting preserves unfinished answer and comment drafts')
  const comment = await createFrom(alice, alice.locator(`#entry-${answer.id}`).getByRole('textbox', { name: /评论/ }), '请补充实验条件，谢谢。')
  await bob.reload()
  await bob.locator(`#entry-${comment.id}`).getByRole('button', { name: '回复', exact: true }).click()
  const reply = await createFrom(bob, bob.getByRole('textbox', { name: new RegExp(`回复 #${comment.id}`) }), '这里指常压下的实验结果。')
  check('question, answer, vote, answer comment and reply through the UI')

  await alice.goto(base + '/account/notifications')
  await alice.getByText('回复了你的评论', { exact: false }).waitFor()
  await alice.getByRole('button', { name: '查看内容', exact: true }).first().click()
  await alice.waitForURL(`**focus=${reply.id}#entry-${reply.id}`)
  await alice.locator(`#entry-${reply.id}`).getByText('这里指常压下的实验结果。', { exact: true }).waitFor()
  await alice.screenshot({ path: path.join(artifacts, 'discussion-desktop.png'), fullPage: true })
  check('notification opens and locates the actual reply')

  await alice.goto(base + '/search?elements=Hg&mode=elements_exact_search')
  await alice.getByRole('link', { name: 'Hg 体系讨论' }).click()
  await alice.getByRole('heading', { name: 'Hg 体系', exact: true }).waitFor()
  const systemComment = await createFrom(alice, alice.getByRole('textbox', { name: /评论/ }), 'Hg 体系共享评论验收。')
  await bob.goto(base + '/systems/Hg')
  await bob.getByText(systemComment.body, { exact: true }).waitFor()
  await commentsOnly(alice)
  await commentsOnly(bob)
  await bob.locator(`#entry-${systemComment.id}`).getByRole('button', { name: '回复', exact: true }).click()
  const systemReply = await createFrom(bob, bob.getByRole('textbox', { name: new RegExp(`回复 #${systemComment.id}`) }), '体系评论可以继续回复。')
  await alice.reload()
  await alice.getByText(systemReply.body, { exact: true }).waitFor()
  await alice.screenshot({ path: path.join(artifacts, 'system-desktop.png'), fullPage: true })
  check('periodic search and shared system comments with replies, without scrolling messages')

  await api(1, 'POST', `/entries/${systemComment.id}/reports`, { reason: '隔离浏览器举报测试' })
  await moderator.goto(base + '/admin/community')
  await moderator.getByText('隔离浏览器举报测试', { exact: true }).waitFor()
  await moderator.getByRole('button', { name: '隐藏内容', exact: true }).click()
  await moderator.getByRole('textbox', { name: '处置原因（至少 5 个字）' }).fill('确认隐藏此条测试评论')
  await moderator.getByRole('button', { name: '保存', exact: true }).click()
  await moderator.getByText('还没有内容，欢迎发起交流。').waitFor()
  await bob.reload()
  await bob.locator(`#entry-${systemComment.id}`).getByText('这条内容已被管理员隐藏', { exact: true }).waitFor()
  assert.equal(await bob.getByText(systemComment.body, { exact: true }).count(), 0)
  await bob.getByText(systemReply.body, { exact: true }).waitFor()
  check('report moderation hides a comment while preserving its existing replies')

  await alice.goto(base + `/papers/${fixture.paper_id}`)
  await alice.getByRole('heading', { name: '论文交流', exact: true }).waitFor()
  await commentsOnly(alice)
  const paperComment = await createFrom(alice, alice.getByRole('textbox', { name: /评论/ }), '只属于这篇论文的评论。')
  await bob.goto(base + `/search?paper_id=${fixture.paper_id}`)
  await bob.getByText(paperComment.body, { exact: true }).waitFor()
  await commentsOnly(bob)
  assert.equal(await bob.getByText(systemComment.body, { exact: true }).count(), 0)
  check('standalone and search paper details share comments without mixing system comments')

  // 仅为既有科学图表提供点数据；论文详情与社区读写仍连接真实 Go/MySQL。
  await bob.route('**/api/papers/stats/tc-*', route => route.fulfill({ json: [{ x: 1, y: 4.2, label: 'Hg', family_id: 0, family_ids: [0], type: 'experimental', year: 2026, paper_id: fixture.paper_id }] }))
  await bob.goto(base + '/share/charts')
  const point = bob.locator('.recharts-scatter-symbol:visible').first()
  await point.hover()
  await point.click()
  await bob.getByRole('heading', { name: '论文交流', exact: true }).waitFor()
  await bob.getByText(paperComment.body, { exact: true }).waitFor()
  await commentsOnly(bob)
  check('chart drawer reads the same paper comment as the other two entry points')

  await alice.goto(base + '/share/rankings')
  await alice.getByRole('heading', { name: '排行榜', exact: true }).waitFor()
  await alice.goto(base + '/share/charts')
  await alice.getByRole('heading', { name: 'Tc~X 演变', exact: true }).waitFor()
  await alice.setViewportSize({ width: 390, height: 844 })
  await alice.goto(base + '/share/discussions')
  await alice.getByRole('button', { name: '社区', exact: true }).click()
  await alice.getByRole('menuitem', { name: '讨论', exact: true }).click()
  await alice.getByRole('heading', { name: '讨论', exact: true }).waitFor()
  assert.ok(await alice.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'mobile content overflows')
  await alice.screenshot({ path: path.join(artifacts, 'discussion-mobile.png'), fullPage: true })
  check('rankings, charts and collapsed mobile community navigation')

  // 请求失败后草稿保留；恢复联网后仍能提交，使用真实服务而非模拟成功响应。
  await alice.goto(base + '/systems/Hg')
  await alice.getByRole('textbox', { name: /评论/ }).fill('断网恢复后提交的评论')
  await alice.context().setOffline(true)
  await alice.getByRole('textbox', { name: /评论/ }).locator('xpath=ancestor::form').getByRole('button', { name: '发布', exact: true }).click()
  await alice.getByText('操作失败，请稍后重试。').waitFor()
  assert.equal(await alice.getByRole('textbox', { name: /评论/ }).inputValue(), '断网恢复后提交的评论')
  await alice.context().setOffline(false)
  await createFrom(alice, alice.getByRole('textbox', { name: /评论/ }), '断网恢复后提交的评论')
  check('network failure preserves draft and allows retry')

  await bob.setViewportSize({ width: 1280, height: 900 })
  await bob.goto(base + '/systems/Hg')
  await bob.getByRole('button', { name: '切换为英文' }).click()
  await bob.getByRole('heading', { name: 'Hg system', exact: true }).waitFor()
  await commentsOnly(bob)
  await bob.keyboard.press('Tab')
  assert.ok(await bob.evaluate(() => document.activeElement !== document.body), 'keyboard focus was lost')
  check('English interface and keyboard focus with comments only')
  assert.deepEqual(retiredRequests, [], 'retired scrolling message requests must stop')
  assert.deepEqual(errors, [])
  await writeFile(path.join(artifacts, 'browser-results.json'), JSON.stringify({ checks, errors, retiredRequests }, null, 2))
} finally {
  await browser.close()
}
