// 同一真实草稿副本对照旧/新完整页面；所有API隔离，原图来自已核验的后端只读响应。
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir, mkdtemp, rm } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import net from 'node:net'
const root=fileURLToPath(new URL('../../',import.meta.url))
const { chromium }=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const { createServer }=await import(root+'/frontend/node_modules/vite/dist/node/index.js')
const data=JSON.parse(await readFile(process.env.DIAGNOSTIC_DRAFT,'utf8'))
const originalState=JSON.parse(await readFile(process.env.DIAGNOSTIC_STATE,'utf8'))
const region=JSON.parse(await readFile(process.env.DIAGNOSTIC_REGION,'utf8'))
const definitions=JSON.parse(await readFile(root+'/backend/data/form_definitions.v1.json','utf8'))
const output=process.env.DIAGNOSTIC_OUTPUT
await mkdir(output,{recursive:true})
const baselineRef=process.env.DIAGNOSTIC_BASELINE_REF || 'f8d058cc23adf8cf771d236b5b66e8eb1d8baa2a'
const baselineCommit=execFileSync('git',['rev-parse',baselineRef],{cwd:root,encoding:'utf8'}).trim()
const baseline=execFileSync('git',['show',`${baselineCommit}:frontend/src/components/UploadTaskEditor.tsx`],{cwd:root,encoding:'utf8'})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const results=[]
try {
 for (const mode of ['baseline','current']) {
  const freePort=await new Promise(resolve=>{const probe=net.createServer();probe.listen(0,'127.0.0.1',()=>{const port=probe.address().port;probe.close(()=>resolve(port))})})
  const cache=await mkdtemp(tmpdir()+'/scwiki-diagnostic-vite-')
  const server=await createServer({root:root+'/frontend',configFile:root+'/frontend/vite.config.ts',cacheDir:cache,
   server:{host:'127.0.0.1',port:freePort,strictPort:true},
   plugins:mode==='baseline'?[{name:'diagnostic-baseline',enforce:'pre',transform(code,id){if(id.endsWith('/src/components/UploadTaskEditor.tsx'))return baseline}}]:[]})
  await server.listen()
  const port=server.httpServer.address().port
  const context=await browser.newContext({viewport:{width:1440,height:1100}})
  try {
   const user={id:2,username:'isolated-reader',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}
   await context.addInitScript(user=>{localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')},user)
   let requests=[],errors=[],measure=false
   await context.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname
    if(measure)requests.push({method:req.method(),path})
    const send=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
    if(path==='/api/auth/me')return send({user})
    if(path.endsWith('/activity'))return send({ok:true})
    if(path==='/api/form-definitions')return send(definitions)
    if(path.startsWith('/api/form-definitions/'))return send(definitions.find(d=>decodeURIComponent(path).includes(d.definition_key))||{})
    if(path==='/api/classification-catalogs')return send({material_families:data.paper.material_families||[],structure_families:[],material_dimensionalities:[]})
    if(path.endsWith('/space-groups'))return send({space_groups:[]})
    if(path.endsWith('/summary'))return send({version:'fixture',records:[],needs_check:false})
    if(path.endsWith('/draft-state'))return send({version:'fixture',draft:data})
    if(path==='/api/rag/evidence/draft'&&req.method()==='PATCH')return send({version:'fixture-2',changed:true})
    if(path.endsWith('/draft'))return send({data})
    if(path===`/api/upload-tasks/${originalState.task_id}`)return send({data:originalState})
    if(path.endsWith('/parsing'))return send({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:2,total:2},next_poll_ms:null}})
    if(path==='/api/rag/evidence/region'){
     const body=req.postDataJSON();assert.equal(body.block_id,region.request.block_id);assert.equal(body.file_id,region.request.file_id)
     return send(region.response)
    }
    if(req.method()!=='GET'){errors.push(req.method()+' '+path);return send({})}
    return send({items:[],total:0})
   })
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
   await page.goto(`http://127.0.0.1:${port}/upload/tasks/${originalState.task_id}`)
   const input=page.locator('[data-issue-field="paper.volume"] input').first()
   await input.waitFor({timeout:60000});await page.waitForTimeout(1200)
   if(mode==='current'){
    await page.getByText('解析来源检查',{exact:true}).waitFor()
    assert.equal(await page.locator('[data-diagnostic-region]').count(),0)
    await page.screenshot({path:output+'/current-overview.png'})
    await page.locator('[data-parsing-diagnostics]').screenshot({path:output+'/current-panel.png'})
    await page.getByRole('button',{name:'查看本类代表例'}).first().click()
    assert.equal(await page.locator('[data-diagnostic-region]').count(),1)
    await page.getByRole('button',{name:'查看原 PDF 区域',exact:true}).click()
    await page.locator('[data-diagnostic-region] img').first().waitFor()
    await page.screenshot({path:output+'/current-original.png'})
    await page.getByRole('button',{name:'收起本类'}).click()
   } else {
    await page.getByText('查看来源差异',{exact:true}).click()
    await page.screenshot({path:output+'/baseline.png'})
   }
   // 等待展开/收起按钮的真实点击涟漪结束，再测量字段输入本身的影响。
   await page.waitForFunction(()=>document.querySelectorAll('.MuiTouchRipple-ripple').length===0)
   await page.evaluate(()=>{
    window.delays=[];window.scans=0;window.diagMutations=0;window.mutationDetails=[]
    const old=Element.prototype.querySelectorAll
    Element.prototype.querySelectorAll=function(s){if(this.hasAttribute('data-evidence-scope')&&s==='[data-issue-field]')window.scans++;return old.call(this,s)}
    const panel=document.querySelector('[data-parsing-diagnostics]')
    if(panel)new MutationObserver(list=>{window.diagMutations+=list.length;window.mutationDetails.push(...list.map(m=>({type:m.type,target:m.target.outerHTML?.slice(0,500),attribute:m.attributeName})))}).observe(panel,{subtree:true,childList:true,characterData:true,attributes:true})
    document.addEventListener('keydown',e=>{if(!e.target.closest('[data-issue-field="paper.volume"]')||e.key.length!==1)return;const now=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>window.delays.push(performance.now()-now)))},true)
   })
   const dom=await page.locator('*').count();await input.click();await input.press('End');measure=true
   await input.pressSequentially(' check123456',{delay:80});await page.waitForTimeout(200);measure=false
   const metrics=await page.evaluate(()=>({delays:window.delays,scans:window.scans,diagMutations:window.diagMutations,mutationDetails:window.mutationDetails}))
   const result={mode,field:'paper.volume',baselineCommit,dom,...metrics,requests,errors};results.push(result)
   await writeFile(output+'/results.json',JSON.stringify(results,null,2))
   assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);assert.equal(metrics.scans,0)
   if(mode==='current')assert.equal(metrics.diagMutations,0)
  } finally {await context.close();await server.close();await rm(cache,{recursive:true,force:true})}
 }
 await writeFile(output+'/results.json',JSON.stringify(results,null,2))
 console.log(JSON.stringify(results))
} finally {await browser.close()}
