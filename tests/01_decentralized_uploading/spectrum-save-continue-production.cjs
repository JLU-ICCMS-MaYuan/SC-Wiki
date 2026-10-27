// #161：实际本地前端 + 隔离正式HTTP/SQLite，验证连续元素保存的共享版本。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8198',frontend='http://127.0.0.1:5173',out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
assert(out);fs.mkdirSync(out,{recursive:true});
const report={checks:[],errors:[],saves:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 let failNext=false,delayNext=false;
 await context.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),save=req.method()==='POST'&&u.pathname.endsWith('/manual');
  if(save&&failNext){failNext=false;return route.abort('failed')}
  if(save&&delayNext){delayNext=false;await new Promise(r=>setTimeout(r,500))}
  const response=await route.fetch({url:backend+u.pathname+u.search});
  if(save&&response.status()===200){
   const body=req.postDataJSON(),json=await response.json(),item=json.items.find(i=>u.pathname.includes(i.id));
   report.saves.push({curve:body.document.curves[0].id,request_version:body.expected_collection_version,request_run:body.base_run_id,result_version:item.version,result_run:item.run.id});
  }
  await route.fulfill({response});
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true}),editor=page.locator('.editor-app'),modal=page.getByRole('dialog',{name:'保留这次调整吗？'});
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});report.screenshots.push(name+'.png')};
 const query='target=upload&target_id=manual-test';
 const listing=async()=>{const r=await fetch(backend+'/api/rag/spectra?'+query);assert.equal(r.status,200);return r.json()};
 const address=i=>frontend+'/spectra/'+i.id+'?'+query+'&'+new URLSearchParams({state_key:i.state_key,collection_version:i.version,run:i.run.id,curve:i.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const active=async name=>{assert(await btn(name).evaluate(e=>e.classList.contains('active')))};
 const edit=async(name,value)=>{await editor.locator('[data-row="'+name+':p50"]').click();await page.getByLabel('选中点幅值',{exact:true}).fill(String(value));await btn('应用坐标到此点').click()};
 const selectValue=async(name,value)=>{await btn(name).click();await active(name);await editor.locator('[data-row="'+name+':p50"]').click();assert.equal(Number(await page.getByLabel('选中点幅值',{exact:true}).inputValue()),value)};
 const continuation=async name=>{await btn(name).click();await modal.waitFor();await btn('保存并继续编辑').click();await modal.waitFor({state:'hidden'});await active(name);assert(await editor.isVisible())};
 try{
  const initial=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');
  await page.goto(address(initial));await ready();await btn('编辑').click();await editor.waitFor();await btn('H').click();
  await edit('H',12);await btn('Sc').click();await modal.waitFor();await shot('save-and-continue-dialog');
  assert.equal(await btn('保存并返回').count(),0);assert(await btn('留在当前元素').isVisible());
  await btn('保存并继续编辑').click();await modal.waitFor({state:'hidden'});await active('Sc');
  assert(await editor.isVisible());assert.equal(report.saves.length,1);
  let current=(await listing()).items.find(i=>i.id===initial.id);
  assert.equal(current.result.curves.find(c=>c.id==='H').points[50].reconstructed_amplitude,12);
  assert.deepEqual(current.result.curves.find(c=>c.id==='Sc'),initial.result.curves.find(c=>c.id==='Sc'));
  check('H保存后直接进入Sc，编辑器保持打开，只有H已入库');

  await btn('隐藏原图').click();await btn('显示原图').click();
  const image=await editor.getByTestId('source-image').getAttribute('href');
  assert(await page.evaluate(src=>new Promise(resolve=>{const i=new Image();i.onload=()=>resolve(true);i.onerror=()=>resolve(false);i.src=src}),image));
  check('保存切换后原图blob仍有效，隐藏再显示不会丢图');

  await edit('Sc',18);await continuation('La');
  assert.equal(report.saves[1].request_version,report.saves[0].result_version);
  assert.equal(report.saves[1].request_run,report.saves[0].result_run);
  await selectValue('H',12);await selectValue('Sc',18);
  assert.equal(report.saves.length,2);
  check('连续保存使用新版本，回切H/Sc保留已保存坐标，不退回初始文档');

  await btn('H').click();await edit('H',13);await btn('Sc').click();failNext=true;
  await btn('保存并继续编辑').click();await modal.getByRole('alert').filter({hasText:/保存失败/}).waitFor();
  await active('H');assert.equal(Number(await page.getByLabel('选中点幅值',{exact:true}).inputValue()),13);
  current=(await listing()).items.find(i=>i.id===initial.id);
  assert.equal(current.result.curves.find(c=>c.id==='H').points[50].reconstructed_amplitude,12);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await shot('mobile-save-failure');
  delayNext=true;await btn('保存并继续编辑').click();await modal.getByRole('button',{name:'正在保存…',exact:true}).waitFor();
  assert(await modal.getByRole('button',{name:'正在保存…',exact:true}).isDisabled());assert(await btn('放弃修改').isDisabled());assert(await btn('留在当前元素').isDisabled());
  await modal.waitFor({state:'hidden'});await active('Sc');assert.equal(report.saves.length,3);
  assert.equal(report.saves[2].request_run,report.saves[1].result_run);
  check('网络失败留在H且输入保留，窄屏错误可见；重试成功且保存中禁止重复操作');

  await btn('H').click();await edit('H',19);await btn('Sc').click();await btn('留在当前元素').click();await active('H');
  assert.equal(Number(await page.getByLabel('选中点幅值',{exact:true}).inputValue()),19);
  await btn('Sc').click();await btn('放弃修改').click();await active('Sc');
  await selectValue('H',13);assert.equal(report.saves.length,3);
  check('取消留在当前元素，放弃切换仅丢未保存修改，不覆盖已保存结果');

  await btn('La').click();await edit('La',8);await btn('← 返回详情').click();await modal.waitFor();
  assert(await btn('保存并返回').isVisible());assert.equal(await btn('保存并继续编辑').count(),0);
  await btn('继续编辑').click();await active('La');
  await btn('← 返回详情').click();await btn('保存并返回').click();await editor.waitFor({state:'hidden'});await ready();
  current=(await listing()).items.find(i=>i.id===initial.id);
  assert.deepEqual(current.result.curves.map(c=>[c.id,c.points[50].reconstructed_amplitude]),[['La',8],['Sc',18],['H',13]]);
  assert.equal(new URL(page.url()).searchParams.get('run'),current.run.id);
  await page.reload();await ready();await btn('编辑').click();await editor.waitFor();await selectValue('H',13);await selectValue('Sc',18);await selectValue('La',8);
  check('真正退出仍保存并返回；URL更新和刷新回读保留全部元素最新保存结果');
  assert.deepEqual(report.errors,[]);report.status='passed';
 }catch(e){report.status='failed';report.failure=e.stack;await shot('failure');throw e}
 finally{fs.writeFileSync(path.join(out,'save-continue-browser.json'),JSON.stringify(report,null,2));await context.unrouteAll({behavior:'wait'});await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
