// 不核对高频末端/安全修复全流程；生产React及HTTP，全部请求仅到隔离测试服务。
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
 const shot=async name=>{const file='preflight-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!await page.locator('.editor-app').count()});report.screenshots.push(file)};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const recalc=async()=>{const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const seed=async(item,kind,cid,mutate)=>{
   const input=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
   const doc=input.documents.find(d=>d.curves[0].id===cid);mutate(doc);
   return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id);
 };
 try{
  let data=await listing(),alpha=data.items.find(i=>i.result.curves[0].kind==='alpha2f');
  alpha=await seed(alpha,'alpha2f','a',doc=>{
    doc.curves[0].points.at(-1).x=139.999998;

  });
  const sourcePoints=JSON.stringify(alpha.result.curves);
  await page.goto(address(alpha));await ready();await recalc();
  let current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  assert(Math.abs(current.result.quality.integrals.raw.maximum_integrated_thz-5.9999999)<1e-12);
  assert.equal(JSON.stringify(current.result.curves),sourcePoints);
  assert.equal(await page.locator('[data-issue-kind="high_endpoint"],[data-issue-kind="projection_range"]').count(),0);
  assert.equal(await page.getByText(/本版本计算时间|参考来源：/).count(),0);
  await shot('no-endpoint-near-frame');
  check('相差0.000002像素也直接按保存范围计算，不要求末端核对，不改点');

  await btn('编辑').click();await page.getByRole('application').waitFor();
  assert.equal(await page.getByTestId('high-endpoint-panel').count(),0);
  assert.equal(await page.getByLabel('高频末端依据').count(),0);
  assert.equal(await btn('确认选中点为真实高频末端').count(),0);
  await page.locator('[data-row="a:p120"]').click();
  await page.getByLabel('选中点频率').fill('5.975');await btn('应用坐标到此点').click();
  await save();await recalc();
  current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  assert(Math.abs(current.result.quality.integrals.raw.maximum_integrated_thz-5.975)<1e-12);
  await shot('edited-without-confirmation');
  check('编辑器无末端依据或确认控件，移动最高频点后保存重算无需确认');

  current=await seed(current,'alpha2f','a',doc=>{
    doc.curves[0].points=doc.curves[0].points.slice(0,101);
    doc.highEndpoint={pointId:'missing-old-point',frequencyTHz:999,evidence:''};
  });
  await page.goto(address(current));await ready();await recalc();
  current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  assert.equal(current.result.quality.integrals.raw.maximum_integrated_thz,5);
  assert(!('highEndpoint' in current.result.manual_documents.a));
  await shot('far-below-frame');
  check('明显不到图框边缘仍按最高频5THz计算，旧确认错误或缺失均不构成限制');

  current=await seed(current,'alpha2f','a',doc=>{
    const p=structuredClone(doc.curves[0].points[60]);p.id='exact-duplicate';p.breakBefore=true;
    doc.curves[0].points.splice(61,0,p);
  });
  const before=current.result.curves[0].points;
  await page.goto(address(current));await ready();await recalc();
  current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.automatic_repairs.alpha2f.length,1);
  const after=current.result.curves[0].points;
  assert.equal(after.length,before.length);
  assert.deepEqual(after.map(({joinTo,...p})=>p),before);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  await page.getByTestId('automatic-repairs').waitFor();await shot('auto-connected');
  check('唯一完全重合断端先自动连接并成功计算，点数/坐标/数值保持且有修订记录');

  await page.getByTestId('automatic-repairs').getByRole('button').first().click();await page.getByRole('application').waitFor();
  await btn('撤销已记录的自动连接').click();await btn('↶ 撤销').click();assert(await btn('撤销已记录的自动连接').isVisible());
  await btn('↷ 重做').click();await save();
  const undone=(await listing()).items.find(i=>i.id===alpha.id);
  assert(!undone.result.curves[0].points.some(p=>p.joinTo==='exact-duplicate'));
  await recalc();
  const respected=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(respected.result.quality.automatic_repairs.alpha2f.length,0);
  assert(respected.result.quality.trace_diagnostics.alpha2f.curves.some(c=>c.issues.some(i=>i.kind==='disconnected')));
  check('自动连接可定位检查、撤销重做并保存；再次重算尊重已撤销连接，不自动加回');

  let dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');
  dos=await seed(dos,'phonon_dos','Sc',doc=>{
    doc.curves[0].points=doc.curves[0].points.slice(0,100);

  });
  const originalDos=JSON.stringify(dos.result.curves);
  await page.goto(address(dos));await ready();await recalc();
  let fresh=(await listing()).items.find(i=>i.id===dos.id);
  assert.equal(fresh.result.quality.dos_mode_integral.status,'available');
  assert(Math.abs(fresh.result.quality.dos_mode_integral.component_intervals.Sc[1]-4.95)<1e-9);
  assert.equal(JSON.stringify(fresh.result.curves),originalDos);
  assert.equal(await page.locator('[data-issue-kind="high_endpoint"],[data-issue-kind="projection_range"]').count(),0);
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await shot('dos-different-ranges');
  await btn('编辑').click();await page.getByRole('application').waitFor();
  await btn('Sc').click();
  assert.equal(await page.getByTestId('high-endpoint-panel').count(),0);
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('dos-mobile-no-setting');
  await btn('← 返回详情').click();await ready();
  check('PhDOS不同最高频范围直接分别积分，界面无分波末端检查或确认设置，窄屏可用');

  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));
  report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'preflight-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
