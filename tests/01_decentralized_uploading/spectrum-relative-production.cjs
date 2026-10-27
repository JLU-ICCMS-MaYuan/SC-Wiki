// #163 正式React/HTTP/版本存储；所有请求只发送到隔离测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend='http://127.0.0.1:5173',out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true});
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{const file='relative-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!await page.locator('.editor-app').count()});report.screenshots.push(file)};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:item.state_key,collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const recalc=async()=>{const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const manual=async(item,kind,cid,change)=>{
  const input=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
  const doc=input.documents.find(d=>d.curves[0].id===cid);delete doc.calibration.amplitudeEvidence;
  change?.(doc);
  return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id)
 };
 const closeEditor=async()=>{await btn('← 返回详情').click();await ready()};
 try{
  let items=(await listing()).items,alpha=items.find(i=>i.state_key==='s1'&&i.result.curves[0].kind==='alpha2f');
  const original=structuredClone(alpha.result.curves);await page.goto(address(alpha));await ready();await recalc();
  let current=(await listing()).items.find(i=>i.id===alpha.id),raw=current.result.quality.integrals.raw;
  assert.equal(raw.parameters.omega_log.status,'available');assert.equal(raw.normalization.status,'available');
  assert.equal(raw.normalization.lambda_reference,.12);assert(Math.abs(raw.normalization.lambda_normalized-.12)/.12<1e-8);assert(current.result.quality.comparisons.raw.omega_log.relative_difference_pct>100);
  assert.equal(current.result.quality.comparisons.raw.lambda,undefined);assert.deepEqual(current.result.curves,original);
  assert(await btn('编辑').isEnabled());assert(await btn('重新计算').isEnabled());
  const table=page.getByRole('table');assert.equal(await table.getByText('λ',{exact:true}).count(),0);
  await page.getByTestId('alpha-normalization').getByText('依据论文 λ 归一化',{exact:true}).waitFor();
  await shot('large-deviation-normalized');check('无绝对刻度/说明也独立计算ωlog；偏差超过100%仍可编辑保存，λ只作为归一化输入');

  const pathBefore=await page.locator('[data-curve="a"]').getAttribute('d'),writes=report.writes.length;
  await btn('相对像素幅值').click();assert.equal(await page.locator('[data-curve="a"]').getAttribute('d'),pathBefore);
  await btn('依据论文 λ 归一化').click();assert.equal(await page.locator('[data-curve="a"]').getAttribute('d'),pathBefore);
  assert.equal(report.writes.length,writes);
  const coefficient=raw.normalization.coefficient,omega=raw.omega_log_k,normalized=current.result.candidates.alpha2f_lambda_normalized.alpha2f;
  await page.reload();await ready();await recalc();current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.normalization.coefficient,coefficient);
  assert.deepEqual(current.result.candidates.alpha2f_lambda_normalized.alpha2f,normalized);
  check('相对/归一化显示只改数值刻度，源曲线几何不变；刷新重复计算不累乘C');

  current=await manual(current,'alpha2f','a',doc=>{for(const p of doc.curves[0].points)p.y=80-2*(80-p.y)});
  await page.goto(address(current));await ready();await recalc();current=(await listing()).items.find(i=>i.id===alpha.id);raw=current.result.quality.integrals.raw;
  assert(Math.abs(raw.omega_log_k-omega)<1e-8);assert(Math.abs(raw.normalization.coefficient-coefficient/2)<1e-10);
  const rawNormalized=current.result.candidates.alpha2f_lambda_normalized.alpha2f;
  assert(normalized.every((v,i)=>Math.abs(v-rawNormalized[i])<1e-10));
  check('真实源像素幅值翻倍，ωlog不变、C减半、归一化谱一致');

  await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.locator('summary').filter({hasText:'坐标标定'}).click();
  assert.equal(await page.getByLabel('幅值标定依据').count(),0);
  await page.getByLabel('幅值单位',{exact:true}).selectOption('dimensionless');await btn('应用标定').click();
  await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('12');await btn('应用坐标到此点').click();
  await save();await recalc();current=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(current.result.quality.integrals.raw.parameters.omega_log.status,'available');
  assert.equal(current.result.quality.integrals.raw.normalization.status,'available');
  check('α²F编辑器没有说明输入；物理单位标定、改点、保存和重算不因说明为空被拒绝');

  items=(await listing()).items;const noLambda=items.find(i=>i.state_key==='s2');
  await page.goto(address(noLambda));await ready();await recalc();
  let item=(await listing()).items.find(i=>i.id===noLambda.id);
  assert.equal(item.result.quality.integrals.raw.parameters.omega_log.status,'available');
  assert.equal(item.result.quality.integrals.raw.normalization.status,'unavailable');
  assert(await page.getByText('不适用（参考为0）',{exact:true}).isVisible());
  assert(await page.getByTestId('alpha-relative-metrics').isVisible());await shot('missing-lambda-zero-omega-reference');
  check('缺论文λ仍显示独立ωlog，ω参考为0保留值/绝对偏差，相对偏差不生成无穷大');

  const noOmega=items.find(i=>i.state_key==='s3');await page.goto(address(noOmega));await ready();await recalc();
  item=(await listing()).items.find(i=>i.id===noOmega.id);
  assert.equal(item.result.quality.integrals.raw.normalization.status,'available');
  assert.equal(item.result.quality.comparisons.raw.omega_log.status,'unavailable');await shot('missing-omega-reference');
  check('缺论文ωlog仍显示计算值与论文λ归一化，参考不连带隐藏其他结果');

  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await shot('alpha-mobile');assert(await btn('重新计算').isEnabled());
  await page.setViewportSize({width:1440,height:1000});
  check('α²F新对比表和倍率卡在390px不溢出，偏差不禁用操作');

  let dos=items.find(i=>i.result.curves[0].kind==='phonon_dos');await page.goto(address(dos));await ready();await btn('编辑').click();await page.getByRole('application').waitFor();
  await btn('Sc').click();await page.locator('summary').filter({hasText:'坐标标定'}).click();
  assert.equal(await page.getByLabel('幅值标定依据').count(),0);
  await page.getByLabel('amplitude-1-value').fill('0.5');await btn('应用标定').click();await save();await recalc();
  dos=(await listing()).items.find(i=>i.id===dos.id);assert.equal(dos.result.quality.dos_mode_integral.status,'available');
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('dos-mobile');
  check('DOS编辑器同样无说明，空说明修改幅值标定可保存计算；3N路径和窄屏保持');

  await page.setViewportSize({width:1440,height:1000});
  current=(await listing()).items.find(i=>i.id===alpha.id);
  current=await manual(current,'alpha2f','a',doc=>{for(const p of doc.curves[0].points)p.y=80});
  await page.goto(address(current));await ready();await recalc();current=(await listing()).items.find(i=>i.id===alpha.id);raw=current.result.quality.integrals.raw;
  assert.equal(raw.pixel_integral,0);assert.equal(raw.parameters.omega_log.status,'unavailable');assert.equal(raw.normalization.status,'unavailable');
  assert.equal(raw.normalization.lambda_reference,.12);assert(await btn('编辑').isEnabled());await shot('zero-integral');
  check('零积分逐项说明ωlog/C无定义，保留参考和编辑入口，不制造数值或锁死操作');

  const history=await api('/api/rag/spectra/'+alpha.id+'/runs/'+alpha.run.id+'?'+query);assert.deepEqual(history.result.curves,original);
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'relative-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
