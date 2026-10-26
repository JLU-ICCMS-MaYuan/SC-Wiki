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
 const context = await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
 const page = await context.newPage(); page.setDefaultTimeout(15000);
 page.on('pageerror', e => report.errors.push(e.message));
 const button = name => page.getByRole('button', {name,exact:true});
 const choose = name => page.getByRole('navigation',{name:'选择模型'}).getByRole('button',{name:new RegExp(name)}).click();
 const shot = async name => {await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(200);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});report.screenshots.push(name+'.png')};
 const predict = async () => {
  const response = page.waitForResponse(r=>r.url().endsWith('/demo-api/predict') && r.request().method()==='POST',{timeout:180000});
  await button('运行模型 →').click(); const r = await response; const body = await r.json();assert.equal(r.status(),200,JSON.stringify(body));
  await page.locator(`[data-result="${body.model_id}"]`).first().waitFor();report.predictions.push(body);return body;
 };
 const download = async id => {
  const expected = catalog.datasets.find(d=>d.id===id), card=page.locator(`[data-dataset="${id}"]`);
  const event = page.waitForEvent('download');await card.getByRole('link',{name:id==='bete-support'?'↓ 下载辅助包':'↓ 下载原文件',exact:true}).click();const file=await event;
  assert.equal(file.suggestedFilename(),expected.filename);const dest=path.join(downloads,expected.filename);await file.saveAs(dest);
  const sha=await digest(dest);assert.equal(sha,expected.sha256);assert.equal(fs.statSync(dest).size,expected.size);
  report.downloads.push({id,filename:file.suggestedFilename(),bytes:expected.size,sha256:sha});
  assert.equal(await card.locator('.original-url>a').getAttribute('href'),expected.original_url);
  assert.equal(await card.getByRole('link',{name:'查看原始发布页 ↗',exact:true}).getAttribute('href'),expected.source_url);
 };
 try {
  await page.goto(base);await page.getByRole('heading',{name:'超导模型实验室Beta'}).waitFor();await page.locator('[data-dataset="bete-data"]').waitFor();
  const reference = await context.newPage();await reference.goto('http://127.0.0.1:5173/tc-predict');await reference.getByRole('heading').first().waitFor();
  const siteTheme = await reference.evaluate(()=>({background:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,font:getComputedStyle(document.body).fontFamily,primary:getComputedStyle(document.querySelector('nav button[aria-label^="SC-Wiki"] span')).backgroundColor}));
  const demoTheme = await page.evaluate(()=>({background:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,font:getComputedStyle(document.body).fontFamily,primary:getComputedStyle(document.querySelector('.brand-mark')).backgroundColor}));
  assert.deepEqual(demoTheme,siteTheme);report.theme={reference:siteTheme,demo:demoTheme};await reference.close();check('与当前 SC-Wiki 实际页面的基础色、文字色、字体和品牌主色一致');
  await shot('demo-desktop');await button('Nb 铌').click();await page.waitForFunction(()=>document.querySelector('#structure').value.includes('Nb'));
  assert.equal(await page.locator('.run').evaluate(el=>getComputedStyle(el).backgroundColor),siteTheme.primary);check('可用的运行按钮使用主站主色');
  const nn = await predict();assert.equal(nn.ensemble_size,100);assert(Number.isFinite(nn.tc) && nn.tc>0);assert.equal(nn.spectrum.a2f.length,51);check('Nb 结构真实运行作者 100 网络集成，返回 Tc 与 51 点谱');
  await download('bete-data');await download('bete-support');check('BETE 原始 JSON 与结构划分辅助包经浏览器下载，原字节摘要一致');
  await page.locator('[data-dataset="bete-data"]').getByRole('button',{name:'预览数据',exact:true}).click();await page.getByRole('dialog').waitFor();assert.equal(await page.getByRole('dialog').locator('tbody tr').count(),5);await button('关闭预览').click();check('真实数据库前 5 条预览可打开、关闭');
  await page.locator('[data-dataset="bete-data"]').getByRole('button',{name:'复制作者原始数据库原始网址',exact:true}).click();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),catalog.datasets[0].original_url);check('原始网址复制正确');
  await button('用此参数对比 SISSO →').click();assert.equal(Number(await page.getByRole('textbox',{name:'lambda',exact:true}).inputValue()),nn.parameters.lambda);
  const sr = await predict();assert.equal(sr.model_id,'sisso-2019');assert.equal(sr.parameters.lambda,nn.parameters.lambda);assert(await page.locator('[data-result="bete-cso"]').isVisible());check('结构预测参数可带入 SISSO 实际计算，保留两个独立结果');
  await download('sisso-train');await download('sisso-published');check('29 条真实训练输入与 43 条发布数据分别下载、分别标注');
  const before = await page.locator('[data-result]').count();await page.getByRole('textbox',{name:'lambda',exact:true}).fill('-1');
  const badResponse=page.waitForResponse(r=>r.url().endsWith('/demo-api/predict'));await button('运行模型 →').click();assert.equal((await badResponse).status(),400);await page.getByRole('alert').waitFor();assert.equal(await page.locator('[data-result]').count(),before);check('非法参数返回错误，已有结果不丢失、不产生伪结果');
  await page.getByRole('tab',{name:/高压氢化物/}).click();await button('加载示例').click();const hp=await predict();assert.equal(hp.model_id,'sisso-2022');assert(hp.tc>0);
  assert(await page.locator('[data-dataset="xie-2022"]').getByRole('button',{name:'暂不可下载',exact:true}).isDisabled());assert.equal((await context.request.get(base+'/demo-api/datasets/xie-2022')).status(),503);check('高压参数模型真实计算；上游训练包失败明确显示且下载接口拒绝空文件');
  await choose('SC-Wiki · 现有估算');const legacy=page.locator('.empty-state').getByRole('link',{name:'打开原有估算 ↗',exact:true});assert.equal(await legacy.getAttribute('href'),'http://127.0.0.1:5173/tc-predict');assert.equal((await context.request.get('http://127.0.0.1:5173/tc-predict')).status(),200);check('现有估算保留，原本地页面可访问');
  await page.getByRole('tab',{name:/常压常规材料/}).click();await choose('SISSO · 81 样本');await download('sisso-81');assert.equal(await page.getByRole('button',{name:'运行模型 →',exact:true}).count(),0);check('81 样本资料候选可下载，未伪装成已接入推理');
  await choose('BETE-NET · CSO');await shot('demo-results');await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile');
  await page.getByRole('tab',{name:/高压氢化物/}).click();await button('加载示例').click();await predict();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile-hydride');check('390px 两组输入、真实运行、数据和结果可操作且无页面横向溢出');
  assert.equal((await context.request.get(base+'/demo-api/datasets/unknown')).status(),404);assert.deepEqual(report.errors,[]);check('未知数据拒绝下载，无页面脚本错误');
  report.status='passed';fs.writeFileSync(path.join(out,'demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');
 } catch (error) {report.status='failed';report.failure=error.stack;await page.screenshot({path:path.join(out,'demo-browser-failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');throw error}
 finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
