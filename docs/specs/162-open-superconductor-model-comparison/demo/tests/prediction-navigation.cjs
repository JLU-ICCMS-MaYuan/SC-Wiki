// 核查已确认的左侧分类／顶部模型布局，使用真实服务验证切换与计算。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[process.cwd(),runtime]}));
const out=path.resolve(__dirname,'../../assets');const report={checks:[],errors:[]};
const check=name=>{report.checks.push(name);console.log('PASS',name)};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const groups=()=>page.getByRole('navigation',{name:'预测分类',exact:true});
 const models=()=>page.getByRole('navigation',{name:'选择模型',exact:true});
 const button=name=>page.getByRole('button',{name,exact:true});
 const shot=async name=>{await page.waitForTimeout(200);await page.screenshot({path:path.join(out,name+'.png'),fullPage:!name.endsWith('-menu')})};
 try{
  await page.goto('http://127.0.0.1:5189/');await models().waitFor();assert.equal(await page.title(),'预测 · SC-Wiki');assert.equal(await page.getByRole('heading',{name:'预测Beta',exact:true}).count(),1);assert(!/模型实验室|常压常规材料/.test(await page.locator('body').innerText()));
  assert.equal(await page.locator('.rail').getByRole('link',{name:'✧ 预测',exact:true}).count(),1);assert.equal(await groups().getByRole('button').count(),2);check('标题、侧栏入口、浏览器标签统一为预测，分类名称按最终确认显示');
  const bounds=await page.evaluate(()=>{const rail=document.querySelector('.rail').getBoundingClientRect(),items=[...document.querySelectorAll('.rail .prediction-groups button')].map(e=>e.getBoundingClientRect()),hero=document.querySelector('.hero').getBoundingClientRect(),picker=document.querySelector('.model-picker').getBoundingClientRect();return {rail:{left:rail.left,right:rail.right},items:items.map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom})),heroBottom:hero.bottom,pickerTop:picker.top}});
  assert(bounds.items.every(r=>r.left>=bounds.rail.left&&r.right<=bounds.rail.right));assert(bounds.items[1].top>=bounds.items[0].bottom);assert(Math.abs(bounds.pickerTop-bounds.heroBottom)<2);assert.equal(await page.locator('.group-bar').count(),0);const tops=await models().getByRole('button').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().top));assert(tops.every(t=>Math.abs(t-tops[0])<1));check('两分类纵向位于左侧预测下方，模型横排直接接在页头之后，不再保留旧分类栏');await shot('prediction-navigation-desktop');
  await models().getByRole('button',{name:/SISSO · Xie 2019/}).click();await groups().getByRole('button',{name:'常压 BCS 超导体',exact:true}).click();assert(await page.getByRole('heading',{name:'SISSO · Xie 2019',exact:true}).isVisible());check('点击已选分类不会重置当前模型');
  await groups().getByRole('button',{name:'高压氢化物',exact:true}).click();assert.equal(await models().getByRole('button').count(),2);assert(await page.getByRole('heading',{name:'SISSO · Xie 2022',exact:true}).isVisible());assert.equal(await groups().getByRole('button',{name:'高压氢化物',exact:true}).getAttribute('aria-pressed'),'true');
  await button('加载示例').click();const response=page.waitForResponse(r=>r.url().endsWith('/demo-api/predict'));await button('运行模型 →').click();assert.equal((await response).status(),200);await page.locator('[data-result="sisso-2022"]').waitFor();await groups().getByRole('button',{name:'常压 BCS 超导体',exact:true}).click();assert.equal(await models().getByRole('button').count(),3);assert(await page.locator('[data-result="sisso-2022"]').isVisible());check('左侧分类联动顶部模型和表单，真实计算可用，切换后已有结果保留');
  await page.setViewportSize({width:800,height:1000});await groups().getByRole('button',{name:'高压氢化物',exact:true}).click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));check('800px 保留可读左侧分类，输入／来源响应式堆叠且不溢出');
  await page.setViewportSize({width:390,height:844});await button('选择分类').click();const dialog=page.getByRole('dialog',{name:'预测分类菜单',exact:true});assert(await dialog.isVisible());const box=await dialog.boundingBox();assert(box.x<=1);await dialog.getByRole('button',{name:'常压 BCS 超导体',exact:true}).click();assert(!(await dialog.isVisible()));assert.equal(await models().getByRole('button').count(),3);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));check('390px 从左侧分类抽屉切换，选择后关闭且模型联动');await page.evaluate(()=>window.scrollTo(0,0));await shot('prediction-navigation-mobile');
  await button('选择分类').click();await shot('prediction-navigation-mobile-menu');await page.keyboard.press('Escape');assert(!(await dialog.isVisible()));assert(await button('选择分类').evaluate(e=>e===document.activeElement));check('分类抽屉支持 Escape 关闭并返回触发按钮焦点');
  assert.deepEqual(report.errors,[]);report.status='passed';fs.writeFileSync(path.join(out,'prediction-navigation-validation.json'),JSON.stringify(report,null,2)+'\n');
 }catch(e){report.status='failed';report.failure=e.stack;fs.writeFileSync(path.join(out,'prediction-navigation-validation.json'),JSON.stringify(report,null,2)+'\n');throw e}finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
