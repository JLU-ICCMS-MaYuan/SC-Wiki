// 正式页面与真实 Chrome 输入；全部业务 API 在独立会话拦截，不改用户稿件。
import assert from 'node:assert/strict'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const definitions=JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json',import.meta.url),'utf8'))
const out=process.env.RED_MARKING_OUTPUT || '/tmp/scwiki221-performance'
await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const results=[]
try {
for(const variant of ['before','after']) for(const role of ['upload','revision','admin','superadmin']) {
 const paper={id:174,title:'Original title',knowledge_graph_title:'Graph title',authors:[],year:2026,paper_type:'review',material_families:[],review_status:'pending',uploaded_by_user_id:8,doi:null}
 const states=Array.from({length:15},(_,i)=>({id:i+1,state_key:'s'+i,material:'Sn',material_name:'State '+i,state_kind:'experimental',crystal_system:'unknown',element_count:1,material_dimensionality:'unknown',superconductor:{chemical_formula:'Sn',material_name:'State '+i},structure_families:[],property_modules:[]}))
 const draft={paper,material_states:states,structure_candidates:[],_parsing_workflow:{workflow_key:'conventional-theory-calculation',workflow_version:1,form_key:'scientific-form-contract',form_version:1,form_sha256:'a'.repeat(64)}}
 const records=[{key:'doi',item_key:'b'.repeat(64),field:'paper.doi',label:'DOI',current_value:null,status:'unchecked',required:false,human_modified:false,evidences:[],reason:''},{key:'graph',item_key:'c'.repeat(64),field:'paper.knowledge_graph_title',label:'图谱科学标题',current_value:'Graph title',status:'supported',required:true,evidences:[],reason:''}]
 const user={id:7,username:'isolated220',role:role==='superadmin'?'superadmin':role==='admin'?'admin':'user',is_admin:['admin','superadmin'].includes(role),is_approved:true,is_email_verified:true,account_status:'active'}
 const context=await browser.newContext({viewport:{width:1500,height:1100}})
 const requests=[],errors=[];let measure=false
 await context.addInitScript(user=>{
  localStorage.setItem('auth_token','isolated220');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
  window.delays=[];window.rootScans=0;window.cardRenders=0
  const query=Element.prototype.querySelectorAll
  Element.prototype.querySelectorAll=function(selector){if(this.hasAttribute('data-evidence-scope')&&selector==='[data-issue-field]')window.rootScans++;return query.call(this,selector)}
  document.addEventListener('keydown',event=>{if(!event.target.closest('[data-issue-field="paper.knowledge_graph_title"]')||event.key.length!==1)return
   const start=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>window.delays.push(performance.now()-start)))},true)
 },user)
 await context.route('**/api/**',async route=>{
  const req=route.request(),p=new URL(req.url()).pathname
  if(measure)requests.push({method:req.method(),path:p})
  const json=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
  if(p==='/api/auth/me')return json({user})
  if(p.endsWith('/activity'))return json({ok:true})
  if(p==='/api/form-definitions')return json(definitions)
  if(p.startsWith('/api/form-definitions/'))return json(definitions.find(d=>decodeURIComponent(p).includes(d.definition_key))||{})
  if(p.includes('/classification-catalogs'))return json({material_families:[],structure_families:[],material_dimensionalities:[]})
  if(p.endsWith('/space-groups'))return json({space_groups:[]})
  if(p==='/api/admin/papers/174')return json({...paper,material_states:states})
  if(p.endsWith('/summary'))return json({version:'isolated',records,needs_check:false})
  if(p.endsWith('/open-workdraft'))return json({write_epoch:'isolated220',revision:1})
  if(p.includes('/draft-state'))return json({version:'isolated',draft,staged:false})
  if(p==='/api/rag/evidence/draft'&&req.method()==='PATCH')return json({version:'saved',changed:true,draft_version:2})
  if(p.includes('/revision-draft'))return json({data:draft,revision_id:'revision220',draft_version:1})
  if(p.endsWith('/draft'))return json({data:draft})
  if(p.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:1,total:1},next_poll_ms:null}})
  if(p==='/api/upload-tasks/'+ '220'.padEnd(32,'0'))return json({data:{task_id:'220'.padEnd(32,'0'),filename:'isolated220.pdf',processing_status:'succeeded',stage:'ready',stage_index:5,stage_total:5}})
  if(p==='/api/upload-tasks')return json({data:[]})
  if(req.method()!=='GET'){errors.push(req.method()+' '+p);return json({})}
  return json({data:{items:[]},items:[],total:0,space_groups:[],modules:[],jobs:[]})
 })
 await context.route('**/src/components/PressureEditor.tsx',async route=>{
  const response=await route.fetch(),source=await response.text()
  const marker=/function PressureEditor\(\{[\s\S]*?\}\) \{/
  assert.ok(marker.test(source),'真实PressureEditor入口未匹配，禁止假计数')
  await route.fulfill({response,body:source.replace(marker,match=>match+'window.cardRenders=(window.cardRenders||0)+1;')})
 })
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.stack||e.message))
 const path=role==='upload'?'/upload/tasks/'+ '220'.padEnd(32,'0'):role==='revision'?'/papers/174/revise':'/admin/papers/174/edit'
 await page.goto('http://127.0.0.1:'+(variant==='before'?5198:5199)+path)
 const graph=page.locator('[data-issue-field="paper.knowledge_graph_title"] input')
 await graph.waitFor({timeout:60000}).catch(async error=>{console.error(await page.locator("body").innerText(),errors);await page.screenshot({path:out+"/failure-"+variant+"-"+role+".png"});throw error});await page.waitForTimeout(400)
 await graph.click();await graph.press('End')
 const fields=await page.locator('[data-issue-field]').count()
 await page.evaluate(()=>{window.delays=[];window.rootScans=0;window.cardRenders=0});measure=true
 await graph.pressSequentially(' test123456',{delay:70})
 await page.locator('[data-issue-field="paper.doi"] input').fill('10.1234/manual')
 await page.waitForTimeout(100)
 const doi=page.locator('[data-issue-field="paper.doi"] [data-evidence-caption-problem]').first()
 const marked=(await doi.getAttribute('data-evidence-caption-problem'))==='true'
 assert.equal(marked,true,variant+'/'+role+' DOI 标红')
 const metrics=await page.evaluate(()=>({delays:window.delays,rootScans:window.rootScans,cardRenders:window.cardRenders}))
 const typing=[...requests]
 assert.equal(metrics.rootScans,0);assert.equal(metrics.cardRenders,0);assert.deepEqual(typing,[])
 await page.getByRole('button',{name:role==='admin'||role==='superadmin'?'保存修改':'立即保存',exact:true}).click()
 await page.waitForTimeout(250)
 assert.equal((await doi.getAttribute('data-evidence-caption-problem'))==='true',marked)
 assert.equal(requests.filter(r=>/jobs|submit-check|preflight|\/summary/.test(r.path)).length,0)
 assert.deepEqual(errors,[])
 const sorted=metrics.delays.toSorted((a,b)=>a-b)
 const result={variant,role,states:states.length,fields,rootScans:metrics.rootScans,cardRenders:metrics.cardRenders,paintSamples:sorted.length,paintP95Ms:sorted[Math.floor(sorted.length*.95)]??null,paintMaxMs:sorted.at(-1)??null,doiMarked:marked,markedAfterSave:marked,requestsWhileTyping:typing,requestsIncludingSave:requests,errors}
 results.push(result);console.log(JSON.stringify(result))
 if(variant==='after'&&role==='revision')await page.screenshot({path:out+'/revision-marked.png'})
 await context.close()
}
await writeFile(out+'/browser.json',JSON.stringify(results,null,2)+'\n')
}finally{await browser.close()}
