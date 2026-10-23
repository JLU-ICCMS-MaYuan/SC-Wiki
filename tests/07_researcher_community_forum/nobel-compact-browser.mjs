import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || '../../prototypes/account-center/node_modules/playwright/index.mjs')
const base=process.env.NOBEL_SITE_URL || 'http://127.0.0.1:5173'
const out=new URL('../../docs/specs/159-nobel-portrait-exhibition/assets/roster-validation/compact/',import.meta.url)
await mkdir(out,{recursive:true})
const b=await chromium.launch({channel:'chrome'})
const p=await b.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'})
const errors=[];p.on('pageerror',e=>errors.push(e.message))
const metrics=[]
async function scan(lang,width) {
  await p.setViewportSize({width,height:1100})
  await p.goto(`${base}/nobel-demo.html?lang=${lang}`)
  await p.getByRole('button',{name:'Onnes',exact:true}).click()
  await p.locator('.nobel-stage').evaluate(e=>e.scrollIntoView({block:'start'}))
  const stage=await p.locator('.nobel-stage').boundingBox()
  const x=stage.x+stage.width/2,y=stage.y+20
  const start=Number(await p.locator('.nobel-stage').getAttribute('data-angle'))
  await p.mouse.move(x,y);await p.mouse.down()
  let minGap=Infinity,maxGap=0,minSpacing=Infinity
  for(let deg=0;deg<=360;deg+=3){
    await p.mouse.move(x+deg*Math.max(stage.width,360)/180,y)
    const snapshot=await p.evaluate(()=>{
      const cards=[...document.querySelectorAll('.nobel-face')].filter(e=>getComputedStyle(e).visibility==='visible').map(e=>e.getBoundingClientRect())
      const index=document.querySelector('.nobel-person-index').getBoundingClientRect()
      const ordered=cards.sort((a,b)=>a.x-b.x)
      return {gap:index.top-Math.max(...cards.map(r=>r.bottom)),spacing:Math.min(...ordered.slice(1).map((r,i)=>r.left-ordered[i].right))}
    })
    assert.ok(snapshot.gap>=8 && snapshot.gap<=18, `${lang}/${width}/${deg}：索引间隙 ${snapshot.gap}`)
    assert.ok(snapshot.spacing>=20, `${lang}/${width}/${deg}：人物发生交叠`)
    minGap=Math.min(minGap,snapshot.gap);maxGap=Math.max(maxGap,snapshot.gap);minSpacing=Math.min(minSpacing,snapshot.spacing)
  }
  assert.ok(Math.abs(Number(await p.locator('.nobel-stage').getAttribute('data-angle'))-start-360)<1)
  await p.mouse.up()
  metrics.push({lang,width,samples:121,minGap,maxGap,minSpacing})
}
try {
 for(const lang of ['zh','en'])for(const width of [1440,768,390])await scan(lang,width)
 await p.setViewportSize({width:1440,height:1100});await p.goto(`${base}/news`)
 await p.getByText('吉林大学 物理学院 物质模拟方法与软件教育部重点实验室',{exact:true}).waitFor()
 assert.equal(await p.getByText('从超导与超流到量子隧穿，认识十一位诺奖得主。',{exact:true}).count(),1)
 assert.equal(await p.locator('.nobel-gallery-topline').count(),0)
 assert.equal(await p.getByRole('button',{name:/暂停旋转|继续旋转/}).count(),0)
 const contact=p.locator('.nobel-contact')
 const emails=await contact.locator('a').evaluateAll(es=>es.map(e=>e.getAttribute('href')))
 assert.deepEqual(emails,['mailto:mayuan@calypso.org.cn','mailto:zhongxin@jlu.edu.cn','mailto:hanyuliu@jlu.edu.cn'])
 assert.equal(await contact.locator('.nobel-contact-person').count(),4)
 assert.equal(await contact.locator('.nobel-contact-person').filter({hasText:'郭强'}).locator('a').count(),0)
 assert.ok((await contact.innerText()).includes('如果有任何问题和合作，欢迎联系。'))
 assert.ok(await contact.evaluate(e=>e.getBoundingClientRect().top>=document.querySelector('.nobel-person-index').getBoundingClientRect().bottom))
 await p.getByRole('button',{name:'Onnes',exact:true}).click()
 await p.locator('.nobel-feature').screenshot({path:new URL('desktop.png',out).pathname})
 await p.setViewportSize({width:390,height:844});await p.getByRole('button',{name:'Giaever',exact:true}).click()
 await p.locator('.nobel-feature').screenshot({path:new URL('mobile.png',out).pathname})
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
 // 正常模式：选择索引后自动恢复，不再依赖一个不可见的暂停开关。
 await p.emulateMedia({reducedMotion:'no-preference'});await p.goto(`${base}/nobel-demo.html`)
 await p.mouse.move(0,0)
 const angle=()=>p.locator('.nobel-stage').getAttribute('data-angle').then(Number)
 const initial=await angle();await p.waitForTimeout(300);assert.ok(await angle()>initial)
 await p.getByRole('button',{name:'Giaever',exact:true}).click();await p.mouse.move(0,0)
 const selected=await angle();await p.waitForTimeout(300);assert.ok(await angle()>selected)
 // 键盘阅读仅在焦点停留于人物时暂停，离开后恢复。
 await p.locator('.nobel-face.is-selected').focus();const focused=await angle();await p.waitForTimeout(200);assert.equal(await angle(),focused)
 await p.locator('.nobel-contact a').first().focus();await p.mouse.move(0,0);await p.waitForTimeout(200);assert.ok(await angle()>focused)
 assert.deepEqual(errors,[])
 await writeFile(new URL('browser.json',out),JSON.stringify({base,metrics,checks:['提示及暂停按钮移除','索引选择后继续旋转','联系人四人、三条准确邮箱、无郭强邮箱','中文机构及引言逐字匹配','键盘焦点阅读及离开恢复','手机无横向溢出'],errors},null,2)+'\n')
 console.log(metrics)
} finally {await b.close()}
