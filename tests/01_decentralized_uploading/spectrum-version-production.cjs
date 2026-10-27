// 普通查看自动追新验收：保留真实HTTP并发保护，全部API仅进入隔离测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend=process.env.SPECTRUM_TEST_BACKEND||'http://127.0.0.1:8197',frontend=process.env.SPECTRUM_FRONTEND||'http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets/full-verification');
const report={checks:[],findings:[],errors:[],writes:[],screenshots:[]};
async function main(){
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 let failNext=null;
 await context.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});
   const fail=failNext && req.method()==='POST' && url.pathname.endsWith(failNext.endpoint)?failNext:null;
   if(fail)failNext=null;
   if(fail?.stage==='before')return route.abort('failed');
   const response=await route.fetch({url:backend+url.pathname+url.search});
   if(fail?.stage==='after')return route.abort('failed');
   return route.fulfill({response});
 });
 const page=await context.newPage(),other=await context.newPage();
 for(const p of [page,other]){p.setDefaultTimeout(15000);p.on('pageerror',e=>report.errors.push(e.message))}
 const btn=(p,name)=>p.getByRole('button',{name,exact:true});
 const check=name=>{report.checks.push(name);console.log('PASS',name)};

 const shot=async(p,name)=>{const file='version-'+name+'.png';await p.screenshot({path:path.join(out,file),fullPage:true});report.screenshots.push(file)};
 const api=async(p)=>{const r=await fetch(backend+p);assert.equal(r.status,200);return r.json()};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=async p=>{await btn(p,'编辑').waitFor();await p.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled})};
 const recalc=async p=>{const old=p.url();await btn(p,'重新计算').click();await p.waitForURL(u=>u.href!==old);await ready(p)};
 const automaticLatest=async(p,expected)=>{
   await ready(p);await p.waitForURL(u=>u.searchParams.get('run')===new URL(expected).searchParams.get('run'));
   assert.equal(await p.getByRole('link',{name:'打开最新结果',exact:true}).count(),0);
   assert.equal(await p.getByText('谱版本已变化，请打开最新结果。',{exact:true}).count(),0);
 };
 try{
  let data=await listing(),alpha=data.items.find(i=>i.result.curves[0].kind==='alpha2f');
  const originalUrl=address(alpha);
  await page.goto(originalUrl);await ready(page);await page.reload();await ready(page);
  assert.equal(page.url(),originalUrl);
  check('版本未变化：刷新当前α²F详情正常，地址不变');
  await other.goto(originalUrl);await ready(other);
  await recalc(page);const newUrl=page.url();await page.reload();await ready(page);assert.equal(page.url(),newUrl);
  check('本页主动重算→新版本地址→刷新正常');
  const countBefore=report.writes.length;
  await other.reload();await automaticLatest(other,newUrl);assert.equal(other.url(),newUrl);await shot(other,'auto-latest-after-refresh');
  assert.equal(report.writes.length,countBefore);
  check('另一标签页重算后，旧页刷新自动使用最新版本和URL，无额外选择或写请求');
  await page.goto(originalUrl);await automaticLatest(page,newUrl);
  assert.equal(report.writes.length,countBefore);
  check('重用旧链接自动恢复同一谱最新结果，无恢复按钮');

  // 人工保存使用真编辑器，检查生成的新地址刷新稳定。
  await btn(page,'编辑').click();await page.getByRole('application').waitFor();
  await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.08');await btn(page,'应用坐标到此点').click();
  await btn(page,'保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready(page);
  const savedUrl=page.url();await page.reload();await ready(page);assert.equal(page.url(),savedUrl);
  const saved=(await listing()).items.find(i=>i.id===alpha.id);assert.equal(saved.result.curves[0].points[50].reconstructed_amplitude,.08);
  check('本页编辑保存→新版本地址→刷新正常，人工点持久化');
  await other.reload();await automaticLatest(other,savedUrl);
  check('另一标签页人工保存后，旧地址刷新直接恢复最新结果');

  // 编辑器打开后竞争写入，必须保持未保存输入。
  await btn(other,'编辑').click();await other.getByRole('application').waitFor();
  await other.locator('[data-row="a:p50"]').click();await other.getByLabel('选中点幅值').fill('0.09');await btn(other,'应用坐标到此点').click();
  await recalc(page);
  await btn(other,'保存调整').click();await other.getByRole('alert').filter({hasText:'保存失败'}).waitFor();
  assert.equal(await other.getByLabel('选中点幅值').inputValue(),'0.09');assert(await other.getByRole('application').isVisible());
  assert.equal((await listing()).items.find(i=>i.id===alpha.id).result.curves[0].points[50].reconstructed_amplitude,.08);
  await shot(other,'unsaved-conflict-preserved');
  check('跨标签页版本冲突拒绝旧保存，保留用户未保存坐标且不覆盖已保存谱');
  await btn(other,'← 返回详情').click();await btn(other,'放弃修改').click();

  // 请求发送前失败不应生成运行；本页保持可重试。
  let current=(await listing()).items.find(i=>i.id===alpha.id);
  const currentRun=current.run.id;
  failNext={endpoint:'/recalculate',stage:'before'};
  await btn(page,'重新计算').click();await page.getByRole('alert').waitFor();
  assert.equal((await listing()).items.find(i=>i.id===alpha.id).run.id,currentRun);
  await ready(page);await recalc(page);
  check('重算请求发送前网络失败不产生新运行，重试成功');

  // 服务端成功但响应丢失：当前协议不具幂等恢复，必须记录为体验限制。
  current=(await listing()).items.find(i=>i.id===alpha.id);
  failNext={endpoint:'/recalculate',stage:'after'};
  await btn(page,'重新计算').click();await page.getByRole('alert').waitFor();
  const persisted=(await listing()).items.find(i=>i.id===alpha.id);assert.notEqual(persisted.run.id,current.run.id);
  await btn(page,'重新计算').click();await page.getByRole('alert').filter({hasText:/版本已变化/}).waitFor();
  const writesBeforeRecovery=report.writes.length;
  await page.reload();await automaticLatest(page,address(persisted));await shot(page,'lost-response-refresh');
  assert.equal(report.writes.length,writesBeforeRecovery);
  check('响应丢失后刷新自动恢复服务端已保存运行，不重复提交计算');


  // DOS使用同一正式路由，重复刷新/陈旧链接测试。
  const dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos'),dosUrl=address(dos);
  await page.goto(dosUrl);await ready(page);await other.goto(dosUrl);await ready(other);
  await recalc(page);await page.reload();await ready(page);
  await other.reload();await automaticLatest(other,page.url());
  assert.equal(page.url(),other.url());check('声子DOS跨页旧版本同样自动恢复当前结果');
  await other.setViewportSize({width:390,height:844});await other.goto(dosUrl);await automaticLatest(other,page.url());
  await other.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot(other,'mobile-auto-latest');
  check('窄屏旧链接自动恢复结果，无额外选择或水平溢出');

  // 故意错误身份必须继续拒绝，不能以自动追新掩盖权限/材料错误。
  const u=new URL(page.url());u.searchParams.set('state_key','wrong-state');
  await page.goto(u.href);await page.getByRole('alert').filter({hasText:/不可访问/}).waitFor();
  assert.equal(await btn(page,'编辑').count(),0);check('材料身份不匹配被拒绝，没有打开其他材料或可写编辑器');
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));
  report.status='passed';report.acceptance='auto-latest-refresh-verified';report.note='仅自动恢复同身份普通查看；编辑冲突和身份校验继续保留。';
 }catch(error){report.status='failed';report.failure=error.stack;await shot(page,'failure');throw error}
 finally{fs.writeFileSync(path.join(out,'version-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
