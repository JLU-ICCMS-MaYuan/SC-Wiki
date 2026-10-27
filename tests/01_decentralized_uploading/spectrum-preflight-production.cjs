// 真实末端/安全修复全流程；生产React及HTTP，全部请求仅到隔离测试服务。
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
  alpha=await seed(alpha,'alpha2f','a',doc=>{doc.curves[0].points.pop();doc.zero={pixel:20,pointIds:[doc.curves[0].points[0].id]}});
  const sourcePoints=JSON.stringify(alpha.result.curves);
  await page.goto(address(alpha));await ready();await recalc();
  let issue=page.locator('[data-issue-kind="high_endpoint"]');await issue.waitFor();
  assert((await issue.getByTestId('endpoint-difference').innerText()).includes('5.95'));
  assert((await issue.getByTestId('endpoint-difference').innerText()).includes('6 THz'));
  assert.equal(await page.getByText(/本版本计算时间|参考来源：/).count(),0);
  await shot('endpoint-problem');check('高频末端低于图框时给出实际端点、参考边界和差距，03无时间或来源JSON');

  await issue.locator('[data-diagnostic-point="a:p119"]').click();await page.getByRole('application').waitFor();
  assert.equal(await page.locator('[data-row="a:p119"]').getAttribute('aria-selected'),'true');
  await page.getByLabel('高频末端依据').fill('合成原图红线在5.95 THz结束，图框6THz为留白，不补造终点');
  await btn('确认选中点为真实高频末端').click();
  await btn('↶ 撤销').click();assert(await page.getByText('尚未确认独立于图框边界的真实高频末端。',{exact:true}).isVisible());
  await btn('↷ 重做').click();await shot('endpoint-confirmed-editor');
  await save();assert.equal(JSON.stringify((await listing()).items.find(i=>i.id===alpha.id).result.curves),sourcePoints);
  await recalc();let current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.lambda.status,'available');
  assert(Math.abs(current.result.quality.integrals.raw.maximum_integrated_thz-5.95)<1e-9);
  assert.equal(await page.locator('[data-issue-kind="high_endpoint"]').count(),0);await shot('actual-range-result');
  check('坐标直达真实末端，确认可撤销重做，保存重算按5.95截止，不移动/增加任何点');

  await page.reload();await ready();await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.locator('[data-row="a:p119"]').click();await page.getByLabel('选中点幅值').fill('0.07');await btn('应用坐标到此点').click();
  assert(await page.getByText('尚未确认独立于图框边界的真实高频末端。',{exact:true}).isVisible());
  await save();await recalc();await page.locator('[data-issue-kind="high_endpoint"]').waitFor();
  check('移动末端后原确认自动失效，保存重算重新给出准确坐标，不沿用旧确认');

  current=(await listing()).items.find(i=>i.id===alpha.id);
  current=await seed(current,'alpha2f','a',doc=>{
    // 恢复末端位置确认，同时构造一对完全重合的唯一断端。
    const end=doc.curves[0].points.at(-1);
    doc.highEndpoint={pointId:end.id,x:end.x,y:end.y,frequencyTHz:5.95,evidence:'原图真实末端'};
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
  dos=await seed(dos,'phonon_dos','Sc',doc=>{doc.curves[0].points.pop();doc.zero={pixel:20,pointIds:[doc.curves[0].points[0].id]}});
  await page.goto(address(dos));await ready();await recalc();
  issue=page.locator('[data-issue-kind="high_endpoint"]').filter({hasText:'Sc'});await issue.waitFor();
  await page.setViewportSize({width:390,height:844});await issue.locator('[data-diagnostic-point]').click();await page.getByRole('application').waitFor();
  assert.equal(await page.locator('[data-row="Sc:p119"]').getAttribute('aria-selected'),'true');
  await page.getByLabel('高频末端依据').fill('原图Sc分波此处终止');
  await btn('确认选中点为真实高频末端').click();await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('dos-mobile-endpoint');
  await save();await recalc();assert.equal(await page.locator('[data-issue-kind="high_endpoint"]').count(),0);
  check('PhDOS末端同样可定位到正确分波并确认，390px布局无溢出');

  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));
  report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'preflight-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
