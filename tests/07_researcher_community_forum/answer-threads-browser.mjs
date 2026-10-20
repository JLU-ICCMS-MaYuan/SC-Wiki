import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE)
const fixture = JSON.parse(await readFile(process.env.COMMUNITY_BROWSER_FIXTURE, 'utf8'))
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH })
const base=process.env.COMMUNITY_BASE_URL, out=process.env.COMMUNITY_ARTIFACT_DIR
const checks=[],errors=[]
try {
 for(const [role,identity] of Object.entries(fixture.users)){
  const context=await browser.newContext({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  await context.addInitScript(user=>{if(user){localStorage.setItem('auth_token',user.token);localStorage.setItem('auth_user',JSON.stringify(user.user))}if(!localStorage.getItem('sc-wiki.language'))localStorage.setItem('sc-wiki.language','zh')},identity)
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
  await page.goto(`${base}/share/discussions`);await page.getByRole('heading',{name:'AI 学术讨论',exact:true}).waitFor()
  assert.equal(await page.getByRole('button',{name:'生成答案',exact:true}).count(),0)
  await page.goto(`${base}/share/discussions/${fixture.question_id}`)
  await page.getByRole('heading',{name:fixture.question_title,exact:true}).waitFor()
  await page.getByText('补充回答',{exact:true}).first().waitFor()
  assert.equal(await page.getByText('DeepSeek',{exact:true}).count(),1)
  assert.equal(await page.getByText('OpenAI',{exact:true}).count(),1)
  if(role==='superadmin'){
   await page.getByRole('button',{name:'生成答案',exact:true}).click()
   await page.getByRole('combobox',{name:'选择回答模型'}).click()
   await page.getByRole('option',{name:/DeepSeek/}).click()
   await page.screenshot({path:`${out}/model-selector.png`,fullPage:true})
   await page.getByRole('button',{name:'加入生成队列',exact:true}).click()
   await page.getByText('等待生成',{exact:true}).last().waitFor()
   checks.push('真实API入队，选择模型并保留运行中的队列')
  } else assert.equal(await page.getByRole('button',{name:'生成答案',exact:true}).count(),0)
  await page.screenshot({path:`${out}/${role}-desktop.png`,fullPage:true})
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  await page.screenshot({path:`${out}/${role}-mobile.png`,fullPage:true})
  await page.evaluate(()=>localStorage.setItem('sc-wiki.language','en'));await page.reload()
  await page.getByText('Follow-up answer',{exact:true}).first().waitFor()
  checks.push(`${role}: 模型分卡、追加段、入口权限、窄屏和英文通过`)
  await context.close()
 }
 assert.deepEqual(errors,[])
 await writeFile(`${out}/browser.json`,JSON.stringify({checks,errors},null,2))
 console.log(`PASS browser ${checks.length} checks`)
}finally{await browser.close()}
