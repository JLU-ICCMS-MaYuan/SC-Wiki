// 正式页面 + 正式HTTP谱路由 + 隔离SQLite/文件存储；禁止请求真实业务API。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=process.env.CODEX_RUNTIME_NODE_MODULES||path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend=process.env.SPECTRUM_FRONTEND||'http://127.0.0.1:5173';
const out=path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.setDefaultTimeout(15000);
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{await page.screenshot({path:path.join(out,'production-'+name+'.png'),fullPage:!(await page.locator('.editor-app').count())});report.screenshots.push('production-'+name+'.png')};
 const btn=name=>page.getByRole('button',{name,exact:true});
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const data=await r.json();return {status:r.status,data}};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const listing=async()=> (await api('/api/rag/spectra?'+query)).data;
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 try{
  const first=await listing(),alpha=first.items.find(i=>i.result.curves[0].kind==='alpha2f');const old=JSON.stringify(alpha.result);
  await page.goto(address(alpha));await btn('编辑').waitFor({state:'visible'});await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑')?.disabled);await page.getByRole('slider',{name:'原图不透明度'}).focus();await page.getByRole('slider',{name:'原图不透明度'}).press('Home');await page.getByRole('slider',{name:'原图不透明度'}).press('ArrowUp');await shot('detail-before');
  await btn('编辑').click();await page.getByRole('application',{name:'谱线人工编辑画布'}).waitFor();assert.equal(await page.locator('.editor-app input[aria-label="原图不透明度"]').inputValue(),'1');await page.locator('.editor-app input[aria-label="原图不透明度"]').focus();await page.locator('.editor-app input[aria-label="原图不透明度"]').press('End');await shot('editor');
  assert.equal(await page.locator('.spectrum-manual-editor.editor-app').count(),1);
  await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.08');await btn('应用坐标到此点').click();
  if(await btn('确认蓝色零频线与原图一致').isEnabled())await btn('确认蓝色零频线与原图一致').click();await page.locator('[data-row="a:p0"]').click();await btn('确认选中点为零频点').click();await btn('保存调整').click();
  await page.waitForFunction(()=>!document.querySelector('.editor-app'));await page.getByTestId('saved-zero-check').waitFor();assert.equal(await page.getByTestId('saved-zero-check').getAttribute('data-complete'),'true');
  const after=await listing(),saved=after.items.find(i=>i.id===alpha.id);assert.notEqual(saved.run.id,alpha.run.id);assert.equal(saved.version,alpha.version+1);assert.equal(saved.result.curves[0].points[50].reconstructed_amplitude,.08);assert.deepEqual(saved.review,{});assert(page.url().includes(saved.run.id));assert.equal(await page.getByRole('slider',{name:'原图不透明度'}).inputValue(),'100');
  assert.equal(saved.result.quality.integrals.raw.status,'unavailable');check('正式详情读取真实接口文档，人工坐标保存到数据库新运行，回跳新版本并显示零频检查');await shot('saved-detail');
  await page.reload();await btn('编辑').waitFor();await page.getByTestId('saved-zero-check').waitFor();assert.equal(await page.getByTestId('saved-zero-check').getAttribute('data-complete'),'true');
  const history=(await api('/api/rag/spectra/'+alpha.id+'/runs/'+alpha.run.id+'?'+query)).data;assert.deepEqual(history.result.curves,JSON.parse(old).curves);assert.deepEqual(history.result.calibration,JSON.parse(old).calibration);check('刷新从持久数据库恢复人工结果，原始运行数值未被覆盖');
  await btn('查看提取历史').click();await page.getByRole('button',{name:/合成|时间未记录/}).count(); // 历史载入仍走正式接口。
  await btn('编辑').click();await page.getByRole('application').waitFor();await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.09');await btn('应用坐标到此点').click();
  const current=await listing(),item=current.items.find(i=>i.id===alpha.id);
  const input=(await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind=alpha2f&collection_version='+item.version+'&run_id='+item.run.id)).data;
  const competing=await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:input.collection_version,base_run_id:input.base_run_id,document:input.documents[0]});assert.equal(competing.status,200);
  await btn('保存调整').click();await page.getByRole('alert').filter({hasText:'保存失败'}).waitFor();assert(await page.getByRole('application').isVisible());assert.equal(await page.getByLabel('选中点幅值').inputValue(),'0.09');check('并发新版本产生409冲突，编辑器保留用户坐标而不覆盖数据库');await shot('conflict');
  await btn('← 返回详情').click();await btn('放弃修改').click();
  const dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');await page.goto(address(dos));await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.getByRole('button',{name:'H',exact:true}).click();assert.equal(await page.locator('.editor-app [data-curve]').count(),3);await page.locator('[data-row="H:p50"]').click();await page.getByLabel('选中点幅值').fill('18');await btn('应用坐标到此点').click();await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));
  const dosAfter=(await listing()).items.find(i=>i.id===dos.id);assert.equal(dosAfter.result.curves.find(c=>c.id==='H').points[50].reconstructed_amplitude,18);assert.deepEqual(dosAfter.result.curves.find(c=>c.id==='La'),dos.result.curves.find(c=>c.id==='La'));check('PhDOS分波使用自身标定保存，未编辑的La曲线逐点保持');
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('mobile-detail');await btn('编辑').click();await page.getByRole('application').waitFor();await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('mobile-editor');check('正式页面及全屏编辑器在390px无水平溢出');
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('scwiki-spectrum-manual')).length),0);assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>w.path.endsWith('/manual')));check('正式保存不访问Demo草稿、不重提取，所有写入仅到隔离manual路由');
  report.status='passed';report.database='isolated SQLite file; production SQLAlchemy models and HTTP routes';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'production-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
