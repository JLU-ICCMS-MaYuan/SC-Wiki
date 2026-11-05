// 正式四宿主路由与Chrome真实输入；全部业务API隔离，不替用户稿件作人工决定。
import assert from 'node:assert/strict'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const out=process.env.EMPTY_CONFIRM_OUTPUT || '/tmp/scwiki221-empty-browser'
await mkdir(out,{recursive:true})
const definitions=JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json',import.meta.url),'utf8'))
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const results=[]
try {
 for(const role of ['upload','revision','admin','superadmin']) for(const mode of ['human','model']) {
  const task='e'.repeat(32),item='c'.repeat(64),field='material_states[0].structure_families'
  const family={id:1,name:'Sodalite',name_en:'Sodalite',name_zh:'方钠石',status:'confirmed'}
  const paper={id:177,title:'Isolated empty confirmation',year:2026,authors:[],paper_type:'theoretical',material_families:[],review_status:role==='revision'?'rejected':'pending',uploaded_by_user_id:7}
  const state={id:1,state_key:'s',material:'CaH4',material_name:'tI10-CaH4',state_kind:'theoretical',pressure_value_gpa:50,
   structure_optimization:'classical_static',crystal_system:'tetragonal',element_count:2,material_dimensionality:'three_dimensional',
   superconductor:{chemical_formula:'CaH4'},structure_families:[family],property_modules:[]}
  const draft={paper,material_states:[state],structure_candidates:[]}
  let manual={changed:true,reason:'',no_evidence_reason:'',items:[]},accepted=false,polls=0
  const writes=[],errors=[]
  const record=()=>({key:item,item_key:item,field,fields:[field],label:'结构家族',state_key:'s',
   current_value:state.structure_families.map(f=>f.name),empty_allowed:true,required:state.structure_families.length>0,
   human_modified:true,status:accepted?'supported':'uncertain',pending_review:!accepted,stale:!accepted,
   human_confirmed:accepted&&mode==='human',reason:accepted?'当前空值合理':'旧值的AI理由',ai_reason:accepted?'':'旧值的AI理由',
   evidences:[{file_id:'main',chunk_index:0,quote:'CaH4 has a tetragonal structure.'}],
   ...(accepted&&mode==='human'?{source_kind:'human_review',field_decision:{contract:'field-review-v2',action:'approve',mode:'empty'}}:{})})
  const user={id:7,username:'isolated',role:role==='admin'?'admin':role==='superadmin'?'superadmin':'user',
   is_admin:['admin','superadmin'].includes(role),is_approved:true,is_email_verified:true,account_status:'active'}
  const context=await browser.newContext({viewport:{width:1500,height:1100}})
  await context.addInitScript(user=>{
   localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
  },user)
  await context.route('**/api/**',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname
   if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push({method:request.method(),path})
   const json=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
   if(path==='/api/auth/me')return json({user})
   if(path==='/api/rag/llm/catalog')return json({data:{items:[]}})
   if(path==='/api/rag/llm/current')return json({data:{provider:'fixture',provider_name:'fixture',model:'isolated',source:'server'}})
   if(path.endsWith('/activity'))return json({ok:true})
   if(path==='/api/form-definitions')return json(definitions)
   if(path.startsWith('/api/form-definitions/'))return json(definitions.find(x=>decodeURIComponent(path).includes(x.definition_key)) || {})
   if(path.includes('/classification-catalogs'))return json({material_families:[],structure_families:[family],material_dimensionalities:[]})
   if(path==='/api/admin/papers/177')return json({...paper,material_states:[state]})
   if(path.endsWith('/open-workdraft'))return json({write_epoch:'isolated-empty',revision:1})
   if(path.includes('/revision-draft'))return json({data:draft,revision_id:'revision-empty',draft_version:1})
   if(path.endsWith('/draft-state'))return json({version:'v',draft,staged:false})
   if(path==='/api/rag/evidence/draft'&&request.method()==='PATCH'){
    const body=request.postDataJSON();assert.equal(body.changes.length,1);assert.equal(body.changes[0].path.at(-1),'structure_families')
    state.structure_families=body.changes[0].value;return json({changed:true,version:'saved'})
   }
   if(path.endsWith('/summary'))return json({version:'v',records:[record()],needs_check:false})
   if(path.endsWith('/identify-field'))return json({record:record()})
   if(path.endsWith('/field-detail'))return json({record:record(),review_token:'fresh',can_confirm_empty:!!manual.reason&&!!manual.no_evidence_reason,approval_state:accepted?'human_approved':'modification_required',source_state:'available'})
   if(path.endsWith('/manual-context'))return json({version:'manual-v1',record:record()})
   if(path.includes('/manual/')){
    if(request.method()==='GET')return json({data:manual})
    manual={...manual,...request.postDataJSON(),after_value:[]};return json({data:manual})
   }
   if(path.endsWith('/field-decision')){
    assert.equal(mode,'human');const body=request.postDataJSON()
    assert.equal(body.action,'confirm_empty');assert.equal(body.review_token,'fresh')
    assert.equal(manual.reason,'此状态暂不分类');assert.equal(manual.no_evidence_reason,'暂无适合分类依据')
    accepted=true;return json({record:record(),review_token:'done',can_confirm_empty:true,approval_state:'human_approved',source_state:'available'})
   }
   if(path.endsWith('/field-input'))return json({field_token:'empty-field',version:'v',records:[record()]})
   if(path.endsWith('/jobs')&&request.method()==='POST'){
    assert.equal(mode,'model');assert.equal(request.postDataJSON().retry_keys.length,1)
    return json({id:'job-empty',status:'queued',timeout_seconds:60})
   }
   if(path.endsWith('/jobs/job-empty')){
    if(polls++===0)return json({id:'job-empty',status:'running',activity:{stage:'model',message:'正在核对留空理由'}})
    accepted=true;return json({id:'job-empty',status:'completed',records:[record()]})
   }
   if(path.endsWith('/draft'))return json({data:draft})
   if(path==='/api/upload-tasks/'+task)return json({data:{task_id:task,filename:'isolated.pdf',stage:'ready',stage_index:5,stage_total:5,processing_status:'succeeded'}})
   if(path.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:1,total:1},next_poll_ms:null}})
   if(request.method()!=='GET'){errors.push(request.method()+' '+path);return json({})}
   return json({data:{},items:[],jobs:[],space_groups:[],total:0})
  })
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
  const path=role==='upload'?'/upload/tasks/'+task:role==='revision'?'/papers/177/revise':'/admin/papers/177/edit'
  await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5173')+path)
  const familyField=page.locator('[data-issue-field="'+field+'"]');await familyField.locator('.MuiChip-deleteIcon').click()
  await familyField.locator('[data-evidence-key]').first().click()
  const side=page.locator('.evidence-review-drawer')
  await side.getByLabel('人工修改判断理由（必填）').fill('此状态暂不分类')
  await side.getByLabel('不提供证据',{exact:true}).check()
  await side.getByLabel('不提供证据的理由（必填）').fill('暂无适合分类依据')
  await side.getByRole('button',{name:mode==='human'?'人工确认留空':'大模型核对',exact:true}).click()
  const label=mode==='human'?'已人工确认留空（结果已保存）':'核对通过（结果已保存）'
  await side.getByText(label,{exact:true}).waitFor({timeout:20000})
  if(mode==='human')await side.getByText(/人工操作未调用大模型/).waitFor()
  assert.equal(await side.getByText('旧值的AI理由',{exact:true}).count(),0)
  await side.getByText(/CaH4 has a tetragonal structure/).waitFor()
  const jobs=writes.filter(x=>x.path.endsWith('/jobs'))
  assert.equal(jobs.length,mode==='human'?0:1)
  assert.equal(await page.getByLabel('标题',{exact:true}).inputValue(),'Isolated empty confirmation')
  await page.screenshot({path:out+'/'+role+'-'+mode+'.png'})
  await side.getByRole('button',{name:'关闭来源详情',exact:true}).click()
  await side.waitFor({state:'hidden'})
  await familyField.locator('[data-evidence-key]').first().click()
  await page.locator('.evidence-review-drawer').getByText(label,{exact:true}).waitFor()
  assert.deepEqual(errors,[])
  results.push({role,mode,model_jobs:jobs.length,write_paths:writes,passed:true,reopened:true,other_value_unchanged:true,errors})
  console.log(role,mode,'passed')
  await context.close()
 }
 await writeFile(out+'/result.json',JSON.stringify(results,null,2))
} finally {await browser.close()}
