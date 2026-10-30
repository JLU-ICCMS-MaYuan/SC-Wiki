import assert from 'node:assert/strict'
import {readFile,writeFile} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const fixture=JSON.parse(await readFile(process.env.HANDOFF_BROWSER_FIXTURE,'utf8'))
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const context=await browser.newContext({viewport:{width:1440,height:1100}})
const requests=[],errors=[]
const user={id:1,username:'isolated-browser',role:'admin',is_approved:true,is_email_verified:true,account_status:'active'}
await context.addInitScript(user=>{
 localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
},user)
await context.route('**/api/**',async route=>{
 const request=route.request(),url=new URL(request.url())
 requests.push({path:url.pathname,method:request.method()})
 const json=value=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)})
 if(url.pathname==='/api/auth/me')return json({user})
 if(url.pathname==='/api/rag/llm/catalog')return json({data:{items:[]}})
 if(url.pathname==='/api/rag/handoffs')return json(fixture)
 const snapshot=url.pathname.match(/\/snapshots\/([^/]+)$/)
 if(snapshot)return json(fixture.snapshots[snapshot[1]])
 if(url.pathname.includes('classification-catalogs'))return json({material_families:[],structure_families:[],material_dimensionalities:[]})
 if(url.pathname.includes('space-groups'))return json({space_groups:[]})
 if(url.pathname.includes('form-definitions'))return json([])
 if(request.method()!=='GET')errors.push('unexpected write '+url.pathname)
 return json({data:[],items:[]})
})
try{
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
 await page.goto(process.env.FRONTEND_URL+'/manuscripts/paper/'+fixture.paper_id+'/handoffs')
 await page.getByRole('heading',{name:'交接记录与快照',exact:true}).waitFor({timeout:10000}).catch(async error=>{
   console.log(JSON.stringify({url:page.url(),errors,body:(await page.locator('body').innerText()).slice(0,3000),requests}))
   throw error
 })
 const links=page.getByRole('link',{name:'查看整稿',exact:true})
 assert.equal(await links.count(),fixture.events.length)
 const waiting=context.waitForEvent('page')
 await links.last().click()
 const frozen=await waiting;frozen.on('pageerror',e=>errors.push(e.message))
 await frozen.waitForLoadState('domcontentloaded')
 const title=frozen.locator('[data-issue-field="paper.title"] input')
 await title.waitFor()
 assert.equal(await title.inputValue(),'公开原稿')
 assert.equal(await title.isEditable(),false)
 await frozen.locator('[data-issue-field="paper.title"] label').click()
 await frozen.getByRole('tab',{name:'来源核对',exact:true}).click()
 assert.equal(await frozen.getByRole('tab').count(),2)
 assert.equal(await frozen.getByRole('tab',{name:'历史记录',exact:true}).count(),0)
 assert.equal(await frozen.getByText(/实时生成中|正在生成解析草稿/).count(),0)
 assert.equal(await frozen.getByText('刷新谱状态',{exact:true}).count(),0)
 assert.deepEqual(requests.filter(r=>r.path.startsWith('/api/rag/spectra')),[])
 assert.deepEqual(requests.filter(r=>r.method!=='GET'),[])
 assert.deepEqual(requests.filter(r=>/field-detail|\/jobs|\/summary|\/draft-revision/.test(r.path)),[])
 assert.deepEqual(errors,[])
 await frozen.screenshot({path:process.env.HANDOFF_BROWSER_OUTPUT+'.png',fullPage:true})
 const report={events:fixture.events.length,new_tab:true,title:'公开原稿',read_only:true,tabs:['字段设置','来源核对'],requests,errors}
 await writeFile(process.env.HANDOFF_BROWSER_OUTPUT,JSON.stringify(report,null,2))
 console.log(JSON.stringify(report))
}finally{await browser.close()}
