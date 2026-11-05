import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const root=process.env.FRONTEND_URL||'http://127.0.0.1:18588'
const fixture=process.env.SEARCH_FIXTURE_URL||'http://127.0.0.1:18587'
const artifacts=process.env.ARTIFACT_DIR||'/tmp/scwiki178-filter-browser'
await fs.mkdir(artifacts,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'})
const errors=[],cases=[],requests=[]
try {
 for(const role of ['anonymous','user','admin','superadmin']) {
  const context=await browser.newContext({viewport:{width:1400,height:1000}})
  let session=null
  if(role!=='anonymous')session=await (await context.request.get(fixture+'/test-session/'+role)).json()
  await context.addInitScript(({session})=>{
   localStorage.setItem('sc-wiki.language','zh')
   if(session){localStorage.setItem('auth_token',session.token);localStorage.setItem('auth_user',JSON.stringify(session.user))}
  },{session})
  // 所有 API 只走本轮隔离夹具，浏览器不调用业务库。
  await context.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url())
   if(req.method()==='POST')requests.push({role,path:url.pathname,body:req.postDataJSON()})
   const response=await route.fetch({url:fixture+url.pathname+url.search})
   await route.fulfill({response})
  })
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
  await page.goto(root+'/search?elements=H,La,Sc&mode=elements_exact_search&view=states&superconductor_type=hydride')
  const admin=role==='admin'||role==='superadmin',count=8 // 家族 1 当前只关联批准论文 271。
  await page.getByTestId('search-state-card').nth(count-1).waitFor()
  const type=page.getByRole('combobox',{name:'超导类型'})
  assert.match(await type.textContent(),/氢基超导体/)
  assert.equal(await page.getByText('高压氢化物',{exact:true}).count(),0)
  assert.equal(await page.getByRole('combobox',{name:'审核状态'}).count(),admin?1:0)
  // 选正式 ID 后旧别名地址移除，新请求按稳定 ID 过滤。
  await type.click();await page.getByRole('option',{name:'自建家族',exact:true}).click()
  await page.getByText('没有匹配记录',{exact:true}).waitFor()
  await type.click();await page.getByRole('option',{name:'氢基超导体',exact:true}).click()
  await page.waitForURL(/material_family_id=1/)
  assert.ok(!page.url().includes('superconductor_type='))
  // 清除类型，才能检索夹具中尚未登记家族的待审／拒绝论文。
  await type.click();await page.getByRole('option',{name:'全部类型',exact:true}).click()
  await page.getByTestId('search-state-card').nth(admin?10:7).waitFor()
  if(admin){
   for(const [label,title] of [['待审核 Pending','待审'],['已驳回 Rejected','拒绝']]){
    await page.getByRole('combobox',{name:'审核状态'}).click()
    await page.getByRole('option',{name:label,exact:true}).click()
    await page.getByText(title,{exact:true}).waitFor()
    assert.equal(await page.getByTestId('search-state-card').count(),1)
   }
  }else{
   await page.goto(root+'/search?elements=H,La,Sc&mode=elements_exact_search&view=states&review_status=Rejected')
   await page.getByTestId('search-state-card').nth(7).waitFor()
   assert.equal(await page.getByRole('combobox',{name:'审核状态'}).count(),0)
   assert.ok(!requests.filter(r=>r.role===role).some(r=>r.body.review_status))
   const before=requests.filter(r=>r.role===role&&r.path.includes('structural-records')).length
   await page.getByRole('button',{name:'仅看有代表 Tc 的材料状态'}).click()
   await page.waitForFunction(()=>document.querySelectorAll('[data-testid="search-state-card"]').length===7)
   assert.equal(requests.filter(r=>r.role===role&&r.path.includes('structural-records')).length,before)
  }
  await page.screenshot({path:path.join(artifacts,role+'-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:path.join(artifacts,role+'-mobile.png'),fullPage:true})
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow '+role)
  cases.push(role+':catalog-id,status-permission,query-results,mobile')
  await context.close()
 }
 assert.deepEqual(errors,[])
 await fs.writeFile(path.join(artifacts,'browser.json'),JSON.stringify({passed:true,cases,errors,requests,scope:'正式 React 路由与 Go Handler／OptionalAuth／隔离 MySQL；目录和独立结构响应为夹具，Python 结构真实查询另由 TestClient 验证。'},null,2))
 console.log('passed four-role browser cases:',artifacts)
} finally {await browser.close()}
