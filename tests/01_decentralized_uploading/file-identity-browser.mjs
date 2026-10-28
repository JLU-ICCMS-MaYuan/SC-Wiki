// 正式上传页面与真实原生确认框；API 仅使用隔离夹具，不提交用户论文。
import assert from 'node:assert/strict'
import {mkdir, writeFile, readFile} from 'node:fs/promises'
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const output = process.env.IDENTITY_BROWSER_OUTPUT || '/tmp/scwiki135-identity-browser'
await mkdir(output,{recursive:true})
const task='8'.repeat(32), submissions=[], dialogs=[], errors=[]
const definitions=JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json',import.meta.url),'utf8'))
const paper={title:'Isolated identity comparison',year:2026,paper_type:'review',superconductor_kind:'unknown',authors:[],
  keywords_tags:[],methodology:[],material_families:[{id:1,name:'氢基超导体',status:'confirmed'}]}
const message='上传文件的身份信息存在以下差异：\n\nDOI：\npaper.pdf：10.1000/main\nSI.pdf：10.1000/other'
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}})
 await context.addInitScript(()=>{
  localStorage.setItem('auth_token','isolated')
  localStorage.setItem('auth_user',JSON.stringify({id:7,username:'fixture',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}))
  localStorage.setItem('sc-wiki.language','zh')
 })
 await context.route('**/api/**',async route=>{
  const request=route.request(), path=new URL(request.url()).pathname
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)})
  if(path==='/api/auth/me')return json({user:{id:7,username:'fixture',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}})
  if(path==='/api/form-definitions')return json(definitions)
  if(path.startsWith('/api/form-definitions/'))return json(definitions.find(d=>path.includes(d.definition_key)))
  if(path==='/api/classification-catalogs')return json({material_families:[{id:1,name:'氢基超导体'}],structure_families:[],material_dimensionalities:[]})
  if(path.endsWith('/space-groups'))return json({space_groups:[]})
  if(path.endsWith('/submit')){
   const body=request.postDataJSON();submissions.push(body)
   if(!body.consistency_acknowledged)return json({detail:{code:'consistency_ack_required',message,consistency_version:'frozen-files'}},409)
   assert.equal(body.consistency_version,'frozen-files');return json({ok:true,paper_id:99,review_status:'pending'})
  }
  if(path.endsWith('/submit-check'))return json({status:'completed',version:'fields-v1',records:[],needs_check:false})
  if(path.endsWith('/summary'))return json({version:'draft-v1',records:[],needs_check:false})
  if(path.endsWith('/draft-state'))return json({version:'draft-v1',draft:{paper,material_states:[]}})
  if(path.endsWith('/draft'))return json(request.method()==='GET'?{data:{paper,material_states:[],structure_candidates:[]}}:{ok:true})
  if(path===`/api/upload-tasks/${task}`)return json({data:{task_id:task,filename:'fixture.pdf',stage:'ready',processing_status:'succeeded',stage_index:5,stage_total:5}})
  if(path.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready'},next_poll_ms:null}})
  if(path==='/api/upload-tasks')return json({data:[]})
  if(path==='/api/rag/spectra')return json({items:[],jobs:[],version:'v',can_edit:true,can_review:false})
  if(path.includes('/jobs'))throw new Error('身份确认不能排队模型任务')
  return json({items:[],total:0})
 })
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message))
 await page.goto(`${process.env.FRONTEND_URL||'http://127.0.0.1:5173'}/upload/tasks/${task}`)
 for(const accepted of [false,true]){
  const dialogSeen=new Promise((resolve,reject)=>page.once('dialog',async dialog=>{
   try{
    assert(dialog.message().includes(message));assert(!dialog.message().includes('标题、DOI 或作者'))
    dialogs.push({accepted,message:dialog.message()})
    if(accepted)await dialog.accept();else await dialog.dismiss()
    resolve()
   }catch(error){reject(error)}
  }))
  await page.getByRole('button',{name:'提交审核',exact:true}).click()
  await dialogSeen
  if(!accepted){
   await page.getByRole('button',{name:'提交审核',exact:true}).waitFor()
   assert.equal(submissions.length,1)
   await page.screenshot({path:`${output}/cancelled-conflict.png`})
  }
 }
 await page.waitForTimeout(300)
 assert.equal(submissions.length,3)
 assert.deepEqual(errors,[])
 await writeFile(`${output}/result.json`,JSON.stringify({passed:true,dialogs,submissions,modelJobs:0,errors},null,2))
 console.log(JSON.stringify({passed:true,submissions:submissions.length,dialogs:dialogs.length,modelJobs:0}))
} finally {await browser.close()}
