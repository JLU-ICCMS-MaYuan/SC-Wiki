// 正式上传路由与真实鼠标／键盘；业务 API 全部隔离，模型结果固定，不写用户草稿。
import assert from 'node:assert/strict'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const output=process.env.FIELD_REVIEW_BROWSER_OUTPUT || '/tmp/scwiki177-browser'
await mkdir(output,{recursive:true})
const definitions=JSON.parse(await readFile(new URL('../fixtures/issue176/form-definitions.json',import.meta.url),'utf8'))
const task='177'.padEnd(32,'0'),item='a'.repeat(64),field='material_states[0].property_modules[0].records[0].payload.parameters.mu_star'
const errors=[],checks=[]
try {
 for(const outcome of ['supported','unsupported','failed','cancelled']){
  const paper={title:'Isolated field review',year:2026,authors:[],paper_type:'theoretical',material_families:[]}
  const property={record_key:'r',module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',
   definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version:1,
   name_raw:'Tc',method_code:'isotropic_eliashberg',value_kind:'number',value_number:220,value_raw:'220',canonical_unit:'K',unit_raw:'K',
   payload:{parameters:{lambda_ep:2.69,mu_star:.13},calculation_conditions:{},
     tc_group:{version:1,group_key:'g',method_key:'m',point_key:'r'}}}
  const draft={paper,structure_candidates:[],material_states:[{state_key:'s',material:'CaH6',material_name:'CaH6',
   state_kind:'theoretical',pressure_value_gpa:150,structure_optimization:'classical_static',
   property_modules:[{module_key:'m',module_code:'superconductive_properties',definition_key:'module.superconductive_properties',
    definition_version:1,records:[property]}]}]}
  const record=()=>({key:item,item_key:item,field,fields:[field],record_field:'payload.parameters.mu_star',
   state_key:'s',module_key:'m',record_key:'r',label:'μ*',current_value:property.payload.parameters.mu_star,
   status:'uncertain',reason:'待核对',evidences:[],human_modified:true,required:true})
  let manual={changed:true,reason:'',no_evidence_reason:'',items:[]},resolveJob,jobResult
  const jobWait=new Promise(resolve=>{resolveJob=resolve})
  const order=[],user={id:7,username:'isolated',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}
  const context=await browser.newContext({viewport:{width:1440,height:1000}})
  await context.addInitScript(user=>{
   localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
  },user)
  await context.route('**/api/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname
   const json=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
   if(path==='/api/auth/me')return json({user})
   if(path==='/api/rag/llm/catalog')return json({data:{items:[]}})
   if(path==='/api/rag/llm/current')return json({data:{provider:'fixture',provider_name:'fixture',model:'isolated',source:'server'}})
   if(path.endsWith('/activity'))return json({ok:true})
   if(path==='/api/form-definitions')return json(definitions)
   if(path.startsWith('/api/form-definitions/'))return json(definitions.find(d=>path.includes(d.definition_key)))
   if(path.endsWith('/classification-catalogs'))return json({material_families:[],structure_families:[],material_dimensionalities:[]})
   if(path.endsWith('/summary'))return json({version:'global-before',records:[jobResult?.records?.[0] || record()],needs_check:false})
   if(path.endsWith('/field-detail'))return json({record:jobResult?.records?.[0] || record(),review_token:'review',source_state:'empty',approval_state:'modification_required'})
   if(path.endsWith('/manual-context'))return json({version:'manual-field-v1:fixture',record:record()})
   if(path.includes('/manual/')){
    if(req.method()==='GET')return json({data:manual})
    order.push('manual-save');manual={...manual,...req.postDataJSON()};return json({data:manual})
   }
   if(path.endsWith('/draft-state'))return json({version:'global-before',draft})
   if(path==='/api/rag/evidence/draft' && req.method()==='PATCH'){
    const body=req.postDataJSON()
    assert.ok(body.field_scope===true || !order.includes('job'));assert.equal(body.changes.length,1)
    assert.equal(body.changes[0].path.at(-1),'mu_star')
    property.payload.parameters.mu_star=body.changes[0].value
    order.push('value-save');return json({changed:true,version:'global-after'})
   }
   if(path.endsWith('/field-input')){
    order.push('field-input')
    return json({version:'field-v1',field_token:'field-v1',records:[record()],needs_check:true})
   }
   if(path.endsWith('/jobs') && req.method()==='POST'){
    const body=req.postDataJSON()
    assert.deepEqual(body.retry_keys,[item]);assert.equal(body.expected_field_token,'field-v1')
    assert.equal(body.expected_draft_version,undefined)
    assert.equal(manual.reason,'最新理由');assert.equal(property.payload.parameters.mu_star,.12)
    order.push('job');return json({id:'job177',status:'queued',timeout_seconds:60})
   }
   if(path.endsWith('/jobs/job177')){
    if(req.method()==='DELETE'){order.push('cancel');return json({status:'cancelled'})}
    await jobWait
    return json(jobResult)
   }
   if(path.includes('/preparations/'))return json({percent:15})
   if(path.endsWith('/draft'))return json({data:draft})
   if(path==='/api/upload-tasks/'+task)return json({data:{task_id:task,filename:'isolated177.pdf',stage:'ready',stage_index:5,stage_total:5,processing_status:'succeeded'}})
   if(path.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:1,total:1}}})
   if(req.method()!=='GET')throw new Error('Unexpected write '+path)
   return json({items:[],jobs:[],data:[],space_groups:[],total:0})
  })
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
  await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5173')+'/upload/tasks/'+task)
  await page.getByRole('button',{name:'全部展开',exact:true}).first().click()
  await page.getByLabel('μ*',{exact:true}).fill('0.12')
  await page.locator('[data-evidence-key="'+item+'"]').first().click()
  await page.getByLabel('人工修改判断理由（必填）').fill('最新理由')
  await page.getByLabel('不提供证据',{exact:true}).check()
  await page.getByLabel('不提供证据的理由（必填）').fill('沿用原文')
  const queued=page.waitForRequest(r=>r.url().endsWith('/jobs') && r.method()==='POST')
  await page.getByRole('button',{name:'大模型核对',exact:true}).click();await queued
  const dialog=page.getByRole('dialog').filter({has:page.getByRole('progressbar')})
  await dialog.waitFor()
  let mouseBlocked=false
  try{await page.getByLabel('标题',{exact:true}).click({timeout:700})}catch{mouseBlocked=true}
  assert.equal(mouseBlocked,true)
  for(let i=0;i<4;i++){
   await page.keyboard.press('Tab')
   assert.equal(await page.evaluate(()=>Boolean(document.activeElement?.closest('[role="dialog"]'))),true)
  }
  assert.equal(await page.getByLabel('标题',{exact:true}).inputValue(),'Isolated field review')
  await page.screenshot({path:output+'/waiting-'+outcome+'.png'})
  if(outcome==='cancelled'){
   const cancelled=page.waitForResponse(r=>r.url().endsWith('/jobs/job177') && r.request().method()==='DELETE')
   await dialog.getByRole('button',{name:'取消',exact:true}).click()
   jobResult={id:'job177',status:'cancelled',records:[]};resolveJob()
   await cancelled
  }else{
   jobResult=outcome==='failed'?{id:'job177',status:'failed',error:{message:'隔离模型技术错误'}}
    :{id:'job177',status:'completed',records:[{...record(),status:outcome,reason:outcome==='supported'?'依据成立':'当前 μ* 与原文不符',
      pending_review:false,stale:false}]}
   resolveJob()
   if(outcome==='supported')await page.getByText('核对通过，结果已保存；内容和依据不变时，提交将直接复用。',{exact:true}).waitFor()
   if(outcome==='unsupported')await page.getByText('当前 μ* 与原文不符',{exact:true}).first().waitFor()
   if(outcome==='failed')await page.getByText('隔离模型技术错误',{exact:true}).waitFor()
  }
  assert.deepEqual(order.slice(0,4),['value-save','manual-save','field-input','job'])
  assert.equal(order.filter(s=>s==='job').length,1)
  checks.push({outcome,order,mouseBlocked,keyboardTrapped:true,otherValueUnchanged:true})
  await context.close()
 }
 assert.deepEqual(errors,[])
 await writeFile(output+'/result.json',JSON.stringify({checks,errors},null,2))
}finally{await browser.close()}
