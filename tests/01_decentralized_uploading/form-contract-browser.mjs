// 固定真实草稿副本、正式页面和隔离 API；不写真实业务数据。
import assert from 'node:assert/strict'
import {readFile,writeFile} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root=fileURLToPath(new URL('../../',import.meta.url))
const live=JSON.parse(await readFile(process.env.FORM_CONTRACT_DRAFT,'utf8'))
const summary=JSON.parse(await readFile(process.env.FORM_CONTRACT_SUMMARY,'utf8'))
const definitions=JSON.parse(await readFile(root+'/backend/data/form_definitions.v1.json','utf8'))
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const all=[]
try {
{
 const mode='full'
 const draft=structuredClone(live)
 const records=summary.records
 const task='173'.padEnd(32,'0'), user={id:7,username:'isolated',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}
 let requests=[],errors=[],measure=false
 const context=await browser.newContext({viewport:{width:1440,height:1100}})
 await context.addInitScript(user=>{
  localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
  window.delays=[];window.longtasks=[];window.rootScans=0
  new PerformanceObserver(list=>window.longtasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true})
  const query=Element.prototype.querySelectorAll
  Element.prototype.querySelectorAll=function(selector){if(this.hasAttribute('data-evidence-scope') && selector==='[data-issue-field]')window.rootScans++;return query.call(this,selector)}
  document.addEventListener('keydown',e=>{if(!e.target.closest('[data-issue-field="paper.knowledge_graph_title"]')||e.key.length!==1)return;const start=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>window.delays.push(performance.now()-start)))},true)
 },user)
 await context.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname
  if(measure)requests.push({method:req.method(),path:p})
  const json=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
  if(p==='/api/auth/me')return json({user})
  if(p.endsWith('/activity'))return json({ok:true})
  if(p==='/api/form-definitions')return json(definitions)
  if(p.startsWith('/api/form-definitions/'))return json(definitions.find(d=>p.includes(encodeURIComponent(d.definition_key)))||definitions.find(d=>decodeURIComponent(p).includes(d.definition_key))||{})
  if(p==='/api/classification-catalogs')return json({material_families:draft.paper.material_families||[],structure_families:[],material_dimensionalities:[]})
  if(p.endsWith('/space-groups'))return json({space_groups:[]})
  if(p.endsWith('/summary'))return json({...summary,records})
  if(p.endsWith('/draft-state'))return json({version:'isolated',draft})
  if(p==='/api/rag/evidence/draft'&&req.method()==='PATCH')return json({version:'isolated2',changed:true})
  if(p.endsWith('/draft'))return json({data:draft})
  if(p===`/api/upload-tasks/${task}`)return json({data:{task_id:task,filename:'isolated-current-draft.pdf',processing_status:'succeeded',stage:'ready',stage_index:5,stage_total:5}})
  if(p.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:1,total:1},next_poll_ms:null}})
  if(p==='/api/upload-tasks')return json({data:[]})
  if(req.method()!=='GET') {errors.push('unexpected '+req.method()+' '+p);return json({})}
  return json({items:[],total:0})
 })
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
 await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}/upload/tasks/${task}`)
 const input=page.locator('[data-issue-field="paper.knowledge_graph_title"] input')
 await input.waitFor({timeout:60000})
 await page.waitForTimeout(1200)
 await input.click();await input.press('End')
 const before=await input.inputValue()
 const dom=await page.evaluate(()=>({nodes:document.querySelectorAll('*').length,fields:document.querySelectorAll('[data-issue-field]').length}))
 await page.evaluate(()=>{window.delays=[];window.longtasks=[];window.rootScans=0})
 measure=true
 const start=Date.now();await input.pressSequentially(' test123456',{delay:80});const wall=Date.now()-start
 await page.waitForTimeout(500)
 const measures=await page.evaluate(()=>({delays:window.delays,longtasks:window.longtasks,rootScans:window.rootScans}))
 const during=[...requests]
 await page.waitForTimeout(5500)
 const sorted=measures.delays.slice().sort((a,b)=>a-b)
 const result={mode,...dom,reviewRecords:records.length,rootScans:measures.rootScans,wallMs:wall,paintMeanMs:sorted.reduce((a,b)=>a+b,0)/sorted.length,paintMaxMs:sorted.at(-1),longTaskCount:measures.longtasks.length,longTaskMaxMs:Math.max(0,...measures.longtasks.map(x=>x.duration)),requestsWhileTyping:during,requestsIncludingAutosave:requests,errors}
 all.push(result);console.log(JSON.stringify(result))
 assert.equal(await input.inputValue(),before+' test123456')
 assert.deepEqual(errors,[])
 assert.deepEqual(during,[])
 if(process.env.FORM_CONTRACT_BASELINE!=='1')assert.equal(measures.rootScans,0)
 await context.close()
}
await writeFile(process.env.FORM_CONTRACT_OUTPUT || '/tmp/scwiki-form-contract-browser.json',JSON.stringify(all,null,2))
}finally{await browser.close()}
