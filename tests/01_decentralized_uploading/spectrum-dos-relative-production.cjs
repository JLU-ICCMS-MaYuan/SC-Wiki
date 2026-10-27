// #164：正式 React + HTTP + SQLite，所有 API 写入仅进入隔离服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8194',frontend='http://127.0.0.1:5175',out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
assert(out);
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1100}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});
   const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response});
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const query='target=upload&target_id=manual-test';
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=i=>frontend+'/spectra/'+i.id+'?'+query+'&'+new URLSearchParams({state_key:i.state_key,collection_version:i.version,run:i.run.id,curve:i.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const button=name=>page.getByRole('button',{name,exact:true});
 const recalc=async()=>{const old=page.url();await button('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});report.screenshots.push(name+'.png')};
 try {
   let items=(await listing()).items;
   const original=items.find(i=>i.state_key==='s1'&&i.result.curves[0].kind==='phonon_dos');
   const curves=structuredClone(original.result.curves);
   await page.goto(address(original));await ready();await recalc();
   let current=(await listing()).items.find(i=>i.id===original.id);
   let relative=current.result.quality.dos_relative;
   const normalizedBefore=structuredClone(current.result.candidates.dos_relative_normalized);
   assert.equal(relative.normalization.status,'available',JSON.stringify(relative));
   assert.deepEqual(relative.normalization.expected_modes,{La:3,H:6});
   assert.deepEqual(relative.normalization.component_mode_integrals,{La:4,H:5});
   assert.deepEqual(current.result.curves,curves);
   await page.getByRole('table',{name:'DOS 相对面积'}).waitFor();
   await page.getByRole('table',{name:'DOS 归一化模式积分'}).getByText('33.33%',{exact:true}).waitFor();
   check('正式重新计算保存新版本，N=3且模式4/5保留偏差；原始描线不变');
   const before=await page.locator('[data-curve="La"]').getAttribute('d'),writes=report.writes.length;
   await button('相对像素幅值').click();assert.equal(await page.locator('[data-curve="La"]').getAttribute('d'),before);
   await button('按 3N 归一化').click();assert.equal(await page.locator('[data-curve="La"]').getAttribute('d'),before);
   assert.equal(report.writes.length,writes);
   await shot('dos-desktop');check('归一化/相对切换仅改变数值刻度，无写请求或几何变化');
   await page.reload();await ready();await recalc();
   current=(await listing()).items.find(i=>i.id===original.id);
   assert.equal(current.result.quality.dos_relative.normalization.coefficient,relative.normalization.coefficient);
   assert.deepEqual(current.result.candidates.dos_relative_normalized.curves,normalizedBefore.curves);
   check('刷新后重复计算仍使用原始数据，共同系数不累乘');
   await page.setViewportSize({width:390,height:900});
   await page.waitForTimeout(500);
   await shot('dos-mobile');
   const overflow=await page.evaluate(()=>({width:window.innerWidth,scroll:document.documentElement.scrollWidth,
      elements:Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>window.innerWidth+1&&e.getBoundingClientRect().width>window.innerWidth).slice(0,20).map(e=>({tag:e.tagName,classes:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))}));
   if(overflow.scroll>overflow.width+1)console.log(JSON.stringify(overflow));
   assert(overflow.scroll<=overflow.width+1);
   await shot('dos-mobile');check('390px 页面无整体横向溢出，结果表可局部滚动');
   const noN=items.find(i=>i.state_key==='dos-no-n');
   await page.goto(address(noN));await ready();await recalc();
   const missing=(await listing()).items.find(i=>i.id===noN.id).result.quality.dos_relative;
   assert.equal(missing.normalization.status,'unavailable');assert.equal(missing.components[0].area,16);
   assert(Math.abs(missing.shares.expected_fractions.La-1/3)<1e-9);
   await page.getByText(/缺少可信原胞原子数/).waitFor();
   await page.getByRole('table',{name:'DOS 相对面积'}).getByText('44.44%',{exact:true}).waitFor();
   await shot('dos-no-n');check('只有化学式时面积与实测/预期占比可用，N与模式归一化保持未知');
   assert.deepEqual(report.errors,[]);
 } finally {fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify(report,null,2));await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
