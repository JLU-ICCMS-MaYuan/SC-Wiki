// 已获用户明确授权：本机真实1208二次送审稿。通过正式页面/API操作，不替换接口。
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const chunks=[];for await(const part of process.stdin)chunks.push(part)
const config=JSON.parse(Buffer.concat(chunks).toString('utf8'))
assert.equal(config.paper_id,1208);assert.ok(['admin','superadmin'].includes(config.user.role))
const base=process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname),'只允许本机黑盒')
const phase=process.argv[2] || 'families',out=process.env.CAH6_REVIEW_OUTPUT || '.local/issue226/blackbox'
await mkdir(out,{recursive:true})
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || '/Users/mayuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'})
const context=await browser.newContext({viewport:{width:1600,height:1150}})
await context.addInitScript(({token,user})=>{
 localStorage.setItem('auth_token',token);localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
},config)
const requests=[],failures=[],results=[],page=await context.newPage()
page.on('pageerror',error=>failures.push({kind:'page',message:error.message}))
page.on('response',async response=>{
 const url=new URL(response.url()),path=url.pathname
 if(!path.startsWith('/api/'))return
 const method=response.request().method()
 if(method!=='GET' && method!=='OPTIONS'){
  const body=response.request().postDataJSON()
  requests.push({path,method,status:response.status(),action:body?.action,status_value:body?.status,item_key:body?.item_key})
 }
 if(response.status()>=400){
  let data={};try{data=await response.json()}catch{}
  failures.push({path,status:response.status(),code:data.code||data.detail?.code,
   message:data.message||data.error||data.detail?.message,issues:data.detail?.issues?.slice(0,5)})
 }
})
try{
 const draftReady=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/draft-state'))
 const initialSummary=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/summary'))
 await page.goto(base+'/admin/papers/1208/edit')
 await page.locator('[data-issue-field="material_states[0].structure_families"]').waitFor()
 assert.equal((await initialSummary).status(),200)
 assert.equal((await draftReady).status(),200)
 await page.waitForFunction(keys=>{
  const nodes=[...document.querySelectorAll('[data-material-state-index][data-state-key]')]
  return nodes.length===keys.length && nodes.every((node,i)=>node.getAttribute('data-state-key')===keys[i])
 },config.states.map(s=>s.state_key))
 if(phase==='families'){
  for(const state of config.states){
   if(!/^CaH/.test(state.material || ''))continue
   const root=page.locator('[data-material-state-index][data-state-key="'+state.state_key+'"]')
   const index=await root.getAttribute('data-material-state-index')
   assert.ok(index!==null,'材料稳定身份未找到 '+state.state_key)
   const field=root.locator('[data-issue-field$=".structure_families"]')
   if(!(await field.isVisible()))await root.locator('[data-state-toggle]').click()
   await field.scrollIntoViewIfNeeded()
   await field.locator('[data-evidence-key]').first().click()
   let side=page.locator('.evidence-review-drawer')
   await side.getByRole('tab',{name:'字段设置',exact:true}).click()
   const input=side.getByRole('combobox').first()
   await input.waitFor()
   const desired=state.material==='CaH6'?['笼型结构']:[]
   while(await side.locator('.MuiAutocomplete-root .MuiChip-deleteIcon').count())await side.locator('.MuiAutocomplete-root .MuiChip-deleteIcon').first().click()
   if(desired.length){await input.fill(desired[0]);await input.press('Enter')}
   const apply=side.getByRole('button',{name:'应用修改',exact:true})
   if(await apply.isEnabled())await apply.click()
   else await side.getByRole('button',{name:'关闭来源详情',exact:true}).click()
   await side.waitFor({state:'hidden'})
   await field.locator('[data-evidence-key]').first().click()
   side=page.locator('.evidence-review-drawer')
   const approve=side.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true})
   await approve.waitFor()
   if(await approve.isEnabled()){
    const reply=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/field-decision')&&r.request().method()==='POST')
    await approve.click()
    const response=await reply,data=await response.json()
    assert.equal(response.status(),200,JSON.stringify(data).slice(0,1000))
    assert.equal(data.record.field_decision?.mode,'without_evidence')
    assert.deepEqual(data.record.current_value,desired)
   }
   await side.getByText('已人工通过，未提供证据（结果已保存）',{exact:true}).waitFor()
   const status=await field.locator('[data-evidence-key]').first().getAttribute('data-evidence-status')
   assert.equal(status,'waived')
   const labels=await field.locator('.MuiChip-label').allTextContents()
   assert.deepEqual(labels,desired)
   results.push({state_key:state.state_key,material:state.material,pressure:state.pressure_value_gpa,value:desired,status:'waived',passed:true})
   if(results.length===1)await page.screenshot({path:out+'/family-yellow.png'})
   await side.getByRole('button',{name:'关闭来源详情',exact:true}).click()
   await side.waitFor({state:'hidden'})
  }
  assert.ok(results.length>0)
  assert.equal(requests.filter(r=>r.path.endsWith('/jobs')).length,0,'结构家族黄色路径不应调用模型')
 }else if(phase==='approve'){
  await page.getByLabel('审核意见',{exact:true}).fill('按本轮要求核查当前稿件；CaH6结构家族为笼型结构，其他Ca–H结构家族留空，均保留人工免证黄色。其余字段使用当前有效核对结果并完成提交检查。')
  await page.locator('#edit-review-status').click()
  await page.getByRole('option',{name:'审核通过并发布',exact:true}).click()
  const reply=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/review-commit')&&r.request().method()==='POST',{timeout:180000})
  await page.getByRole('button',{name:'审核通过并发布',exact:true}).click()
  const response=await reply,data=await response.json()
  results.push({status:response.status(),response:data})
  assert.equal(response.status(),200,JSON.stringify(data).slice(0,1500))
  assert.equal(data.review_status,'approved')
  await page.waitForURL(url=>!url.pathname.endsWith('/edit'))
  await page.screenshot({path:out+'/approved-workspace.png'})
 }else throw new Error('未知阶段')
 await writeFile(out+'/'+phase+'.json',JSON.stringify({phase,paper_id:1208,results,requests,failures},null,2))
 console.log(JSON.stringify({phase,results,failures}))
}catch(error){
 await page.screenshot({path:out+'/'+phase+'-failure.png'}).catch(()=>{})
 await writeFile(out+'/'+phase+'-failure.json',JSON.stringify({phase,results,requests,failures,error:error.message},null,2))
 console.log(JSON.stringify({phase,completed:results,error:error.message,failures}))
 throw error
}finally{await context.close();await browser.close()}
