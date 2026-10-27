// 正式React/HTTP/数据库路径；所有API重定向到本次专用测试服务，禁止业务API写入。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend='http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],writes:[],errors:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname,fields:Object.keys(req.postDataJSON()),base_run_id:req.postDataJSON().base_run_id,kind:req.postDataJSON().kind});
   if(url.pathname.endsWith('/recalculate'))await new Promise(r=>setTimeout(r,350));
   const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response});
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const btn=name=>page.getByRole('button',{name,exact:true});
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});return {status:r.status,data:await r.json()}};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const listing=async()=> (await api('/api/rag/spectra?'+query)).data;
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const shot=async name=>{const file='recalculate-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:true});report.screenshots.push(file)};
 const ready=async()=>{await btn('重新计算').waitFor();await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='重新计算')?.disabled)};
 const calculate=async()=>{const oldUrl=page.url();await btn('重新计算').click();await page.waitForURL(url=>url.href!==oldUrl);await ready()};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const confirmZero=async()=>{if(await btn('确认蓝色零频线与原图一致').isEnabled())await btn('确认蓝色零频线与原图一致').click();await page.locator('[data-row="a:p0"]').click();await btn('确认选中点为零频点').click()};
 try{
  const initial=await listing(),alpha=initial.items.find(i=>i.result.curves[0].kind==='alpha2f');
  await page.goto(address(alpha));await ready();
  const beforeWrites=report.writes.length,oldUrl=page.url();
  await btn('重新计算').click();const busy=btn('计算中…');await busy.waitFor();assert(await busy.isDisabled());await busy.evaluate(el=>el.click());
  await page.waitForURL(url=>url.href!==oldUrl);await ready();assert.equal(report.writes.length-beforeWrites,1);
  let current=(await listing()).items.find(i=>i.id===alpha.id),raw=current.result.quality.integrals.raw;
  assert.equal(raw.parameters.lambda.status,'available');assert.equal(raw.parameters.omega_log.status,'available');
  assert.deepEqual(current.result.curves,alpha.result.curves);assert.deepEqual(current.review,{});
  assert.equal(await page.getByText(/本版本计算时间/).count(),0);assert.equal(await page.getByText(/参考来源：/).count(),0);
  assert.equal(await page.getByText('04 · 逐点数据核对',{exact:true}).count(),0);assert.equal(await page.getByText(/为什么零频完成/).count(),0);
  check('α²F主动计算真实持久化且不改点，计算中防重复提交，详情移除旧说明和04表');
  await page.reload();await ready();assert.equal(await page.getByText(/本版本计算时间/).count(),0);assert.equal(await page.getByText(/参考来源：/).count(),0);check('刷新恢复计算记录，03不展示时间或原始来源');

  await btn('编辑').click();await page.getByRole('application').waitFor();
  assert(await page.getByText('逐点数据',{exact:true}).isVisible());
  await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.08');await btn('应用坐标到此点').click();
  await confirmZero();await save();
  assert.equal(await page.getByText('零频位置核对完成',{exact:true}).count(),1);
  assert.equal(await page.getByText(/本版本计算时间/).count(),0);
  current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.status,'unavailable');assert(!current.result.quality.recalculations);
  await calculate();current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  await shot('alpha-result');check('人工保存使旧结果失效，点击重算才得到新积分；零频只显示一次，编辑器仍保留点表');

  await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.locator('summary').filter({hasText:'坐标标定'}).click();
  await page.getByLabel('幅值单位',{exact:true}).selectOption('pixel');
  await page.getByLabel('幅值标定依据',{exact:true}).fill('合成测试原图：幅值零基线y=80；整条线使用统一线性正倍率，绝对倍率未知。');
  await btn('应用标定').click();await confirmZero();await save();await calculate();
  current=(await listing()).items.find(i=>i.id===alpha.id);raw=current.result.quality.integrals.raw;
  assert.equal(raw.parameters.lambda.status,'unavailable');assert.equal(raw.parameters.omega_log.status,'available');
  await page.getByText(/λ：λ需要α²F绝对幅值刻度/).waitFor();await shot('relative-omega');
  check('有零基线和统一倍率依据的相对谱只显示ωlog，不伪造λ');

  await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.locator('[data-row="a:p50"]').click();await btn('删除选中点').click();await save();
  current=(await listing()).items.find(i=>i.id===alpha.id);const points=JSON.stringify(current.result.curves);
  await calculate();current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.status,'unavailable');assert(current.result.quality.integrals.raw.reason.includes('缺口'));
  assert.equal(JSON.stringify(current.result.curves),points);await page.getByText(/λ、ωlog：曲线存在缺口/).waitFor();check('删点保留缺口，重算显示具体阻塞原因，不跨缺口补点或积分');

  const dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');
  await page.goto(address(dos));await ready();await calculate();
  let updated=(await listing()).items.find(i=>i.id===dos.id);
  assert.equal(updated.result.quality.dos_mode_integral.status,'available');
  assert.equal(updated.result.quality.dos_mode_integral.comparison_status,'unavailable');
  assert(updated.result.quality.dos_mode_integral.integral>0);assert.deepEqual(updated.result.curves,dos.result.curves);
  await page.getByText(/缺少原胞原子数或每原胞绝对密度依据/).waitFor();await shot('dos-result');
  check('DOS同样主动积分，有积分但缺原胞依据时仅3N比较留空');

  const latest=await listing(),item=latest.items.find(i=>i.id===dos.id);
  const race=await api('/api/rag/spectra/'+item.id+'/recalculate',{...target,expected_version:latest.version,expected_collection_version:item.version,base_run_id:item.run.id,kind:'phonon_dos'});
  assert.equal(race.status,200);
  await btn('重新计算').click();await page.getByRole('alert').filter({hasText:/版本已变化/}).waitFor();
  assert.equal((await listing()).items.find(i=>i.id===dos.id).run.id,race.data.items.find(i=>i.id===dos.id).run.id);
  check('并发新版本后旧页面重算返回409，不覆盖新的结果');
  updated=(await listing()).items.find(i=>i.id===dos.id);await page.goto(address(updated));await ready();
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await btn('重新计算').scrollIntoViewIfNeeded();await shot('mobile-detail');
  assert(await btn('重新计算').isVisible());check('390px窄屏无水平溢出，重算按钮可操作');
  assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));assert.deepEqual(report.errors,[]);
  report.status='passed';report.database='isolated SQLite; production routes and SQLAlchemy; all browser API traffic redirected';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'recalculate-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
