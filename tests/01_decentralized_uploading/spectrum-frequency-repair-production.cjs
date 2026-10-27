// #166：正式React/HTTP/SQLite验证；所有请求只发送到临时测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8196',frontend='http://127.0.0.1:5175',out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
assert(out);fs.mkdirSync(out,{recursive:true});
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1100}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true}),editor=page.locator('.editor-app');
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png'),fullPage:!await editor.count()});report.screenshots.push(name+'.png')};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=i=>frontend+'/spectra/'+i.id+'?'+query+'&'+new URLSearchParams({state_key:i.state_key,collection_version:i.version,run:i.run.id,curve:i.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const recalc=async()=>{const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const current=async id=>(await listing()).items.find(i=>i.id===id);
 const seed=async(item,kind,cid,large=false)=>{
  const input=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
  const doc=input.documents.find(d=>d.curves[0].id===cid),axis=doc.calibration.direction,points=doc.curves[0].points;
  doc.zero={pixel:points[0][axis],pointIds:[points[0].id]};
  const sign=Math.sign((doc.calibration.frequency.values[1]-doc.calibration.frequency.values[0])/(doc.calibration.frequency.pixels[1]-doc.calibration.frequency.pixels[0]));
  const center=(points[50][axis]+points[51][axis])/2;
  points[50][axis]=center+sign*(large?1.1:.1);points[51][axis]=center-sign*(large?1.1:.1);
  doc.operations.push({kind:'move',at:'2026-10-27T12:00:00Z',detail:'隔离测试人工回折'});
  return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id);
 };
 try{
  let alpha=(await listing()).items.find(i=>i.result.curves[0].kind==='alpha2f');
  alpha=await seed(alpha,'alpha2f','a');
  const before=structuredClone(alpha.result.curves[0]);
  await page.goto(address(alpha));await ready();await recalc();
  let item=await current(alpha.id),curve=item.result.curves[0],rep=item.result.quality.frequency_repairs.alpha2f[0];
  assert.equal(rep.new_point_count,2);assert(rep.max_shift_px<=.5);
  for(let i=0;i<curve.points.length;i++)assert.equal(curve.points[i].amplitude_pixel,before.points[i].amplitude_pixel);
  assert.equal(item.result.quality.integrals.raw.parameters.omega_log.status,'available');
  await page.getByTestId('frequency-repair-report').waitFor();
  assert.equal(await page.locator('[data-frequency-repaired=true]').count(),2);
  await shot('recalculated');
  check('纵轴α²F真实重算修正两点，幅值保持，积分可用，详情高亮并显示最大位移');

  const repaired=structuredClone(curve.points);await page.reload();await ready();await recalc();
  item=await current(alpha.id);
  assert.deepEqual(item.result.curves[0].points,repaired);
  assert.equal(item.result.quality.frequency_repairs.alpha2f[0].new_point_count,0);
  check('刷新和重复重算不累积移动，已有修正报告保留');

  await page.getByTestId('frequency-repair-report').getByRole('button').first().click();
  await editor.waitFor();
  assert.equal(await editor.locator('[data-frequency-repaired=true]').count(),2);
  await btn('撤销自动频率微调').scrollIntoViewIfNeeded();await shot('editor-undo');
  await btn('撤销自动频率微调').click();
  const coords=await editor.locator('[data-point="a:p50"]').evaluate(e=>({x:Number(e.dataset.x),y:Number(e.dataset.y)}));
  assert.equal(coords.y,before.points[50].frequency_pixel);
  await save();await recalc();
  item=await current(alpha.id);
  assert.equal(item.result.curves[0].points[50].frequency_pixel,before.points[50].frequency_pixel);
  assert.equal(item.result.quality.frequency_repairs.alpha2f[0].new_point_count,0);
  assert.equal(item.result.quality.integrals.raw.status,'unavailable');
  assert(await page.locator('[data-issue-kind="frequency_backtrack"]').count()>0);
  await shot('undo-respected');
  check('点击定位后在编辑器撤销并保存，再次重算尊重撤销意图，保留真实回折诊断');

  await btn('编辑').click();await editor.waitFor();
  await editor.locator('[data-row="a:p50"]').click();
  const value=Number(await page.getByLabel('选中点频率',{exact:true}).inputValue());
  await page.getByLabel('选中点频率',{exact:true}).fill(String(value+.001));
  await btn('应用坐标到此点').click();await save();await recalc();
  item=await current(alpha.id);
  assert.equal(item.result.quality.frequency_repairs.alpha2f[0].new_point_count,2);
  await page.getByTestId('frequency-repair-report').getByRole('button').first().click();await editor.waitFor();
  const f=Number(await page.getByLabel('选中点频率',{exact:true}).inputValue());
  await page.getByLabel('选中点频率',{exact:true}).fill(String(f+.002));
  await btn('应用坐标到此点').click();
  assert(await btn('撤销自动频率微调').isDisabled());
  await btn('← 返回详情').click();await btn('放弃修改').click();await ready();
  check('继续人工编辑后允许新一轮修正；随后改动频率时禁用直接撤销，避免覆盖新编辑');

  let dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');
  dos=await seed(dos,'phonon_dos','Sc');
  const unchanged=structuredClone(dos.result.curves.filter(c=>c.id!=='Sc'));
  await page.goto(address(dos));await ready();await recalc();item=await current(dos.id);
  assert.equal(item.result.quality.frequency_repairs.phonon_dos.find(c=>c.curve_id==='Sc').new_point_count,2);
  assert.deepEqual(item.result.curves.filter(c=>c.id!=='Sc'),unchanged);
  await page.setViewportSize({width:390,height:1000});await page.waitForTimeout(500);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await shot('dos-mobile');check('横轴DOS同样修正且不改变其他分波，窄屏报告可用');

  dos=await seed(item,'phonon_dos','Sc',true);
  const large=structuredClone(dos.result.curves);
  await page.goto(address(dos));await ready();await recalc();item=await current(dos.id);
  assert.deepEqual(item.result.curves,large);
  assert(item.result.quality.frequency_repairs.phonon_dos.find(c=>c.curve_id==='Sc').skipped.length);
  await page.getByText(/未自动修正：Sc/).waitFor();await shot('large-kept');
  check('超过0.5px可修范围的回折保持原点和诊断，未伪造修复成功');
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));
  report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'frequency-repair-browser.json'),JSON.stringify(report,null,2));await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
