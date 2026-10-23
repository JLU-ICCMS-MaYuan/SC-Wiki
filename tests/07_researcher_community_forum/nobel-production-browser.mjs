import assert from 'node:assert/strict'
import {mkdir, writeFile, readFile} from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || '../../prototypes/account-center/node_modules/playwright/index.mjs')
const base = process.env.NOBEL_SITE_URL || 'http://127.0.0.1:5174'
const output = new URL('../../docs/specs/159-nobel-portrait-exhibition/assets/fixed-divider-validation/production/', import.meta.url)
await mkdir(output, {recursive: true})
const browser = await chromium.launch({channel:'chrome', headless:true})
const page = await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'})
const pageErrors = []
const apiStatuses = []
page.on('pageerror', e => pageErrors.push(e.message))
page.on('response', r => { if (new URL(r.url()).pathname.startsWith('/api/news')) apiStatuses.push(r.status()) })
const results = {}
const facts = JSON.parse(await readFile(new URL('../../docs/specs/159-nobel-portrait-exhibition/assets/award-facts.json', import.meta.url)))
try {
  await page.goto(`${base}/news`)
  await page.getByRole('button',{name:'Giaever',exact:true}).click()
  const root = page.locator('.nobel-feature')
  const giaever = root.locator('.nobel-face[href="/nobel/giaever"]')
  assert.ok((await giaever.locator('.nobel-person-achievement').innerText()).includes('超导体中的电子隧穿'))
  assert.equal(await giaever.locator('.nobel-person-coaward').innerText(), '与江崎玲于奈、布赖恩·约瑟夫森共同获颁 1973 年诺贝尔物理学奖。')
  assert.equal(await root.locator('.nobel-brand').count(),0)
  assert.equal(await page.getByRole('heading',{level:1}).count(),1)
  assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(248, 250, 252)')
  assert.equal(await root.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 255, 255)')
  await root.screenshot({path:new URL('news-zh.png',output).pathname})
  assert.equal(await root.locator('.nobel-face[href="/nobel/esaki"]').count(),0)
  assert.equal(await page.getByRole('button',{name:'Esaki',exact:true}).count(),0)
  assert.equal(await page.getByRole('button',{name:'Josephson',exact:true}).count(),1)
  assert.equal(await page.getByRole('button',{name:'Leggett',exact:true}).count(),1)
  const hrefs = await root.locator('.nobel-face').evaluateAll(es => es.map(e => e.href))
  assert.equal(hrefs.length,11)
  assert.ok(hrefs.every(url=>new URL(url).pathname.startsWith('/nobel/')))
  const [popup] = await Promise.all([page.waitForEvent('popup'), giaever.click()])
  await popup.waitForLoadState()
  assert.equal(new URL(popup.url()).pathname,'/nobel/giaever')
  assert.equal(await popup.evaluate(()=>window.opener===null),true)
  assert.equal(await popup.locator('.nobel-biography strong').innerText(),'1/4')
  await popup.reload()
  await popup.getByRole('heading',{name:'伊瓦尔·贾埃弗',level:1}).waitFor()
  await popup.locator('.nobel-feature').screenshot({path:new URL('giaever-detail-zh.png',output).pathname})
  await popup.close()
  results.routing='真实/news入口、新标签页、空opener及正式详情刷新通过'
  results.styles='沿用站点浅灰body和白色展陈，不增加重复品牌或h1，CSS未覆盖全局背景'
  await page.getByRole('button',{name:'切换为英文',exact:true}).click()
  assert.equal(/[\u3400-\u9fff]/.test(await root.textContent()),false)
  assert.ok((await giaever.locator('.nobel-person-coaward').innerText()).includes('with Leo Esaki and Brian Josephson'))
  await root.screenshot({path:new URL('news-en.png',output).pathname})
  for (const href of hrefs) {
    await page.goto(href)
    await page.locator('.nobel-detail-portrait img').evaluate(img=>img.decode())
    const id=new URL(href).pathname.split('/').pop()
    const fact=facts.find(f=>f.id===(id==='mueller'?'muller':id))
    assert.equal(await page.locator('.nobel-biography strong').innerText(),fact.share)
    assert.equal(/[\u3400-\u9fff]/.test(await page.locator('.nobel-feature').textContent()),false)
    for(const href of await page.locator('.nobel-citations a').evaluateAll(es=>es.map(e=>e.getAttribute('href')))) assert.equal(await page.locator(href).count(),1)
  }
  results.content='11位正式详情、原照解码、官方份额比对、英文内容及引用锚点通过；共享奖项不改写个人成果'
  await page.goto(`${base}/nobel/esaki`)
  await page.getByRole('heading',{name:'Laureate not found'}).waitFor()
  assert.equal(await page.locator('.nobel-biography').count(),0)
  await page.goto(`${base}/nobel/unknown`)
  await page.getByRole('heading',{name:'Laureate not found'}).waitFor()
  assert.equal(await page.locator('.nobel-biography').count(),0)
  await page.goto(`${base}/news`)
  await page.getByRole('button',{name:'Switch to Simplified Chinese',exact:true}).click()
  await page.setViewportSize({width:390,height:844})
  const names=['Onnes','Bardeen','Cooper','Schrieffer','Giaever','Josephson','Bednorz','Müller','Abrikosov','Ginzburg','Leggett']
  for(const name of names){
    await page.getByRole('button',{name,exact:true}).click()
    const stage=await page.locator('.nobel-stage').boundingBox()
    const face=await page.locator('.nobel-face.is-selected').boundingBox()
    assert.ok(face.y+face.height <= stage.y+stage.height+1,`${name}文字不被舞台裁掉`)
    assert.ok(face.x>=0 && face.x+face.width<=390)
  }
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.getByRole('button',{name:'Giaever',exact:true}).click()
  await root.screenshot({path:new URL('news-mobile.png',output).pathname})
  results.mobile='390px正式侧栏布局下11个人物和新增共享说明完整，无文字裁切及页面横向溢出'
  // 验证样式随路由加载后不会污染资讯之外的页面。
  await page.goto(`${base}/search`)
  await page.waitForSelector('main')
  assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(248, 250, 252)')
  assert.deepEqual(pageErrors,[])
  await writeFile(new URL('browser.json',output), JSON.stringify({base,results,pageErrors,apiStatuses},null,2)+'\n')
  console.log(results)
} finally {await browser.close()}
