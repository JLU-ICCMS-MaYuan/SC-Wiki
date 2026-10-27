// #167：真实前端 + 隔离 HTTP/SQLite，验证取消人工零频核对及实际区间积分。
const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
const runtime=path.join(process.env.HOME,".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules");
const {chromium}=require(require.resolve("playwright",{paths:[runtime]}));
const backend=process.env.SPECTRUM_TEST_BACKEND||"http://127.0.0.1:8199",frontend="http://127.0.0.1:5173",out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
assert(out);fs.mkdirSync(out,{recursive:true});
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:"chrome"}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem("auth_token","isolated-test");localStorage.setItem("auth_user",JSON.stringify({id:161,username:"isolated_validation",role:"user",is_approved:true,account_status:"active",is_email_verified:true}))});
 await context.route("**/api/**",async route=>{const req=route.request(),u=new URL(req.url());if(req.method()!=="GET")report.writes.push({method:req.method(),path:u.pathname});const response=await route.fetch({url:backend+u.pathname+u.search});await route.fulfill({response})});
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on("pageerror",e=>report.errors.push(e.message));
 const btn=name=>page.getByRole("button",{name,exact:true}),check=name=>{report.checks.push(name);console.log("PASS",name)};
 const shot=async name=>{const file=name+".png";await page.screenshot({path:path.join(out,file),fullPage:!await page.locator(".editor-app").count()});report.screenshots.push(file)};
 const target={target:"upload",target_id:"manual-test"},query=new URLSearchParams(target).toString();
 const api=async p=>{const r=await fetch(backend+p);assert.equal(r.status,200);return r.json()};
 const listing=()=>api("/api/rag/spectra?"+query);
 const address=item=>frontend+"/spectra/"+item.id+"?"+new URLSearchParams({...target,state_key:item.state_key,collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:"/upload"});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll("button")).find(b=>b.textContent==="编辑");return b&&!b.disabled});
 const recalc=async()=>{const old=page.url();await btn("重新计算").click();await page.waitForURL(u=>u.href!==old);await ready()};
 const noReview=async()=>{assert.equal(await page.getByText(/零频位置核对|继续核对|确认蓝色零频|确认选中点为零频|补选曲线零频|标记原图 0 频率/).count(),0);assert.equal(await page.locator(".zero-steps,[data-testid=zero-frequency-check]").count(),0)};
 const current=async id=>(await listing()).items.find(i=>i.id===id);
 const edit=async(index,value)=>{await page.locator("[data-row]").nth(index).click();await page.getByLabel("选中点幅值",{exact:true}).fill(String(value));await btn("应用坐标到此点").click()};
 try{
  let alpha=(await listing()).items.find(i=>i.state_key==="s1"),oldUrl=address(alpha);
  const source=structuredClone(alpha.result.curves);
  await page.goto(oldUrl);await ready();await noReview();await recalc();
  alpha=await current(alpha.id);let raw=alpha.result.quality.integrals.raw;
  assert.equal(raw.method,"alpha2f-relative-v2");assert.equal(raw.parameters.omega_log.status,"available");assert.equal(raw.normalization.status,"available");
  assert(Math.abs(raw.minimum_integrated_thz-.2)<1e-10);assert(Math.abs(raw.maximum_integrated_thz-6)<1e-10);assert.equal(raw.positive_frequency_complete,false);
  assert(Math.abs(raw.normalization.lambda_normalized-.12)<1e-10);assert.deepEqual(alpha.result.curves,source);
  await noReview();await shot("alpha-positive-range");check("没有零刻度/人工确认，0.2–6 THz α²F直接计算ωlog和论文λ归一化，点数据不变");
  await btn("编辑").click();await page.getByRole("application").waitFor();await noReview();await edit(50,.08);
  await btn("保存调整").click();await page.waitForFunction(()=>!document.querySelector(".editor-app"));await ready();await noReview();await recalc();
  alpha=await current(alpha.id);raw=alpha.result.quality.integrals.raw;assert.equal(raw.parameters.omega_log.status,"available");assert(Math.abs(raw.minimum_integrated_thz-.2)<1e-10);
  const docs=await api("/api/rag/spectra/"+alpha.id+"/manual?"+query+"&kind=alpha2f&collection_version="+alpha.version+"&run_id="+alpha.run.id);
  assert(docs.documents.every(d=>!Object.hasOwn(d,"zero")));assert(!Object.hasOwn(alpha.result.quality,"manual_zero_checks"));
  check("正式编辑器改点保存后无需核对即可重算，新文档不携带zero或核对报告");
  const writes=report.writes.length;await page.goto(oldUrl);await ready();await page.waitForURL(u=>u.searchParams.get("run")===alpha.run.id);
  assert.equal(await page.getByRole("link",{name:"打开最新结果",exact:true}).count(),0);assert.equal(report.writes.length,writes);
  check("旧地址自动打开最新保存/计算结果，不要求再次选择，也不新增写请求");
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+1);await shot("alpha-mobile");await page.setViewportSize({width:1440,height:1000});
  let dos=(await listing()).items.find(i=>i.state_key==="dos-positive");const before=structuredClone(dos.result.curves);
  await page.goto(address(dos));await ready();await recalc();dos=await current(dos.id);
  let relative=dos.result.quality.dos_relative;
  assert.equal(relative.normalization.status,"available");assert(Math.abs(relative.normalization.total_mode_integral-9)<1e-10);
  assert(relative.components.every(c=>Math.abs(c.frequency_interval_thz[0]-.2)<1e-10&&Math.abs(c.frequency_interval_thz[1]-1.2)<1e-10));
  assert.deepEqual(dos.result.curves,before);await noReview();await shot("dos-positive-3n");check("LaH2的正起点DOS在实际0.2–1.2 THz范围按共同倍率归一化到3N=9");
  await btn("编辑").click();await page.getByRole("application").waitFor();await noReview();await edit(1,9);
  await btn("H").click();await btn("保存并继续编辑").click();await page.locator(".production-curve-tabs button.active").filter({hasText:/^H$/}).waitFor();
  await edit(1,11);await btn("La").click();await btn("保存并继续编辑").click();await page.locator(".production-curve-tabs button.active").filter({hasText:/^La$/}).waitFor();
  await btn("← 返回详情").click();await ready();await recalc();dos=await current(dos.id);
  assert.equal(dos.result.curves.find(c=>c.id==="La").points[1].reconstructed_amplitude,9);assert.equal(dos.result.curves.find(c=>c.id==="H").points[1].reconstructed_amplitude,11);
  assert.equal(dos.result.quality.dos_relative.normalization.status,"available");assert(Math.abs(dos.result.quality.dos_relative.normalization.total_mode_integral-9)<1e-10);
  await page.reload();await ready();await noReview();check("切换元素保存并继续编辑使用最新版本，两个元素均持久化，刷新和重新3N计算无需零频核对");
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+1);await shot("dos-mobile");check("正式详情390px窄屏无横向溢出");
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));report.status="passed";
 }catch(e){report.status="failed";report.failure=e.stack;await shot("failure");throw e}
 finally{fs.writeFileSync(path.join(out,"browser-validation.json"),JSON.stringify(report,null,2)+"\n");await context.unrouteAll({behavior:"wait"});await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
