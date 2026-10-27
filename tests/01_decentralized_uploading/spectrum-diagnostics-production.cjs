// 正式React与HTTP/SQLite；所有API重定向测试服务，不写真实业务谱。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend='http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true});
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{const file='diagnostics-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!(await page.locator('.editor-app').count())});report.screenshots.push(file)};
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const recalc=async()=>{const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const seed=async(item,kind,cid)=>{
   const data=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
   const doc=data.documents.find(d=>d.curves[0].id===cid),points=doc.curves[0].points;
   points[50].breakBefore=true;points[51].breakBefore=true;
   if(kind==='alpha2f')points[92].joinTo=points[90].id;
   return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:data.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id)
 };
 const locate=async(cid,pid)=>{
   const button=page.locator('[data-diagnostic-curve="'+cid+'"][data-diagnostic-point="'+pid+'"]').first();
   await button.click();await page.getByRole('application').waitFor();
   const row=page.locator('[data-row="'+pid+'"]');assert.equal(await row.getAttribute('aria-selected'),'true');
   const canvas=page.getByRole('application');
   const centered=await canvas.evaluate((el,id)=>{
     const p=el.querySelector('[data-point="'+id+'"]'),v=el.viewBox.baseVal;
     return {x:Number(p.dataset.x),y:Number(p.dataset.y),cx:v.x+v.width/2,cy:v.y+v.height/2};
   },pid);
   assert(Math.abs(centered.x-centered.cx)<1e-4 && Math.abs(centered.y-centered.cy)<1e-4,JSON.stringify(centered));
   assert(await page.getByLabel('选中点频率').isVisible());
   assert(await row.isVisible());
 };
 try{
  let data=await listing(),alpha=data.items.find(i=>i.result.curves[0].kind==='alpha2f');
  alpha=await seed(alpha,'alpha2f','a');const original=JSON.stringify(alpha.result.curves);
  await page.goto(address(alpha));await ready();await recalc();
  const diagnostics=page.getByTestId('trace-diagnostics');await diagnostics.waitFor();
  for(const kind of ['cycle','branch','isolated','disconnected'])assert(await diagnostics.locator('[data-issue-kind="'+kind+'"]').count()>0);
  assert.equal(await page.getByText('曲线存在分叉，请检查下方问题坐标',{exact:true}).count(),1);
  await shot('issues');
  check('重算分别列出闭环、分叉、孤立点和未连接片段，λ/ωlog共用诊断');
  const beforeWrites=report.writes.length;await locate('a','a:p50');await shot('isolated-focus');
  assert.equal(report.writes.length,beforeWrites);await btn('← 返回详情').click();await ready();
  assert.equal(JSON.stringify((await listing()).items.find(i=>i.id===alpha.id).result.curves),original);
  check('点击孤立坐标自动打开编辑器、放大居中并选中正确点，返回不写数据');
  const loopId=await diagnostics.locator('[data-issue-kind="cycle"] [data-diagnostic-point]').first().getAttribute('data-diagnostic-point');
  await locate('a',loopId);await btn('← 返回详情').click();await ready();
  check('闭环实际连接坐标可定位环内点，无误选邻近点');
  await locate('a','a:p50');await btn('删除选中点').click();assert.equal(await page.locator('[data-row="a:p50"]').count(),0);
  await btn('↶ 撤销').click();assert.equal(await page.locator('[data-row="a:p50"]').count(),1);
  await btn('↷ 重做').click();await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready();
  assert.equal(await page.getByTestId('trace-diagnostics').count(),0);
  await recalc();assert.equal(await page.locator('[data-diagnostic-point="a:p50"]').count(),0);
  check('手动删除可撤销重做；保存清除旧诊断，重算后已删除点不再列出');

  let dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');
  dos=await seed(dos,'phonon_dos','Sc');await page.goto(address(dos));await ready();await recalc();
  await locate('Sc','Sc:p50');assert.equal(await page.locator('[data-row="La:p50"]').count(),0);
  await shot('dos-focus');await btn('← 返回详情').click();await ready();
  check('PhDOS定位打开正确Sc分波，不误选同坐标的La或H');

  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await locate('Sc','Sc:p50');await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await shot('mobile-focus');await btn('← 返回详情').click();await ready();
  check('390px窄屏坐标入口与编辑器定位可用，无页面水平溢出');

  data=await listing();dos=data.items.find(i=>i.id===dos.id);
  await api('/api/rag/spectra/'+dos.id+'/recalculate',{...target,expected_version:data.version,expected_collection_version:dos.version,base_run_id:dos.run.id,kind:'phonon_dos'});
  await page.locator('[data-diagnostic-point="Sc:p50"]').first().click();
  await page.getByRole('alert').filter({hasText:/版本已变化/}).waitFor();assert.equal(await page.locator('.editor-app').count(),0);
  check('诊断版本过期时拒绝打开编辑，不静默选择新版本的其他点');
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));
  report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'diagnostics-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
