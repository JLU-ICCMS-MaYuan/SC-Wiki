// 从实际模型请求生成结果，验证横条几何与独立展开；不伪造预测数据。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[process.cwd(),runtime]}));
const demo=path.resolve(__dirname,'..'),out=path.resolve(demo,'../assets');
const report={checks:[],errors:[]},base='http://127.0.0.1:5189';
const check=name=>{report.checks.push(name);console.log('PASS',name)};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const run=async()=>{const pending=page.waitForResponse(r=>r.url().endsWith('/demo-api/predict'),{timeout:120000});await page.getByRole('button',{name:'运行模型 →',exact:true}).click();const response=await pending;assert.equal(response.status(),200);const data=await response.json();await page.locator(`[data-result="${data.model_id}"]`).first().waitFor();return data};
 const geometry=()=>page.locator('.result-card').evaluateAll(nodes=>nodes.map(el=>{const r=el.getBoundingClientRect(),s=el.querySelector('.result-summary').getBoundingClientRect();return{id:el.dataset.result,top:r.top,left:r.left,width:r.width,height:r.height,summaryHeight:s.height,expanded:el.dataset.expanded}}));
 const shot=async name=>{await page.waitForTimeout(800);await page.locator('.results').scrollIntoViewIfNeeded();await page.waitForTimeout(200);await page.locator('.results').screenshot({path:path.join(out,name+'.png')})};
 try{
  await page.goto(base);await page.locator('#structure').fill(fs.readFileSync(path.join(__dirname,'fixtures/MgB2.POSCAR'),'utf8'));const nn=await run();
  const bete=page.locator('[data-result="bete-cso"]');assert.equal(await bete.getByRole('button',{name:'展开',exact:true}).getAttribute('aria-expanded'),'false');assert(!(await bete.locator('.spectrum').isVisible()));
  await bete.getByRole('button',{name:'用此参数对比 SISSO →',exact:true}).click();const simple=await run();assert.equal(simple.parameters.lambda,nn.parameters.lambda);
  let rows=await geometry();assert.equal(rows.length,2);assert(rows[0].top<rows[1].top);assert.equal(rows[0].left,rows[1].left);assert.equal(rows[0].width,rows[1].width);assert(rows.every(r=>r.summaryHeight===104 && r.height===106 && r.expanded==='false'));check('真实结构和参数结果从上到下单列排列，默认横条同高 106px');
  await shot('result-rows-collapsed');const simpleRow=page.locator('[data-result="sisso-2019"]');const originalText=await simpleRow.locator('.tc').innerText();
  await bete.getByRole('button',{name:'展开',exact:true}).click();assert(await bete.locator('.spectrum').isVisible());assert.equal(await bete.getByRole('button',{name:'折叠',exact:true}).getAttribute('aria-expanded'),'true');rows=await geometry();assert(rows.find(r=>r.id==='bete-cso').height>106);assert.equal(rows.find(r=>r.id==='sisso-2019').height,106);assert.equal(await simpleRow.locator('.tc').innerText(),originalText);check('只展开当前结果的谱图和完整信息，其他结果保持定高且数值不变');
  await shot('result-rows-expanded');await simpleRow.getByRole('button',{name:'展开',exact:true}).focus();await page.keyboard.press('Enter');assert(await simpleRow.locator('.result-details').isVisible());await bete.getByRole('button',{name:'折叠',exact:true}).click();assert(await simpleRow.locator('.result-details').isVisible());assert.equal((await geometry()).find(r=>r.id==='bete-cso').height,106);check('键盘可展开，折叠另一条不改变当前条的展开状态');
  await page.getByLabel('lambda',{exact:true}).fill('1.6');await run();assert.equal(await page.locator('[data-result="sisso-2019"]').count(),2);assert.equal(await page.locator('[data-result="sisso-2019"]').first().getAttribute('data-expanded'),'false');assert.equal(await page.locator('[data-result="sisso-2019"]').nth(1).getAttribute('data-expanded'),'true');check('新增结果默认折叠，已有结果展开状态保留');
  for(const button of await page.getByRole('button',{name:'折叠',exact:true}).all())await button.click();
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);rows=await geometry();assert(rows.every(r=>r.summaryHeight===124 && r.height===126));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('result-rows-mobile');check('390px 各结果保持同高 126px，单列排列且无页面横向溢出');
  await bete.getByRole('button',{name:'展开',exact:true}).click();assert(await bete.locator('.spectrum').isVisible());assert(await bete.getByRole('button',{name:'折叠',exact:true}).isVisible());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await bete.getByRole('button',{name:'折叠',exact:true}).click();check('窄屏可完整展开谱图并恢复固定高度');
  await page.getByRole('button',{name:'清空结果',exact:true}).click();assert.equal(await page.locator('[data-result]').count(),0);assert.deepEqual(report.errors,[]);check('清空移除所有横条与展开区，无脚本错误');
  report.status='passed';report.desktopRowHeight=106;report.mobileRowHeight=126;report.predictions={beteTc:nn.tc,sissoTc:simple.tc};fs.writeFileSync(path.join(out,'result-rows-validation.json'),JSON.stringify(report,null,2)+'\n');
 }catch(e){report.status='failed';report.failure=e.stack;fs.writeFileSync(path.join(out,'result-rows-validation.json'),JSON.stringify(report,null,2)+'\n');throw e}finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
