// 对实际 Demo 执行鼠标操作和浏览器存储验证；不模拟编辑核心，不访问业务 API。
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const runtime = process.env.CODEX_RUNTIME_NODE_MODULES || path.join(process.env.HOME, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = require(require.resolve('playwright', { paths: [process.cwd(), runtime] }));
const root = path.resolve(__dirname, '..'), out = process.env.SCWIKI_SPECTRUM_BROWSER_OUT || path.resolve(root, '../assets');
const samples = JSON.parse(fs.readFileSync(path.join(root, 'src/fixtures.json'), 'utf8'));
const base = process.env.SPECTRUM_DEMO_URL || 'http://127.0.0.1:5187';
const report = { checks: [], errors: [], apiRequests: [], downloads: [], screenshots: [] };
const check = name => { report.checks.push(name); console.log('PASS', name) };
async function main() {
 const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
 const context = await browser.newContext({ viewport: {width:1440,height:1000} });
 context.on('page', page => {page.on('pageerror',e=>report.errors.push(e.message));page.on('download',d=>report.downloads.push(d.suggestedFilename()))});
 context.on('request', r => { if(new URL(r.url()).pathname.startsWith('/api/')) report.apiRequests.push({url:r.url(),method:r.method()}) });
 const page = await context.newPage();page.setDefaultTimeout(10000);
 const shot = async name => {await page.screenshot({path:path.join(out,'chain-demo-'+name+'.png'),fullPage:true});report.screenshots.push('chain-demo-'+name+'.png')};
 const button = name => page.getByRole('button',{name,exact:true});
 const svg = () => page.getByRole('application',{name:'谱线人工编辑画布'});
 const screen = (x,y) => svg().evaluate(async(el,p)=>{await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));const v=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return {x:v.x,y:v.y}}, {x,y});
 const clickAt = async(x,y) => {const p=await screen(x,y);await page.mouse.click(p.x,p.y)};
 const points = () => page.locator('[data-point]').evaluateAll(nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.point,{x:Number(n.dataset.x),y:Number(n.dataset.y)}])));
 const drag = async(id,dx,dy) => {const p=(await points())[id];const a=await screen(p.x,p.y),b=await screen(p.x+dx,p.y+dy);await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:8});await page.mouse.up()};
 const assertFit=async()=>{
  await button('适应窗口').click();
  await page.waitForFunction(()=>{
    const svg=document.querySelector('.source-canvas'),r=svg.getBoundingClientRect(),toolbar=document.querySelector('.canvas-toolbar').getBoundingClientRect(),footer=document.querySelector('.canvas-caption').getBoundingClientRect();
    const texts=[...svg.querySelectorAll('[data-testid="axes-overlay"] text')];
    const [x,y,w,h]=svg.dataset.sourceCrop.split(',').map(Number),a=new DOMPoint(x,y).matrixTransform(svg.getScreenCTM()),b=new DOMPoint(x+w,y+h).matrixTransform(svg.getScreenCTM());
    const horizontal=svg.querySelector('[data-testid="current-axes"]')?.dataset.frequencyDirection==='y'?'current-amplitude':'current-frequency';
    const labels=[...svg.querySelectorAll(`[data-axis-tick="${horizontal}"] text`)].map(t=>t.getBoundingClientRect()).sort((a,b)=>a.left-b.left);
    const separated=labels.every((b,i)=>i===0 || b.left>=labels[i-1].right+1);
    return separated && toolbar.bottom<=r.top+.5 && footer.top>=r.bottom-.5 && a.x>=r.left-.5 && a.y>=r.top-.5 && b.x<=r.right+.5 && b.y<=r.bottom+.5 && texts.every(t=>{const b=t.getBoundingClientRect();return b.left>=r.left-.5&&b.right<=r.right+.5&&b.top>=r.top-.5&&b.bottom<=r.bottom+.5});
  });
 };
 const stored = id => page.evaluate(id=>JSON.parse(localStorage.getItem('scwiki-spectrum-manual-v1:'+id)),id);
 try {
  await page.goto(base);await button('✎ 编辑').waitFor();
  const influence=await page.evaluate(async()=>({... (await import('/src/dragInfluence.ts')).DRAG_INFLUENCE}));report.influenceConfig=influence;
  const expectedWeight=d=>{const w=d<=influence.coreNeighbors?1-(1-influence.edgeWeight)*d/influence.coreNeighbors:influence.edgeWeight*Math.exp(-(d-influence.coreNeighbors)/influence.decayLength);return w<influence.minWeight?0:w};
  const support=Array.from({length:1001},(_,i)=>expectedWeight(i)).filter(w=>w>0).length;const slider=()=>page.getByRole('slider',{name:'原图不透明度'});
  await assertFit();check('详情适应窗口完整包含原图子图和全部轴文字，工具栏/说明不覆盖绘图区');
  const detailSvg=page.locator('.source-canvas'),beforePan=await detailSvg.getAttribute('data-viewbox'),detailPaths=await page.locator('[data-curve]').evaluateAll(ns=>ns.map(n=>n.getAttribute('d')));let boxPan=await detailSvg.boundingBox();
  await page.mouse.move(boxPan.x+boxPan.width/2,boxPan.y+boxPan.height/2);await page.mouse.down({button:'right'});await page.mouse.move(boxPan.x+boxPan.width/2+50,boxPan.y+boxPan.height/2+25,{steps:6});await page.mouse.up({button:'right'});assert.notEqual(await detailSvg.getAttribute('data-viewbox'),beforePan);assert.deepEqual(await page.locator('[data-curve]').evaluateAll(ns=>ns.map(n=>n.getAttribute('d'))),detailPaths);check('详情图窗右键平移可用且曲线数据不变');
  await assertFit();const fitWidth=Number((await detailSvg.getAttribute('data-viewbox')).split(',')[2]);await button('缩小').click();assert(Math.abs(Number((await detailSvg.getAttribute('data-viewbox')).split(',')[2])/fitWidth-1.05)<.00001);await button('放大').click();await assertFit();check('缩放按钮约5%步幅，可逆回到完整适应');
  boxPan=await detailSvg.boundingBox();await page.mouse.move(boxPan.x+boxPan.width/2,boxPan.y+boxPan.height/2);await page.mouse.wheel(0,2);await page.waitForFunction(w=>Number(document.querySelector('.source-canvas').dataset.viewbox.split(',')[2])>w,fitWidth);const slowWidth=Number((await detailSvg.getAttribute('data-viewbox')).split(',')[2]);await page.mouse.wheel(0,120);await page.waitForFunction(w=>Number(document.querySelector('.source-canvas').dataset.viewbox.split(',')[2])>w,slowWidth);const fastWidth=Number((await detailSvg.getAttribute('data-viewbox')).split(',')[2]);assert(slowWidth/fitWidth-1<.002);assert(fastWidth/slowWidth-1>(slowWidth/fitWidth-1)*20);await assertFit();check('细小滚轮输入精细缩放，快速大量滚动缩放更快');

  assert.equal(await slider().inputValue(),'100');await slider().scrollIntoViewIfNeeded();let rail=await slider().boundingBox(),drawing=await page.locator('.source-canvas').boundingBox();assert(rail.height>rail.width*4 && rail.x<drawing.x);check('详情图卡左侧为竖向0–100原图不透明度滑条');
  const initialPaths=await page.locator('[data-curve]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('d')));
  await slider().focus();await slider().press('Home');assert.equal(await slider().inputValue(),'0');assert.equal(await page.getByTestId('source-image').getAttribute('opacity'),'0');assert.deepEqual(await page.locator('[data-curve]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('d'))),initialPaths);assert(await page.getByTestId('axes-overlay').isVisible());await shot('opacity-zero');
  await slider().press('End');assert.equal(await slider().inputValue(),'100');assert.equal(await page.getByTestId('source-image').getAttribute('opacity'),'1');check('0%隐藏原图、100%完整显示，数据曲线与坐标轴不变');
  rail=await slider().boundingBox();await page.mouse.move(rail.x+rail.width/2,rail.y+8);await page.mouse.down();await page.mouse.move(rail.x+rail.width/2,rail.y+rail.height*.6,{steps:8});await page.mouse.up();const opacityValue=Number(await slider().inputValue());assert(opacityValue>25 && opacityValue<55);assert(Math.abs(Number(await page.getByTestId('source-image').getAttribute('opacity'))-opacityValue/100)<.00001);
  await slider().focus();await slider().press('ArrowUp');assert.equal(Number(await slider().inputValue()),opacityValue+1);await slider().press('ArrowDown');assert.equal(Number(await slider().inputValue()),opacityValue);check('鼠标竖向拖动和方向键可按1%调节');
  await button('仅提取数据').click();assert(await slider().isDisabled());assert.equal(await page.getByTestId('source-image').count(),0);await button('原图与数据叠加').click();assert.equal(Number(await slider().inputValue()),opacityValue);assert.equal(await page.evaluate(()=>localStorage.getItem('scwiki-spectrum-manual-v1:alpha2f')),null);check('隐藏原图时禁用滑条但保留值，显示设置不写科学草稿');
  await shot('demo-alpha-detail');
  assert.equal(await page.getByRole('button',{name:/导出|下载/}).count(),0);
  await button('✎ 编辑').click();await svg().waitFor();await assertFit();assert.equal(await page.getByText(/选择一个点，拖动修正局部形状/).count(),0);assert.equal(await page.locator('.tool-hint').count(),0);assert.equal(await page.getByTestId('zero-steps').count(),0);check('编辑器适应窗口完整，通用提示与空占位已移除，无零频核对步骤');rail=await slider().boundingBox();drawing=await svg().boundingBox();assert(rail.height>rail.width*4 && rail.x<drawing.x);assert.equal(Number(await slider().inputValue()),opacityValue);await button('← 返回详情').click();assert.equal(await page.getByRole('dialog').count(),0);assert.equal(Number(await slider().inputValue()),opacityValue);await button('✎ 编辑').click();await button('隐藏原图').click();assert(await slider().isDisabled());await button('显示原图').click();assert.equal(Number(await slider().inputValue()),opacityValue);check('编辑画布左侧竖向滑条与详情共用值，单调显示不产生未保存数据提示');
  const recognizedTicks=await page.locator('[data-axis-tick="recognized-frequency"]').evaluateAll(nodes=>nodes.map(n=>[Number(n.dataset.pixel),Number(n.dataset.value)]));assert.deepEqual(recognizedTicks,[[435,0],[311,20],[188,40],[65,60]]);
  assert.equal(await page.locator('[data-axis-tick="recognized-lambda"]').count(),5);assert(await page.getByText('累计 λ · 识别参考',{exact:true}).isVisible());assert.equal(await page.getByTestId('calibrated-zero').count(),0);check('原图叠加真实记录的频率刻度与独立λ参考，普通坐标刻度保持，无专用零频核对线');
  await button('轴与刻度').click();assert.equal(await page.getByTestId('axes-overlay').count(),0);await button('轴与刻度').click();check('辅助轴可隐藏/恢复，不修改点');
  const start=await points();assert.equal(Object.keys(start).length,samples[0].curves[0].points.length);
  assert((await button('自由移动（X / Y）').getAttribute('class')).includes('active'));
  await page.getByLabel('附近点联动').uncheck();await drag('a-200',3,-3);const xy=await points();assert(Math.abs(xy['a-200'].x-start['a-200'].x-3)<.01);assert(Math.abs(xy['a-200'].y-start['a-200'].y+3)<.01);await button('↶ 撤销').click();assert.deepEqual(await points(),start);await page.getByLabel('附近点联动').check();check('默认X/Y自由移动，竖向可越过旧邻点频率，撤销恢复原坐标');
  const id='a-200';assert(start[id]);await drag(id,8,0);const moved=await points();
  assert(Math.abs(moved[id].x-start[id].x-8)<.01);assert.equal(moved[id].y,start[id].y);assert(Object.keys(start).filter(k=>moved[k].x!==start[k].x).length>1);
  assert.deepEqual(moved['a-50'],start['a-50']);assert.deepEqual(moved['a-legend-0'],start['a-legend-0']);check('α²F 默认二维模式水平拖动：中心/邻点变化，范围外及其他片段不变');

  const centerIndex=samples[0].curves[0].points.findIndex(p=>p.id===id), originalPoints=samples[0].curves[0].points;
  for(const distance of [...new Set([1,influence.coreNeighbors,influence.coreNeighbors+1,support-1,support])].filter(d=>d<20)) {
    const expected=expectedWeight(distance);
    for(const step of [-1,1]) {const p=originalPoints[centerIndex+step*distance];assert(Math.abs((moved[p.id].x-start[p.id].x)/8-expected)<.0001)}
  }check('实际鼠标拖动符合当前用户配置，未要求重置调参值');
  await button('↶ 撤销').click();assert.deepEqual(await points(),start);await button('↷ 重做').click();assert.deepEqual(await points(),moved);check('一次拖动只需一次撤销，重做精确恢复');
  const anchor=await screen(moved[id].x,moved[id].y);await page.mouse.move(anchor.x,anchor.y);await page.mouse.wheel(0,-450);await page.waitForTimeout(150);const after=await screen(moved[id].x,moved[id].y);assert(Math.hypot(anchor.x-after.x,anchor.y-after.y)<2);
  await drag(id,2,0);assert(Math.abs((await points())[id].x-moved[id].x-2)<.01);check('鼠标中心放大后保持锚点，放大选点拖动仍准确');
  const view=await svg().getAttribute('data-viewbox');await page.mouse.move(500,450);await page.mouse.down({button:'right'});await page.mouse.move(540,475,{steps:4});await page.mouse.up({button:'right'});assert.notEqual(await svg().getAttribute('data-viewbox'),view);await button('适应窗口').click();check('右键平移及适应窗口');
  const p=(await points())[id];await clickAt(p.x,p.y);await page.getByLabel('选中点幅值').fill('35');await button('应用坐标到此点').click();assert(Math.abs((await points())[id].x-672)<.01);check('数值输入修改选中点坐标');
  await page.locator('summary').click();const beforeCal=await points();await page.getByLabel('frequency-1-value',{exact:true}).fill('65');await button('应用标定').click();assert.deepEqual(await points(),beforeCal);assert.deepEqual(await page.locator('[data-axis-tick="recognized-frequency"]').evaluateAll(nodes=>nodes.map(n=>[Number(n.dataset.pixel),Number(n.dataset.value)])),recognizedTicks);assert(await page.locator('[data-axis-tick="current-frequency"][data-value="65"]').count());await button('↶ 撤销').click();check('两点标定重新换算，全部源像素位置不变，可撤销');
  await page.getByLabel('频率单位',{exact:true}).selectOption('meV');await button('应用标定').click();assert.deepEqual(await points(),beforeCal);assert.deepEqual(await page.locator('[data-axis-tick="recognized-frequency"]').evaluateAll(nodes=>nodes.map(n=>[Number(n.dataset.pixel),Number(n.dataset.value)])),recognizedTicks);assert(Number(await page.locator('[data-axis-tick="current-frequency"]').last().getAttribute('data-value'))>60);await button('↶ 撤销').click();check('改单位只更新当前刻度，已有识别THz值与点位置保持');
  await page.getByLabel('频率轴方向',{exact:true}).selectOption('x');await button('应用标定').click();assert.equal(await page.getByTestId('current-axes').getAttribute('data-frequency-direction'),'x');assert.equal(await page.locator('[data-axis-tick="current-frequency"][data-value="0"]').getAttribute('data-pixel'),'637');assert.deepEqual(await points(),beforeCal);assert.deepEqual(await page.locator('[data-axis-tick="recognized-frequency"]').evaluateAll(nodes=>nodes.map(n=>[Number(n.dataset.pixel),Number(n.dataset.value)])),recognizedTicks);await button('↶ 撤销').click();check('频率轴切换为横轴时蓝色轴同步，已有识别轴与源像素不变');

  await page.locator('summary').click();
  await button('▣ 框选').click();let a=await screen(735,409),b=await screen(754,416);await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:5});await page.mouse.up();await page.getByRole('button',{name:/删除选中点/}).click();const deleted=await points();assert.equal(Object.keys(deleted).filter(k=>k.startsWith('a-legend')).length,0);check('框选删除图例误识别点');
  await page.locator('[data-row]').first().click();await button('＋ 增加点').click();await clickAt(649,430.5);assert.equal(Object.keys(await points()).length,Object.keys(deleted).length+1);check('在原图缺失区域人工补点');
  assert(await page.getByLabel('选中点频率').isVisible());assert(Math.abs(Number(await page.getByTestId('point-x').textContent())-649)<.001);assert(Math.abs(Number(await page.getByTestId('point-y').textContent())-430.5)<.001);assert(await page.getByTestId('selected-point-projection').isVisible());check('新增点自动选中并显示X/Y、换算坐标及投影');

  const withAdded=await points();const addedId=Object.keys(withAdded).find(k=>!deleted[k]);
  const linkPath=await page.locator('[data-curve="alpha"]').getAttribute('d');
  assert(linkPath.includes(' L'+withAdded[addedId].x+','+withAdded[addedId].y));check('选中起点后补点只连接明确前驱，未插入额外点');const finishAt=await screen(withAdded[addedId].x,withAdded[addedId].y);await page.mouse.dblclick(finishAt.x,finishAt.y);assert.equal(await page.locator('.tool-add').count(),0);assert.equal(Object.keys(await points()).length,Object.keys(withAdded).length);check('Demo双击已有末点结束，不重复加点');

  assert.equal(await page.getByRole('button',{name:'1 · 标记原图 0 频率位置',exact:true}).count(),0);
  assert.equal(await page.getByTestId('saved-zero-check').count(),0);
  await button('↖ 选点 / 拖动').click();await button('保存调整').click();await button('✎ 编辑').waitFor();
  const savedAlpha=await stored('alpha2f');assert.equal(Object.hasOwn(savedAlpha,'zero'),false);
  assert.equal(Number(await slider().inputValue()),opacityValue);
  await page.reload();await button('✎ 编辑').click();
  assert.deepEqual(await points(),Object.fromEntries(savedAlpha.curves[0].points.map(p=>[p.id,{x:p.x,y:p.y}])));
  check('无人工零频步骤也可保存和刷新，坐标及不透明度保持');
  await button('← 返回详情').click();
  await button('声子 DOS').click();assert.equal(await page.locator('[data-axis-tick="recognized-lambda"]').count(),0);assert.equal(await page.locator('[data-axis-tick="recognized-frequency"]').count(),4);check('PhDOS共用频率识别，未把λ或相对像素冒充DOS识别幅值');await shot('demo-dos-detail');await button('✎ 编辑').click();await page.getByRole('button',{name:/^H \d/}).click();const h=await points();const hid=Object.keys(h).find(k=>k==='H-200');assert(hid);await drag(hid,5,0);await shot('demo-dos-editor');await button('保存调整').click();const savedDos=await stored('phdos');for(const c of samples[1].curves.filter(c=>c.id!=='H'))assert.deepEqual(savedDos.curves.find(v=>v.id===c.id),c);check('PhDOS 只编辑所选 H 分波，La/Sc 保持原样');
  await button('✎ 编辑').click();await page.getByRole('button',{name:/^La \d/}).click();const la=await points();await button('自由移动（X / Y）').click();await page.getByLabel('附近点联动').uncheck();await drag('La-420',2,-.2);const laAfter=await points();assert.notDeepEqual(laAfter['La-420'],la['La-420']);assert.deepEqual(laAfter['La-419'],la['La-419']);check('二维单点模式可同时改频率和幅值，其余点不动');
  await button('← 返回详情').click();await button('保存并返回').click();await button('✎ 编辑').waitFor();check('未保存退出：保存并返回');
  await page.setViewportSize({width:390,height:844});await assertFit();check('窄屏适应窗口也完整包含轴标题与刻度');await shot('demo-mobile-detail');rail=await slider().boundingBox();drawing=await page.locator('.source-canvas').boundingBox();assert(rail.height>rail.width*4 && rail.x<drawing.x);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await button('✎ 编辑').click();await svg().waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('demo-mobile-editor');check('390px 详情和全屏编辑器无页面横向溢出');
  await button('← 返回详情').click();await page.setViewportSize({width:1440,height:1000});
  await button('✎ 编辑').click();await page.locator('summary').click();await page.getByLabel('frequency-0-value',{exact:true}).fill('1');await button('← 返回详情').click();await page.getByRole('dialog').waitFor();await button('放弃修改').click();check('未应用标定表单也有退出保护，放弃后恢复已保存标定');
  await button('✎ 编辑').click();await page.locator('summary').click();await page.getByLabel('frequency-1-pixel',{exact:true}).fill('435');await button('应用标定').click();assert((await page.getByRole('alert').textContent()).includes('互不重合'));await button('← 返回详情').click();await button('放弃修改').click();check('退化标定拒绝应用，保留已有点');
  // 同一真实页面，通过存储平台异常验证失败路径，不替换编辑逻辑。
  await button('✎ 编辑').click();await button('恢复原始提取').click();await page.evaluate(()=>{window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new DOMException('Demo quota test','QuotaExceededError')}});await button('保存调整').click();assert(await svg().isVisible());assert((await page.getByRole('alert').textContent()).includes('保存失败'));assert.equal(await page.getByTestId('saved-zero-check').count(),0);await page.evaluate(()=>{Storage.prototype.setItem=window.originalSetItem});check('localStorage 写入失败保留编辑内容并提示，未假报保存成功');
  await button('← 返回详情').click();await button('放弃修改').click();await page.evaluate(()=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f','{broken'));await button('α²F 谱函数').click();assert((await page.getByRole('alert').textContent()).includes('不可读取'));assert.equal(await page.evaluate(()=>localStorage.getItem('scwiki-spectrum-manual-v1:alpha2f')),'{broken');check('损坏草稿提示错误，不静默覆盖');
  await button('✎ 编辑').click();await button('恢复原始提取').click();await button('保存调整').click();check('显式恢复后允许替换损坏草稿');
  await page.setViewportSize({width:390,height:844});await button('✎ 编辑').click();await page.locator('[data-row="a-200"]').click();await page.getByLabel('选中点幅值').fill('28');await button('应用坐标到此点').click();assert(Math.abs((await points())['a-200'].x-665)<.01);await shot('demo-mobile-inspector');await button('保存调整').click();await button('✎ 编辑').waitFor();check('窄屏侧栏数据表选点、坐标修改及顶部保存均可操作');
  await page.route('**/fixtures/source.png',route=>route.abort());await page.reload();await button('✎ 编辑').click();await page.getByText('原图加载失败，暂不能选点。').waitFor();const imageFailPoints=await points();await button('＋ 增加点').click();await clickAt(649,430.5);assert.deepEqual(await points(),imageFailPoints);await page.unroute('**/fixtures/source.png');await button('重试图片').click();await page.waitForFunction(()=>!document.querySelector('.canvas-error'));check('原图失败禁用图上选点，重试可恢复');

  await button('← 返回详情').click();await page.setViewportSize({width:1440,height:1000});
  const legacy=structuredClone(samples[0]);legacy.curves[0].points.push({id:'legacy-added',x:649,y:430.5,segment:'legacy-isolated',status:'人工调整'});
  const oldJson=JSON.stringify(legacy);await page.evaluate(value=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f',value),oldJson);await page.reload();await button('✎ 编辑').click();
  assert.deepEqual((await points())['legacy-added'],{x:649,y:430.5});assert.equal(await page.evaluate(()=>localStorage.getItem('scwiki-spectrum-manual-v1:alpha2f')),oldJson);
  const oldPath=await page.locator('[data-curve="alpha"]').getAttribute('d');assert(oldPath.includes('M649,430.5 L'));await shot('legacy-connected');check('旧草稿已移动的人工散点恢复后自动连线，坐标和原存储不变');
  await clickAt(649,430.5);await page.getByRole('button',{name:/删除选中点/}).click();await button('↶ 撤销').click();assert((await page.locator('[data-curve="alpha"]').getAttribute('d')).includes('M649,430.5 L'));await button('保存调整').click();await page.reload();await button('✎ 编辑').click();assert((await page.locator('[data-curve="alpha"]').getAttribute('d')).includes('M649,430.5 L'));check('补点连线撤销及保存刷新后保持');

  await button('← 返回详情').click();
  const userRaw=fs.readFileSync(path.resolve(__dirname,'../../assets/user-saved-alpha-xy.json'),'utf8'),userDoc=JSON.parse(userRaw);
  await page.evaluate(v=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f',v),userRaw);await page.reload();await button('✎ 编辑').click();
  const userCoords=Object.fromEntries(userDoc.curves[0].points.map(p=>[p.id,{x:p.x,y:p.y}]));assert.deepEqual(await points(),userCoords);assert.equal(await page.evaluate(()=>localStorage.getItem('scwiki-spectrum-manual-v1:alpha2f')),userRaw);
  const oldUserPath=await page.locator('[data-curve="alpha"]').getAttribute('d');await shot('user-before-reconnect');await button('重新连接人工补点').click();assert.deepEqual(await points(),userCoords);await shot('user-after-reconnect');
  if(await button('↶ 撤销').isEnabled()){await button('↶ 撤销').click();assert.equal(await page.locator('[data-curve="alpha"]').getAttribute('d'),oldUserPath);await button('↷ 重做').click()}
  await button('保存调整').click();await page.reload();await button('✎ 编辑').click();assert.deepEqual(await points(),userCoords);check('真实399点43操作草稿恢复、局部重连和保存刷新，所有坐标不变');
  await button('← 返回详情').click();
  const small=structuredClone(samples[0]);small.curves[0].points=[{id:'before',x:679.7,y:302.51,segment:'s',status:'原始'},{id:'old-end',x:685.13,y:302.24,segment:'s',status:'原始'}];
  await page.evaluate(v=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f',JSON.stringify(v)),small);await page.reload();await button('✎ 编辑').click();
  await page.locator('[data-row="old-end"]').click();await svg().evaluate(el=>el.setAttribute('viewBox','676 300 15 5'));await button('＋ 增加点').click();await clickAt(687.8,302.30);
  const pathAfter=await page.locator('[data-curve="alpha"]').getAttribute('d');assert(pathAfter.startsWith('M679.7,302.51 L685.13,302.24 M685.13,302.24 L687.'));const idsAfter=await page.locator('[data-point]').evaluateAll(nodes=>nodes.map(n=>n.dataset.point));assert.deepEqual(idsAfter.slice(0,2),['before','old-end']);await shot('end-extension-regression');check('截图日志坐标真实点击：右侧新点y略大仍延长端点，不回折');
  await button('保存调整').click();
  const folded=structuredClone(small);folded.curves[0].points.push({id:'new-point',x:687.8,y:302.30,segment:'s',manual:true,status:'人工补选'});
  await page.evaluate(v=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f',JSON.stringify(v)),folded);await page.reload();await button('✎ 编辑').click();const foldedPath=await page.locator('[data-curve="alpha"]').getAttribute('d');assert(foldedPath.includes('L687.8,302.3 L685.13,302.24'));
  await button('重新连接人工补点').click();const fixedPath=await page.locator('[data-curve="alpha"]').getAttribute('d');assert(fixedPath.includes('L685.13,302.24 L687.8,302.3'));await button('↶ 撤销').click();assert.equal(await page.locator('[data-curve="alpha"]').getAttribute('d'),foldedPath);await button('↷ 重做').click();assert.equal(await page.locator('[data-curve="alpha"]').getAttribute('d'),fixedPath);check('历史回折局部修正：点坐标不变，撤销和重做精确恢复连线');
  await button('保存调整').click();
  await page.evaluate(v=>localStorage.setItem('scwiki-spectrum-manual-v1:alpha2f',JSON.stringify(v)),samples[0]);await page.reload();
  assert.equal(await page.getByTestId('saved-zero-check').count(),0);
  await button('✎ 编辑').click();
  assert.equal(await page.getByRole('button',{name:'确认选中点为零频点',exact:true}).count(),0);
  await button('保存调整').click();
  assert.equal(Object.hasOwn(await stored('alpha2f'),'zero'),false);
  check('旧草稿的零频确认状态不再参与保存或展示');
  report.performance=await page.evaluate(async()=>{
    const engine=await import('/src/engine.ts');
    const doc={schemaVersion:1,id:'perf',source:{plot:[0,0,10000,100]},calibration:{direction:'x',frequency:{pixels:[0,10000],values:[0,100],unit:'THz'},amplitude:{pixels:[100,0],values:[0,1],unit:'pixel'}},curves:[{id:'a',points:Array.from({length:10000},(_,i)=>({id:String(i),x:i,y:50,segment:'s',status:'original'}))}]};
    const begin=performance.now(), prepared=engine.prepareMove(doc,'a','5000',true), prepareMs=performance.now()-begin;
    const times=[];let moved;
    for(let i=0;i<120;i++){const start=performance.now();moved=engine.movePrepared(prepared,0,-2,'amplitude');engine.curvePath(moved,moved.curves[0]);times.push(performance.now()-start)}
    times.sort((a,b)=>a-b);
    return {points:10000,iterations:120,prepareMs,medianMoveAndPathMs:times[60],p95MoveAndPathMs:times[114],weightedPoints:prepared.byId.size,changedPoints:moved.curves[0].points.filter(p=>p.y!==50).length,includesReactRender:false};
  });assert.equal(report.performance.weightedPoints,2*support-1);assert.equal(report.performance.changedPoints,2*support-1);check('10000点按用户配置的有限邻域移动，120次复用准备结果');
  assert.equal(await page.getByRole('button',{name:/导出|下载/}).count(),0);assert.deepEqual(report.apiRequests,[]);assert.deepEqual(report.downloads,[]);assert.deepEqual(report.errors,[]);check('无业务 API 请求、无下载入口/下载事件、无页面脚本错误');
  report.status='passed';fs.writeFileSync(path.join(out,'chain-demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');
 } catch(error) {report.status='failed';report.failure=error.stack;await page.screenshot({path:path.join(out,'browser-failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'chain-demo-browser-validation.json'),JSON.stringify(report,null,2)+'\n');throw error}
 finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
