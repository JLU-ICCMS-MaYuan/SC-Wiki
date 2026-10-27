// 正式UI/HTTP/数据库：来源相同但材料签名过期；仅使用隔离测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend='http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 let failRevalidation=false;
 await context.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});
   if(url.pathname.endsWith('/revalidate') && req.method()==='POST'){
     if(failRevalidation){failRevalidation=false;return route.fulfill({status:409,json:{detail:{message:'内容或谱版本已变化，请刷新后重试'}}})}
     await new Promise(resolve=>setTimeout(resolve,300));
   }
   const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true});
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{const file='revalidation-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!await page.locator('.editor-app').count()});report.screenshots.push(file)};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async p=>{const r=await fetch(backend+p);assert.equal(r.status,200);return r.json()};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const recover=async()=>{await btn('核对材料条件并继续编辑').click();await page.getByRole('dialog',{name:'核对这条谱的材料条件'}).waitFor();await btn('确认属于当前材料并继续编辑').click();await page.getByRole('application').waitFor()};
 try{
   const data=await listing(),alpha=data.items.find(i=>i.result.curves[0].kind==='alpha2f'),dos=data.items.find(i=>i.result.curves[0].kind==='phonon_dos');
   assert.deepEqual(alpha.stale_reasons,['state_changed']);assert.deepEqual(dos.stale_reasons,['state_changed']);
   await page.goto(address(alpha));await btn('核对材料条件并继续编辑').waitFor();
   assert(await btn('编辑').isDisabled());assert(await btn('重新计算').isDisabled());
   assert.equal(await page.getByText(/幅值标定待核对/).count(),0);
   assert((await page.getByText('材料条件待重新核对，请点击“核对材料条件并继续编辑”。',{exact:true}).count())>=1);
   await shot('stale-with-action');check('原图相同但材料签名过期时显示具体原因及可用恢复入口，幅值提示不冒充禁用原因');

   await btn('核对材料条件并继续编辑').click();const dialog=page.getByRole('dialog',{name:'核对这条谱的材料条件'});await dialog.waitFor();
   assert((await dialog.innerText()).includes('H3S'));assert((await dialog.innerText()).includes('200'));assert((await dialog.innerText()).includes('合成原图'));
   await page.waitForFunction(()=>{
     let node=document.querySelector('[aria-labelledby="revalidate-material-title"]');
     if(!node)return false;
     while(node){if(Number(getComputedStyle(node).opacity)<.99)return false;node=node.parentElement}
     return true;
   });
   await shot('confirm-dialog');await btn('取消').click();assert.equal(report.writes.length,0);
   assert.equal((await listing()).items.find(i=>i.id===alpha.id).run.id,alpha.run.id);
   check('确认窗口展示当前材料/原图说明，取消不产生任何写入');

   failRevalidation=true;await btn('核对材料条件并继续编辑').click();await btn('确认属于当前材料并继续编辑').click();
   await dialog.getByRole('alert').filter({hasText:/版本已变化/}).waitFor();assert.equal(await page.getByRole('application').count(),0);
   assert.equal((await listing()).items.find(i=>i.id===alpha.id).run.id,alpha.run.id);
   await btn('取消').click();check('恢复提交发生版本冲突时保留对话框，不打开错误数据或覆盖谱');

   await btn('核对材料条件并继续编辑').click();const before=report.writes.length;
   await btn('确认属于当前材料并继续编辑').click();await btn('正在确认…').waitFor();assert(await btn('正在确认…').isDisabled());
   await btn('正在确认…').evaluate(el=>el.click());await page.getByRole('application').waitFor();assert.equal(report.writes.length-before,1);
   let current=(await listing()).items.find(i=>i.id===alpha.id);
   assert.equal(current.stale,false);assert.deepEqual(current.result.curves,alpha.result.curves);assert.deepEqual(current.result.calibration,alpha.result.calibration);
   assert.deepEqual(current.review,{});assert.equal(current.result.quality.integrals.raw.status,'unavailable');
   assert.equal(current.result.state_revalidation.base_run_id,alpha.run.id);
   assert(page.url().includes(current.run.id));await shot('alpha-editor-unlocked');
   check('显式确认后新建版本并自动打开编辑器，全部曲线/标定保持不变，重复点击受限');

   await btn('← 返回详情').click();await ready();await page.reload();await ready();
   assert(await btn('重新计算').isEnabled());assert.equal(await btn('核对材料条件并继续编辑').count(),0);
   assert.equal(await page.getByText(/幅值标定待核对/).count(),0);
   check('刷新仍保持恢复后的新版本，幅值依据缺失时编辑和重算按钮可用');

   await btn('编辑').click();await page.getByRole('application').waitFor();
   await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('8');await btn('应用坐标到此点').click();
   await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready();
   current=(await listing()).items.find(i=>i.id===alpha.id);
   assert.equal(current.result.curves[0].points[50].reconstructed_amplitude,8);
   const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready();
   current=(await listing()).items.find(i=>i.id===alpha.id);assert(current.result.quality.recalculations.alpha2f);
   assert.equal(current.result.quality.integrals.raw.status,'unavailable');
   check('恢复后可以真实编辑保存并主动重算，科学依据不足返回原因而非锁死操作');

   await page.goto(address(dos));await btn('核对材料条件并继续编辑').waitFor();
   await page.setViewportSize({width:390,height:844});await recover();
   assert(page.url().includes((await listing()).items.find(i=>i.id===dos.id).run.id));
   await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('dos-mobile-editor');
   current=(await listing()).items.find(i=>i.id===dos.id);assert.deepEqual(current.result.curves,dos.result.curves);
   await btn('← 返回详情').click();await ready();assert(await btn('重新计算').isEnabled());await shot('dos-mobile-detail');
   check('声子DOS使用相同恢复流程，分波点逐项保持，390px确认/编辑/详情均可操作');

   const history=await api('/api/rag/spectra/'+alpha.id+'/runs/'+alpha.run.id+'?'+query);
   assert.deepEqual(history.result.curves,alpha.result.curves);
   assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(revalidate|manual|recalculate)$/.test(w.path)));
   check('旧运行保留，浏览器无脚本错误，写入均限于隔离恢复/保存/重算路由');
   report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'revalidation-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
