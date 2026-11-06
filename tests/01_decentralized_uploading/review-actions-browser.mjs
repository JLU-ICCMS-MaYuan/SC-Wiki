// 正式路由、Chrome真实选择与按钮；全部业务API拦截，不发布用户稿件。
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const out=process.env.REVIEW_ACTION_OUTPUT || '/tmp/scwiki100-review'
await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const results=[]
try {
 for(const role of ['admin','superadmin'])for(const host of ['quick','edit'])for(const action of ['approved','rejected']){
  const paper={id:192,title:'Isolated review action',year:2026,paper_type:'review',authors:[],review_status:'pending',workflow_status:'pending',review_comment:'通过',material_families:[],material_states:[],uploaded_by_user_id:9}
  const draft={paper,material_states:[],structure_candidates:[]},calls=[],errors=[]
  const user={id:7,username:'isolated-reviewer',role,is_admin:true,is_approved:true,is_email_verified:true,account_status:'active'}
  const context=await browser.newContext({viewport:{width:1500,height:1100}})
  await context.addInitScript(user=>{
   localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
  },user)
  await context.route('**/api/**',async route=>{
   const request=route.request(),url=new URL(request.url()),path=url.pathname
   const json=value=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)})
   if(request.method()!=='GET')calls.push({path,body:request.postDataJSON()})
   if(path==='/api/auth/me')return json({user})
   if(path.endsWith('/llm/catalog'))return json({data:{items:[]}})
   if(path.endsWith('/llm/current'))return json({data:{provider:'fixture',provider_name:'fixture',model:'isolated',source:'server'}})
   if(path.includes('/papers/all')||path.includes('/reviewed-papers'))return json({items:paper.workflow_status==='pending'?[paper]:[],total:paper.workflow_status==='pending'?1:0})
   if(path==='/api/admin/papers/192')return json(paper)
   if(path.endsWith('/open-workdraft'))return json({revision:1,write_epoch:'isolated-cycle',paper_header:{title:paper.title}})
   if(path.endsWith('/draft-state'))return json({staged:false,version:'v',draft})
   if(path.endsWith('/draft-revision'))return json({revision:1,write_epoch:'isolated-cycle'})
   if(path.endsWith('/draft'))return json({data:draft})
   if(path.endsWith('/summary'))return json({version:'v',records:[],needs_check:false})
   if(path.endsWith('/submit-check'))return json({id:'gate',status:'completed',version:'v',records:[]})
   if(path.endsWith('/review-commit')){
    const body=request.postDataJSON();assert.equal(body.status,action);assert.equal(body.comment,'本轮核查意见')
    paper.workflow_status=action
    return json({ok:true,paper_id:192,review_status:action})
   }
   if(path.includes('/classification-catalogs'))return json({material_families:[],structure_families:[],material_dimensionalities:[]})
   if(path.includes('/form-definitions'))return json([])
   if(request.method()!=='GET')errors.push('未预期写入 '+path)
   return json({data:{},items:[],total:0,jobs:[],space_groups:[]})
  })
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message))
  const workspace=role==='admin'?'/admin?section=papers':'/superadmin?section=papers&review_tab=pending'
  await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5173')+(host==='edit'?'/admin/papers/192/edit':workspace))
  if(host==='quick')await page.getByRole('button',{name:'审核',exact:true}).click()
  const scope=host==='quick'?page.getByRole('dialog'):page
  const initial=scope.getByRole('button',{name:host==='quick'?'确认审核':'提交审核',exact:true})
  await initial.waitFor()
  assert.equal(await initial.isDisabled(),true)
  assert.equal(await scope.getByLabel('审核意见',{exact:true}).inputValue(),'')
  await scope.locator(host==='quick'?'#paper-review-status':'#edit-review-status').click()
  assert.equal(await page.getByRole('option',{name:/退回待审核|转交/}).count(),0)
  const label=action==='approved'?'审核通过并发布':'拒绝并退回作者'
  await page.getByRole('option',{name:label,exact:true}).click()
  await scope.getByLabel('审核意见',{exact:true}).fill('本轮核查意见')
  await page.screenshot({path:out+'/'+role+'-'+host+'-'+action+'.png',fullPage:true})
  await scope.getByRole('button',{name:label,exact:true}).click()
  await page.waitForFunction(()=>!document.querySelector('[role="dialog"]') || !document.querySelector('#paper-review-status'),{},{timeout:10000}).catch(()=>{})
  await page.waitForURL(url=>!url.pathname.endsWith('/edit'),{timeout:10000})
  for(let i=0;i<30&&calls.filter(c=>c.path.endsWith('/review-commit')).length===0;i++)await page.waitForTimeout(100)
  assert.equal(calls.filter(c=>c.path.endsWith('/review-commit')).length,1)
  assert.equal(calls.filter(c=>c.path.endsWith('/submit-check')).length,action==='approved'?1:0)
  assert.equal(calls.filter(c=>c.path.endsWith('/jobs')).length,0)
  assert.deepEqual(errors,[])
  results.push({role,host,action,passed:true,requests:calls.map(c=>c.path),business_writes:0,errors})
  await context.close()
 }
 await writeFile(out+'/result.json',JSON.stringify(results,null,2))
 console.log(JSON.stringify(results.map(({role,host,action,passed})=>({role,host,action,passed}))))
}finally{await browser.close()}
