// 使用用户原始 POSCAR，验证真实浏览器输入和真实模型 API；不替换推理响应。
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const runtime = path.join(process.env.HOME, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = require(require.resolve('playwright', { paths: [process.cwd(), runtime] }));
const demo = path.resolve(__dirname, '..'), out = path.resolve(demo, '../assets');
const input = fs.readFileSync(path.join(__dirname, 'fixtures/MgB2.POSCAR'), 'utf8');
const base = 'http://127.0.0.1:5189';
const report = { checks: [], errors: [], results: [] };
const check = text => { report.checks.push(text); console.log('PASS', text) };
async function main() {
 const browser = await chromium.launch({headless:true,channel:'chrome'}), context = await browser.newContext({viewport:{width:1440,height:1000}}), page = await context.newPage();
 page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const run = async () => {const pending=page.waitForResponse(r=>r.url().endsWith('/demo-api/predict'),{timeout:120000});await page.getByRole('button',{name:'运行模型 →',exact:true}).click();const response=await pending;return {status:response.status(),body:await response.json(),request:response.request().postDataJSON()}};
 try {
  await page.goto(base);await page.locator('#structure').waitFor();assert.equal(await page.getByLabel('结构格式').inputValue(),'auto');
  await page.locator('#structure').fill(input);const auto=await run();assert.equal(auto.status,200);assert.equal(auto.request.format,'auto');assert.equal(auto.request.structure,input);assert.equal(auto.body.input_format,'vasp');assert.equal(auto.body.formula,'B2Mg');assert.equal(auto.body.ensemble_size,100);report.results.push({case:'用户 POSCAR 默认自动识别',...auto.body});check('用户完整 POSCAR 不修改内容即可自动识别并运行 100 网络模型');
  await page.waitForFunction(()=>document.querySelector('[data-result="bete-cso"]')?.textContent.includes('POSCAR / CONTCAR'));await page.waitForTimeout(700);await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await page.waitForTimeout(200);await page.screenshot({path:path.join(out,'mg-b2-poscar-success.png'),fullPage:true});
  const explicit=await context.request.post(base+'/demo-api/predict',{data:{model_id:'bete-cso',structure:input,format:'vasp'}});assert.equal(explicit.status(),200);const explicitBody=await explicit.json();assert(Math.abs(explicitBody.tc-auto.body.tc)<1e-10);check('自动识别与显式 POSCAR 的真实输出一致');
  const omitted=await context.request.post(base+'/demo-api/predict',{data:{model_id:'bete-cso',structure:input}});assert.equal(omitted.status(),200);assert.equal((await omitted.json()).input_format,'vasp');check('API 未指定格式时同样自动识别');
  await page.getByLabel('结构格式').selectOption('cif');const wrong=await run();assert.equal(wrong.status,400);assert(wrong.body.detail.includes('当前选择了 CIF') && wrong.body.detail.includes('POSCAR'));assert.equal(await page.locator('#structure').inputValue(),input);assert.equal(await page.locator('[data-result]').count(),1);check('手动选错 CIF 时提示具体不匹配原因，输入与成功结果保留');
  await page.locator('#structure').evaluate((el,text)=>{const data=new DataTransfer();data.setData('text/plain',text);el.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,clipboardData:data}))},input);await page.locator('#structure').fill(input);assert.equal(await page.getByLabel('结构格式').inputValue(),'auto');const pasted=await run();assert.equal(pasted.status,200);check('粘贴事件将遗留的手动格式切回自动识别');
  await page.getByLabel('结构格式').selectOption('cif');await page.locator('.upload input').setInputFiles({name:'wrong-extension.cif',mimeType:'text/plain',buffer:Buffer.from(input)});assert.equal(await page.getByLabel('结构格式').inputValue(),'auto');const uploaded=await run();assert.equal(uploaded.status,200);assert.equal(uploaded.body.input_format,'vasp');check('上传按内容识别，不被错误的 .cif 后缀误导');
  await page.getByRole('button',{name:'Nb 铌',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#structure').value.includes('_cell_length'));assert.equal(await page.getByLabel('结构格式').inputValue(),'auto');const cif=await run();assert.equal(cif.status,200);assert.equal(cif.body.input_format,'cif');report.results.push({case:'作者 CIF 自动识别',...cif.body});check('作者 CIF 示例仍可自动识别并实际运行');
  const previous=await page.locator('[data-result]').count();await page.locator('#structure').fill('broken structure');const bad=await run();assert.equal(bad.status,400);assert(bad.body.detail.includes('完整的 CIF 或 POSCAR'));assert.equal(await page.locator('[data-result]').count(),previous);check('无效内容仍拒绝，不以自动识别绕过校验');
  assert.deepEqual(report.errors,[]);report.status='passed';fs.writeFileSync(path.join(out,'structure-format-validation.json'),JSON.stringify(report,null,2)+'\n');
 } catch(e) {report.status='failed';report.failure=e.stack;fs.writeFileSync(path.join(out,'structure-format-validation.json'),JSON.stringify(report,null,2)+'\n');throw e}
 finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
