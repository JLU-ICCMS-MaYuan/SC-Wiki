// 三入口真实组件验收：全部 API 截获，不修改真实论文，也不调用模型。
import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const base=process.env.FRONTEND_URL || 'http://127.0.0.1:5173'
const artifacts=process.env.ARTIFACT_DIR || '/tmp/scwiki-109-browser'
await mkdir(artifacts,{recursive:true})
const definitions=JSON.parse(await readFile(new URL('../../backend/data/form_definitions.v1.json',import.meta.url),'utf8'))
try {
 for(const role of ['upload','admin','superadmin']) {
  const context=await browser.newContext({viewport:{width:1440,height:900}})
  const user={id:7,username:'fixture',role:role==='upload'?'user':role,is_admin:role!=='upload',is_superadmin:role==='superadmin',is_approved:true,is_email_verified:true}
  await context.addInitScript(user=>{localStorage.setItem('auth_token','fixture');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')},user)
  let paper={id:990109,title:'Evidence fixture',year:2026,authors:['Fixture Author'],journal:'Synthetic',summary:'',paper_type:'experimental',superconductor_kind:'conventional',review_status:'approved',material_families:[{id:8,name:'单质超导体'}]}
  let states=Array.from({length:3},(_,i)=>({state_key:`s-${i}`,material_name:'Sn',material:'Sn',state_kind:'experimental',material_dimensionality:'three_dimensional',crystal_system:'tetragonal',element_count:1,pressure_value_gpa:i,property_modules:[],structure_families:[],structures:[]}))
  const source={file_id:'main',source_name:'synthetic.txt',page_start:2,quote:'Synthetic evidence only.'}
  const records=()=>[
   {key:'title',field:'paper.title',label:'标题',current_value:paper.title,status:'supported',required:false,reason:'标题与原文一致',evidences:[source]},
   {key:'summary',field:'paper.summary',label:'论文总结',current_value:null,status:'unchecked',required:false,reason:'',evidences:[]},
   ...states.map((s,i)=>({key:s.state_key,state_key:s.state_key,field:`material_states[${i}].pressure_value_gpa`,label:'压强',current_value:s.pressure_value_gpa,status:i===1?'uncertain':'supported',reason:'压力来源',evidences:[source],...(i===1?{human_confirmed:true,adopted_basis:'general_knowledge',decision:{accepted:true,actor_user_id:8,reason:'人工确认的通用知识推测',basis_kind:'general_knowledge'}}:{})})),
  ]
  let jobs=0, writes=0
  await context.route('**/api/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname,json=(body)=>route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
   if(path==='/api/auth/me')return json({user})
   if(path==='/api/form-definitions')return json(definitions)
   if(path==='/api/classification-catalogs')return json({material_families:[{id:8,name:'单质超导体'}],structure_families:[],material_dimensionalities:[]})
   if(path.endsWith('/space-groups'))return json({space_groups:[]})
   if(path.endsWith('/review-artifact'))return json({data:{}})
   if(path.endsWith('/preflight'))return json({version:'v1',needs_check:false,records:records(),sources:[]})
   if(path.endsWith('/jobs') && req.method()==='POST'){assert.equal(req.postDataJSON().purpose,'review_all');jobs++;return json({id:'job',status:'queued'})}
   if(path.endsWith('/jobs/job'))return json({id:'job',status:'completed',version:'v1',records:records()})
   if(path===`/api/admin/papers/${paper.id}`){if(req.method()==='PUT'){paper={...paper,...req.postDataJSON()};writes++}return json({...paper,material_states:states})}
   if(path.endsWith('/scientific-draft')){states=req.postDataJSON().material_states;writes++;return json({ok:true,data:{unchanged:true}})}
   if(path.endsWith('/draft')){if(req.method()==='PUT'){paper=req.postDataJSON().paper;states=req.postDataJSON().material_states;writes++}return json({ok:true,data:{paper,material_states:states,structure_candidates:[]}})}
   assert(!path.endsWith('/review')&&!path.endsWith('/submit'),'不能自动提交或批准')
   return json({items:[],total:0})
  })
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
  async function open(){
   if(role!=='upload'){await page.goto(`${base}/admin/papers/990109/edit`);return}
   await page.goto(`${base}/login`)
   await page.evaluate(async data=>{
    const {default:React}=await import('/node_modules/.vite/deps/react.js')
    const {default:ReactDOM}=await import('/node_modules/.vite/deps/react-dom_client.js')
    const {LanguageProvider}=await import('/src/context/LanguageContext.tsx')
    const {default:Editor}=await import('/src/components/UploadTaskEditor.tsx')
    document.getElementById('root').style.display='none';const host=document.createElement('main');host.style.cssText='max-width:1200px;margin:auto;padding:16px';document.body.append(host)
    ReactDOM.createRoot(host).render(React.createElement(LanguageProvider,{},React.createElement(Editor,{taskId:'a'.repeat(32),draftOverride:data,onSubmitted(){}})))
   },{paper,material_states:states,structure_candidates:[]})
  }
  await open()
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:900})
   await page.getByRole('button',{name:'全部展开',exact:true}).click()
   const empty=page.locator('[data-evidence-key="summary"]').first();await empty.waitFor();await empty.focus();await page.keyboard.press('Enter')
   const drawer=page.locator('.evidence-review-drawer')
   await drawer.getByText('暂无证据或建议',{exact:true}).waitFor()
   await page.keyboard.press('Escape');await drawer.waitFor({state:'detached'})
   const state=page.locator('[data-state-key="s-1"]'),label=state.getByRole('button',{name:'压强 (GPa)',exact:true})
   await label.scrollIntoViewIfNeeded();const before=await label.evaluate(e=>e.getBoundingClientRect().top)
   await label.focus();await page.keyboard.press('Space')
   await drawer.getByText('人工确认的通用知识推测',{exact:false}).waitFor()
   await drawer.locator('details > summary').last().click()
   await drawer.getByText('Synthetic evidence only.',{exact:false}).waitFor()
   await page.getByLabel('关闭来源详情').click();await drawer.waitFor({state:'detached'});await page.waitForTimeout(400)
   assert(Math.abs(before-await label.evaluate(e=>e.getBoundingClientRect().top))<4,'关闭不跳回顶部')
   assert.equal(await state.locator('[data-evidence-problem]').count(),0,'人工确认恢复普通样式')
   assert.equal(await page.locator('button[data-evidence-key="s-1"]').count(),0,'无顶部接受列表')
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'窄屏横向溢出')
   await page.screenshot({path:`${artifacts}/${role}-${width}.png`})
  }
  assert.equal(jobs,0,'查看侧栏不能调用模型')
  if(role==='upload'){
   const field=page.locator('[data-issue-field="paper.summary"] textarea').first()
   await field.fill('Changed current summary')
   await page.locator('[data-evidence-key="summary"]').first().click()
   await page.locator('.evidence-review-drawer').getByText('Changed current summary',{exact:true}).waitFor()
   await page.keyboard.press('Escape')
  }else{
   await Promise.all([page.waitForRequest(r=>r.url().endsWith('/jobs') && r.method()==='POST'),page.getByRole('button',{name:'进行 AI 审核',exact:true}).click()])
   await page.waitForFunction(()=>!document.querySelector('[role="dialog"]'),{},{timeout:15000})
   assert.equal(jobs,1,'已有通过结论仍启动全量审核')
  }
  await open()
  await page.getByRole('button',{name:'全部展开',exact:true}).click()
  await page.locator('[data-state-key="s-1"]').getByRole('button',{name:'压强 (GPa)',exact:true}).click()
  await page.getByText('人工确认的通用知识推测',{exact:false}).waitFor()
  assert.deepEqual(errors,[])
  console.log(JSON.stringify({role,widths:[1440,390,320],jobs,writes,approvedReopen:true,result:'passed'}))
  await context.close()
 }
}finally{await browser.close()}
