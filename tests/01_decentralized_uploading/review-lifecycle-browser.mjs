// 实际上传详情路由/完整编辑器 + 服务函数/MySQL回滚桥；HTTP适配与登录身份是隔离夹具。
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'
import { writeFile, mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const out = process.env.ARTIFACT_DIR || '/tmp/scwiki144-browser'
await mkdir(out, { recursive: true })
const bridge = spawn(process.env.PYTHON_BIN || 'python3', [new URL('./review-lifecycle-storage.py', import.meta.url).pathname], { stdio:['pipe','pipe','inherit'], env:process.env })
const waiting = []
createInterface({ input:bridge.stdout }).on('line', line => waiting.shift()?.resolve(JSON.parse(line)))
bridge.on('exit', code => waiting.splice(0).forEach(x => x.reject(new Error(`存储桥退出${code}`))))
const call = body => new Promise((resolve,reject) => { waiting.push({resolve,reject}); bridge.stdin.write(JSON.stringify(body)+'\n') })
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const requests=[],positions=[],errors=[]
let stored = await call({op:'init'}), saves=0, proposals=0, failNextProposal=false
const definitions = stored.definitions
const context=await browser.newContext({viewport:{width:1800,height:1000}})
const user={id:2,username:'fixture',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}
await context.addInitScript(user=>{localStorage.setItem('auth_token','fixture-only');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')},user)
await context.route('**/api/**',async route=>{
 const req=route.request(),path=new URL(req.url()).pathname
 requests.push({path,method:req.method(),time:Date.now()})
 const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
 if(path==='/api/auth/me')return json({user})
 if(path==='/api/form-definitions')return json(definitions)
 if(path.startsWith('/api/form-definitions/'))return json(definitions.find(d=>path.includes(encodeURIComponent(d.definition_key))))
 if(path==='/api/classification-catalogs')return json({material_families:[],structure_families:[],material_dimensionalities:[]})
 if(path.endsWith('/space-groups'))return json({space_groups:[{number:191,symbol:'P6/mmm'}]})
 if(path.endsWith('/parsing'))return json({ok:true,data:{status:'ready',stage:'ready',chunks:[],files:[],summary:{status:'completed',completed:1,total:1},next_poll_ms:null}})
 if(path.endsWith('/preflight')){stored=await call({op:'read'});return json(stored.preflight)}
 if(path.includes('/manual/'))return json({ok:true,data:{changed:false,reason:'',items:[],history:[]}})
 if(path.endsWith('/proposals')){
  if(failNextProposal){failNextProposal=false;return json({detail:'测试注入：保存失败，输入应保留'},503)}
  const result=await call({op:'proposal',body:req.postDataJSON()})
  if(result.error)return json({detail:result.error},result.status)
  stored=result;proposals++;return json(result.response)
 }
 if(path.endsWith('/draft')){
  if(req.method()==='PUT'){stored=await call({op:'save',draft:req.postDataJSON()});saves++}
  return json({ok:true,data:stored.draft})
 }
 if(path.endsWith('/jobs')&&path.includes('/evidence')){stored=await call({op:'recheck'});return json({id:'fixture',status:'completed'})}
 if(path.endsWith('/jobs/fixture'))return json({id:'fixture',status:'completed',...stored.preflight})
 if(/\/upload-tasks\/[a-f0-9]+$/.test(path))return json({ok:true,data:{task_id:'a'.repeat(32),stage:'ready',processing_status:'succeeded',stage_index:5,stage_total:5,progress:100,filename:'La–Sc–H真实草稿副本',file_kind:'pdf',can_edit:true}})
 assert(!path.endsWith('/submit')&&!path.endsWith('/review'),`禁止批准/提交：${path}`)
 return json({ok:true,items:[],total:0})
})
const page=await context.newPage()
page.on('pageerror',e=>errors.push(e.message))
page.setDefaultTimeout(20000)
const url=(process.env.FRONTEND_URL||'http://127.0.0.1:5173')+'/upload/tasks/'+'a'.repeat(32)
const waitSaveIdle=async()=>{
 for(let i=0;i<60;i++){
  if(await page.getByRole('button',{name:'立即保存',exact:true}).isEnabled())return
  await page.waitForTimeout(500)
 }
 assert.fail('草稿保存及核对刷新未结束')
}
try{
 await page.goto(url)
 await page.getByRole('button',{name:'全部展开',exact:true}).first().click()
 const stateKey=stored.draft.material_states.find(s=>s.pressure_value_gpa===250).state_key
 const area=page.locator(`[data-state-key="${stateKey}"]`)
 const module=area.getByTestId('property-module-superconductive_properties')
 const summary=module.locator('summary').first()
 if(await summary.count()&&!(await summary.evaluate(el=>el.parentElement.open)))await summary.click()
 const add=area.getByRole('button',{name:'添加 Tc／μ* 组合'}).first()
 await add.waitFor();await add.scrollIntoViewIfNeeded();await page.waitForTimeout(500)
 const conditionLabels=()=>area.locator('[data-scientific-field-key^="sscha."]')
 const inspect=async stage=>{
  await conditionLabels().first().waitFor({timeout:30000})
  await conditionLabels().first().locator('[data-evidence-key]').waitFor({timeout:30000})
  const labels=await conditionLabels().evaluateAll(ns=>ns.map(n=>({label:n.textContent,red:n.dataset.evidenceProblem==='true'})))
  assert.equal(labels.length,8,`${stage}:必须检查8项实际SSCHA字段`)
  assert(labels.every(x=>!x.red),`${stage}: ${JSON.stringify(labels)}`)
  positions.push({stage,url:page.url(),position:await page.evaluate(()=>({scrollY,active:document.activeElement?.getAttribute('aria-label'),value:document.activeElement?.value})),labels})
  assert.equal(page.url(),url)
 }
 await inspect('initial')
 await add.click()
 const point=area.getByRole('group',{name:'第2组 Tc 与 μ*',exact:true})
 await point.getByLabel('Tc',{exact:true}).fill('296')
 await point.getByLabel('μ*',{exact:true}).fill('0.16')
 await page.waitForTimeout(250)
 await inspect('add-pair')
 assert(await point.getByLabel('μ*',{exact:true}).evaluate(el=>el===document.activeElement),'新增输入后不得丢失焦点')
 const inputPosition=await page.evaluate(()=>({scrollY,active:document.activeElement?.getAttribute('aria-label')}))
 // 等待自动保存完成，不能点击页顶保存按钮制造测试自身的滚动。
 for(let i=0;i<30&&!saves;i++)await page.waitForTimeout(1000)
 await page.waitForTimeout(1000)
 await inspect('autosaved')
 assert(saves>0,'必须经过真实草稿持久化桥')
 assert(Math.abs((await page.evaluate(()=>scrollY))-inputPosition.scrollY)<5,'自动保存不能跳离输入位置')
 assert(await point.getByLabel('μ*',{exact:true}).evaluate(el=>el===document.activeElement),'自动保存后输入焦点保持')
 // 整页刷新再打开；保存字段资格仍需重新从MySQL读取。
 await page.reload();await page.getByRole('button',{name:'全部展开',exact:true}).first().click()
 if(await summary.count()&&!(await summary.evaluate(el=>el.parentElement.open)))await summary.click()
 await add.waitFor();await page.waitForTimeout(600);await inspect('reopen')
 const software=conditionLabels().filter({hasText:'计算软件'}).first()
 await software.scrollIntoViewIfNeeded();await page.waitForTimeout(400)
 const before=await software.evaluate(el=>el.getBoundingClientRect().top)
 await software.locator('[data-evidence-key]').click()
 await page.getByRole('button',{name:'完成',exact:true}).click()
 await page.locator('.evidence-review-drawer').waitFor({state:'hidden'})
 await page.waitForTimeout(700)
 const after=await software.evaluate(el=>el.getBoundingClientRect().top)
 assert(Math.abs(before-after)<5,`关闭后位置变化：${before} -> ${after}`)
 assert(proposals>0,'完成须实际调用后台保存校验')
 await inspect('complete')
 // 删除原331承载点，保留296点：共用条件不因旧record_key消失而失效。
 const savesBeforeDelete=saves
 await area.getByRole('button',{name:'删除第1组组合',exact:true}).click()
 await page.waitForTimeout(500)
 await inspect('delete-first-point')
 for(let i=0;i<30&&saves===savesBeforeDelete;i++)await page.waitForTimeout(1000)
 assert(saves>savesBeforeDelete)
 await waitSaveIdle()
 await inspect('delete-first-point-saved')
 // 200 GPa SSCHA：首次保存请求失败，保留输入并通过现有重试恢复。
 const key200=stored.draft.material_states.find(s=>s.pressure_value_gpa===200).state_key
 const software200=page.locator(`[data-state-key="${key200}"] [data-scientific-field-key="sscha.calculation_code"]`)
 await software200.locator('[data-evidence-key]').click()
 failNextProposal=true
 await page.getByRole('button',{name:'完成',exact:true}).click()
 await page.getByRole('button',{name:'重试保存',exact:true}).waitFor({timeout:30000})
 await page.getByRole('button',{name:'重试保存',exact:true}).click()
 await page.waitForTimeout(1000)
 await page.getByLabel('关闭来源详情').click()
 await page.waitForTimeout(600)
 assert.notEqual(await software200.getAttribute('data-evidence-problem'),'true')
 positions.push({stage:'200-GPa-retry',url:page.url(),proposals})
 // 普通物性名称编辑：保存成功，数值与科学争议不被本测试采纳或替换。
 const dosState=stored.draft.material_states.find(s=>(s.property_modules||[]).some(m=>m.records.some(r=>r.property_code==='dos_fermi'&&r.value_raw==='17.27')))
 const dosArea=page.locator(`[data-state-key="${dosState.state_key}"]`)
 const dosModule=dosArea.getByTestId('property-module-electronic_properties')
 const dosSummary=dosModule.locator('summary').first()
 if(await dosSummary.count()&&!(await dosSummary.evaluate(el=>el.parentElement.open)))await dosSummary.click()
 const nameInput=dosModule.locator('[data-issue-field$=".name_raw"] input').first()
 const beforeSaves=saves
 await nameInput.fill('N(EF)')
 for(let i=0;i<30&&saves===beforeSaves;i++)await page.waitForTimeout(1000)
 assert(saves>beforeSaves,'N(EF)名称必须成功持久化')
 const savedDos=stored.draft.material_states.find(s=>s.state_key===dosState.state_key).property_modules.flatMap(m=>m.records).find(r=>r.property_code==='dos_fermi')
 assert.equal(savedDos.name_raw,'N(EF)');assert.equal(savedDos.value_raw,'17.27');assert.equal(savedDos.value_number,null)
 positions.push({stage:'N-EF-name-save',url:page.url(),value:savedDos.value_raw,name:savedDos.name_raw})
 stored=await call({op:'recheck'})
 await page.reload();await page.getByRole('button',{name:'全部展开',exact:true}).first().click()
 if(await summary.count()&&!(await summary.evaluate(el=>el.parentElement.open)))await summary.click()
 await add.waitFor();await page.waitForTimeout(600);await inspect('recheck-failure-preserves-proof')
 assert.deepEqual(errors,[])
 await page.screenshot({path:out+'/final.png',fullPage:true})
 await writeFile(out+'/results.json',JSON.stringify({saves,proposals,positions,requests,errors,http:'隔离适配',storage:'真实MySQL外层事务回滚'},null,2))
 console.log(JSON.stringify({passed:positions.length,saves,proposals,out}))
}catch(error){await page.screenshot({path:out+'/failure.png',fullPage:true});await writeFile(out+'/failure.html',await page.content());await writeFile(out+'/failure.json',JSON.stringify({error:String(error),positions,requests,errors},null,2));throw error}
finally{await browser.close();bridge.stdin.end(JSON.stringify({op:'close'})+'\n')}
