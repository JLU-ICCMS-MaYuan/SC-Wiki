// 对运行中的本地 Demo 做真实模型请求和真实文件下载，不替换预测 API。
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const runtime = path.join(process.env.HOME, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = require(require.resolve('playwright', { paths: [process.cwd(), runtime] }));
const demo = path.resolve(__dirname, '..'), root = path.resolve(demo, '../../../..'), out = path.resolve(demo, '../assets');
const catalog = JSON.parse(fs.readFileSync(path.join(demo, 'catalog.json'), 'utf8'));
const downloads = path.join(root, '.local/tc-model-demo/browser-downloads');
fs.mkdirSync(out, { recursive: true }); fs.mkdirSync(downloads, { recursive: true });
const report = { checks: [], errors: [], downloads: [], predictions: [], screenshots: [] };
const base = 'http://127.0.0.1:5189';
function check(name) { report.checks.push(name); console.log('PASS', name) }
async function digest(file) { const h = crypto.createHash('sha256'); for await (const chunk of fs.createReadStream(file)) h.update(chunk); return h.digest('hex') }
async function main() {
 const browser = await chromium.launch({headless:true,channel:'chrome'});
 const context = await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true,permissions:[]});
 const page = await context.newPage(); page.setDefaultTimeout(15000);
 page.on('pageerror', e => report.errors.push(e.message));
 const button = name => page.getByRole('button', {name,exact:true});
 const choose = name => page.getByRole('navigation',{name:'选择模型'}).getByRole('button',{name:new RegExp(name)}).click();
 const shot = async name => {await page.waitForTimeout(250);await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await page.getByRole('status').waitFor({state:'hidden'});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(200);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});report.screenshots.push(name+'.png')};
 const predict = async () => {
  const response = page.waitForResponse(r=>r.url().endsWith('/demo-api/predict') && r.request().method()==='POST',{timeout:180000});
  await button('运行模型 →').click(); const r = await response; const body = await r.json();assert.equal(r.status(),200,JSON.stringify(body));
  await page.locator(`[data-result="${body.model_id}"]`).first().waitFor();report.predictions.push(body);return body;
 };
 const download = async id => {
  const expected = catalog.datasets.find(d=>d.id===id), card=page.locator(`[data-dataset="${id}"]`);
  const event = page.waitForEvent('download');await card.getByRole('link',{name:expected.download_label?'↓ '+expected.download_label:'↓ 下载原文件',exact:true}).click();const file=await event;
  assert.equal(file.suggestedFilename(),expected.filename);const dest=path.join(downloads,expected.filename);await file.saveAs(dest);
  const sha=await digest(dest);assert.equal(sha,expected.sha256);assert.equal(fs.statSync(dest).size,expected.size);
  report.downloads.push({id,filename:file.suggestedFilename(),bytes:expected.size,sha256:sha});
  const source=page.locator('.data-panel').getByRole('link',{name:'原始网站',exact:true});assert.equal(await source.count(),1);const href=await source.getAttribute('href');assert(href.startsWith('https://'));
  const repo=url=>new URL(url).hostname+new URL(url).pathname.split('/').slice(0,3).join('/');assert.equal(repo(href),repo(expected.source_url));
 };
 try {
  await page.goto(base);await page.getByRole('heading',{name:'超导模型实验室Beta'}).waitFor();await page.locator('[data-dataset="bete-bundle"]').waitFor();
  const reference = await context.newPage();await reference.goto('http://127.0.0.1:5173/tc-predict');await reference.getByRole('heading').first().waitFor();
  const siteTheme = await reference.evaluate(()=>({background:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,font:getComputedStyle(document.body).fontFamily,primary:getComputedStyle(document.querySelector('nav button[aria-label^="SC-Wiki"] span')).backgroundColor}));
  const demoTheme = await page.evaluate(()=>({background:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,font:getComputedStyle(document.body).fontFamily,primary:getComputedStyle(document.querySelector('.brand-mark')).backgroundColor}));
  assert.deepEqual(demoTheme,siteTheme);report.theme={reference:siteTheme,demo:demoTheme};await reference.close();check('与当前 SC-Wiki 实际页面的基础色、文字色、字体和品牌主色一致');
  const aligned = async () => {
    const boxes=await page.evaluate(()=>{const a=document.querySelector('.model-panel').getBoundingClientRect(),b=document.querySelector('.data-panel').getBoundingClientRect();return {top:Math.abs(a.top-b.top),bottom:Math.abs(a.bottom-b.bottom),height:Math.abs(a.height-b.height)}});
    assert(boxes.top<1 && boxes.bottom<1 && boxes.height<1,JSON.stringify(boxes));
    assert.equal(await page.locator('.model-panel .model-links').count(),0);
  };
  await aligned();assert(await page.locator('.data-panel').getByRole('link',{name:'论文链接',exact:true}).isVisible());assert(await page.locator('.data-panel').getByRole('link',{name:'原始网站',exact:true}).isVisible());check('论文／代码位于右卡，桌面左右卡片顶底和高度对齐');
  await shot('demo-desktop');await button('Nb 铌').click();await page.waitForFunction(()=>document.querySelector('#structure').value.includes('Nb'));
  assert.equal(await page.locator('.run').evaluate(el=>getComputedStyle(el).backgroundColor),siteTheme.primary);check('可用的运行按钮使用主站主色');
  const nn = await predict();assert.equal(nn.ensemble_size,100);assert(Number.isFinite(nn.tc) && nn.tc>0);assert.equal(nn.spectrum.a2f.length,51);check('Nb 结构真实运行作者 100 网络集成，返回 Tc 与 51 点谱');
  assert.equal(await page.locator('.data-panel [data-dataset]').count(),1);await download('bete-bundle');check('BETE 只展示一个整包下载，浏览器实际下载摘要与准备包一致');
  assert.equal(await page.getByRole('button',{name:'预览数据',exact:true}).count(),0);assert.equal(await page.getByText('它学习的数据',{exact:true}).count(),0);assert.equal((await context.request.get(base+'/demo-api/preview/bete-data')).status(),404);check('数据预览按钮及旧标题移除，废弃预览接口已退役');
  assert(!/https?:\/\/|SHA-256|许可与版本|原始网址|查看原始发布页/.test(await page.locator('.data-panel').innerText()));assert.equal(await page.locator('.data-panel').getByRole('link',{name:'模型代码',exact:true}).count(),0);check('论文链接／原始网站均为文字链接，同仓库入口去重，不展示裸网址、许可版本和校验码');
  await button('用此参数对比 SISSO →').click();assert.equal(Number(await page.getByRole('textbox',{name:'lambda',exact:true}).inputValue()),nn.parameters.lambda);
  const sr = await predict();assert.equal(sr.model_id,'sisso-2019');assert.equal(sr.parameters.lambda,nn.parameters.lambda);assert(await page.locator('[data-result="bete-cso"]').isVisible());check('结构预测参数可带入 SISSO 实际计算，保留两个独立结果');
  await aligned();assert.equal(await page.locator('.data-panel [data-dataset]').count(),1);await download('sisso-train');check('SISSO 只展示作者实际使用的 29 条训练数据，不要求用户另选全集');
  const before = await page.locator('[data-result]').count();await page.getByRole('textbox',{name:'lambda',exact:true}).fill('-1');
  const badResponse=page.waitForResponse(r=>r.url().endsWith('/demo-api/predict'));await button('运行模型 →').click();assert.equal((await badResponse).status(),400);await page.getByRole('alert').waitFor();assert.equal(await page.locator('[data-result]').count(),before);check('非法参数返回错误，已有结果不丢失、不产生伪结果');
  await page.getByRole('tab',{name:/高压氢化物/}).click();await button('加载示例').click();await aligned();const hp=await predict();assert.equal(hp.model_id,'sisso-2022');assert(hp.tc>0);
  assert(await page.locator('[data-dataset="xie-2022"]').getByRole('button',{name:'暂不可下载',exact:true}).isDisabled());assert.equal((await context.request.get(base+'/demo-api/datasets/xie-2022')).status(),503);check('高压参数模型真实计算；上游训练包失败明确显示且下载接口拒绝空文件');
  assert.equal(await page.locator('.data-panel').getByRole('link',{name:'模型代码',exact:true}).count(),1);assert.equal(await page.locator('.data-panel').getByRole('link',{name:'原始网站',exact:true}).getAttribute('href'),'https://archive.materialscloud.org/records/skdzy-kyx54');
  await choose('Tc assessment model');await aligned();assert.equal(await page.getByRole('link',{name:'打开原有估算 ↗',exact:true}).count(),0);
  assert.equal(await page.locator('.data-panel').getByRole('link',{name:'论文链接',exact:true}).getAttribute('href'),'https://doi.org/10.1103/PhysRevB.111.054505');
  const structureFile={name:'CONTCAR',mimeType:'text/plain',buffer:Buffer.from('H2La synthetic integration fixture\n1.0\n4 0 0\n0 4 0\n0 0 4\nH La\n2 1\nCartesian\n0 0 0\n1 0 0\n2 2 2\n')};
  const hydrogen={name:'PDOS_H.dat',mimeType:'text/plain',buffer:Buffer.from('-1 0.01\n0 0.02\n1 0.03\n')},metal={name:'PDOS_La.dat',mimeType:'text/plain',buffer:Buffer.from('-1 0.01\n0 0.01\n1 0.01\n')};
  await page.getByLabel('CONTCAR / POSCAR 文件',{exact:true}).setInputFiles(structureFile);await page.getByLabel('电子 PDOS 文件',{exact:true}).setInputFiles([hydrogen,metal]);
  const pagesBefore=context.pages().length, urlBefore=page.url();
  const legacyResponse=page.waitForResponse(r=>r.url().endsWith('/api/tc-predict/') && r.request().method()==='POST');await button('运行模型 →').click();const legacyReply=await legacyResponse;assert.equal(legacyReply.status(),200);const legacyData=await legacyReply.json();

  // 相同两文件请求经原始 API 和 Demo 代理应逐字段一致；不用 Mock 替代计算。
  const originalBody=new FormData();originalBody.append('contcar',new Blob([structureFile.buffer]),structureFile.name);originalBody.append('pdos_files',new Blob([hydrogen.buffer]),hydrogen.name);originalBody.append('pdos_files',new Blob([metal.buffer]),metal.name);
  const original=await fetch('http://127.0.0.1:8080/api/tc-predict/',{method:'POST',body:originalBody});assert.equal(original.status,200);assert.deepEqual(legacyData,await original.json());
  await page.locator('[data-result="legacy"]').waitFor();const card=page.locator('[data-result="legacy"]');assert((await card.textContent()).includes('E_couple'));assert((await card.textContent()).includes(String(legacyData.predicted_tc)));assert.equal(page.url(),urlBefore);assert.equal(context.pages().length,pagesBefore);report.legacy={input:'合成 H2La 接口夹具，不用于科学评估',response:legacyData};await shot('demo-clathrate-inline');check('论文原名显示，CONTCAR＋多个 PDOS 在当前页面真实运行，与原 API 逐字段一致且无跳转');
  await page.getByLabel('电子 PDOS 文件',{exact:true}).setInputFiles(metal);const missingH=page.waitForResponse(r=>r.url().endsWith('/api/tc-predict/'));await button('运行模型 →').click();assert.equal((await missingH).status(),400);await page.getByRole('alert').waitFor();assert((await page.getByRole('alert').textContent()).includes('PDOS_H'));assert(await card.isVisible());check('缺少氢 PDOS 显示原接口错误，已成功结果保留');
  await page.getByRole('tab',{name:/常压常规材料/}).click();await choose('SISSO · 81 样本');await aligned();await download('sisso-81');assert.equal(await page.getByRole('button',{name:'运行模型 →',exact:true}).count(),0);check('81 样本资料候选可下载，未伪装成已接入推理');
  await choose('BETE-NET · CSO');await shot('demo-results');await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile');
  await page.getByRole('tab',{name:/高压氢化物/}).click();await button('加载示例').click();await predict();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile-hydride');check('390px 两组输入、真实运行、数据和结果可操作且无页面横向溢出');
  await choose('Tc assessment model');await page.getByLabel('电子 PDOS 文件',{exact:true}).setInputFiles([hydrogen,metal]);const mobileReply=page.waitForResponse(r=>r.url().endsWith('/api/tc-predict/'));await button('运行模型 →').click();assert.equal((await mobileReply).status(),200);await page.waitForFunction(()=>document.querySelectorAll('[data-result=legacy]').length===2);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile-clathrate');check('390px 原模型上传与当前页结果完整可用');
  assert.equal((await context.request.get(base+'/demo-api/datasets/unknown')).status(),404);assert.deepEqual(report.errors,[]);check('未知数据拒绝下载，无页面脚本错误');
  report.status='passed';fs.writeFileSync(path.join(out,'demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');
 } catch (error) {report.status='failed';report.failure=error.stack;await page.screenshot({path:path.join(out,'demo-browser-failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');throw error}
 finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
