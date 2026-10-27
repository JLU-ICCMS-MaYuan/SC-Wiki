// 正式页面 + 正式HTTP谱路由 + 隔离SQLite/文件存储；禁止请求真实业务API。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=process.env.CODEX_RUNTIME_NODE_MODULES||path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend=process.env.SPECTRUM_FRONTEND||'http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));page.setDefaultTimeout(15000);
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{await page.screenshot({path:path.join(out,'snap-production-'+name+'.png'),fullPage:!(await page.locator('.editor-app').count())});report.screenshots.push('snap-production-'+name+'.png')};
 const btn=name=>page.getByRole('button',{name,exact:true});
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined);const data=await r.json();return {status:r.status,data}};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const listing=async()=> (await api('/api/rag/spectra?'+query)).data;
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 try{
  const first=await listing(),alpha=first.items.find(i=>i.result.curves[0].kind==='alpha2f');const old=JSON.stringify(alpha.result);
  await page.goto(address(alpha));await btn('编辑').waitFor({state:'visible'});await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑')?.disabled);await page.getByRole('slider',{name:'原图不透明度'}).focus();await page.getByRole('slider',{name:'原图不透明度'}).press('Home');await page.getByRole('slider',{name:'原图不透明度'}).press('ArrowUp');await shot('detail-before');
  await btn('编辑').click();await page.getByRole('application',{name:'谱线人工编辑画布'}).waitFor();assert.equal(await page.locator('.editor-app input[aria-label="原图不透明度"]').inputValue(),'1');await page.locator('.editor-app input[aria-label="原图不透明度"]').focus();await page.locator('.editor-app input[aria-label="原图不透明度"]').press('End');await shot('editor');
  assert.equal(await page.locator('.spectrum-manual-editor.editor-app').count(),1);
  const editor=page.locator('.editor-app'),canvas=editor.getByRole('application');
  // 工具提示改变画布高度；等待ResizeObserver完成布局后再记录屏幕坐标。
  const stableCanvas=()=>canvas.evaluate(async el=>{
    let previous='',stable=0;
    for(let i=0;i<30;i++){
      await new Promise(resolve=>requestAnimationFrame(resolve));
      const m=el.getScreenCTM(),box=el.getBoundingClientRect();
      const current=JSON.stringify([m.a,m.d,m.e,m.f,box.width,box.height,el.getAttribute('viewBox')]);
      stable=current===previous?stable+1:0;previous=current;
      if(stable>=3)return;
    }
    throw new Error('画布布局未稳定，不能使用旧屏幕坐标验证吸附');
  });
  const currentPoints=()=>editor.locator('[data-point]').evaluateAll(nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.point,{x:Number(n.dataset.x),y:Number(n.dataset.y)}])));
  const clickPixel=async(x,y,double=false)=>{const p=await canvas.evaluate((el,v)=>{const p=new DOMPoint(v.x,v.y).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y}},{x,y});if(double)await page.mouse.dblclick(p.x,p.y);else await page.mouse.click(p.x,p.y)};
  const beforeChain=await currentPoints(),beforePath=await editor.locator('[data-curve="a"]').getAttribute('d');
  await btn('＋ 增加点').click();assert.equal(await btn('＋ 增加点').getAttribute('aria-pressed'),'true');assert.equal(Object.keys(await currentPoints()).length,Object.keys(beforeChain).length);check('没有起点时也可激活增加点，等待选择已有点且数据不变');
  await clickPixel(beforeChain['a:p50'].x,beforeChain['a:p50'].y);assert.deepEqual(await currentPoints(),beforeChain);await clickPixel(65,40);let added=Object.keys(await currentPoints()).filter(id=>!beforeChain[id]);assert.equal(added.length,1);const firstId=added[0];
  await clickPixel(72,38);await clickPixel(75,35,true);added=Object.keys(await currentPoints()).filter(id=>!beforeChain[id]);assert.equal(added.length,3);assert.equal(await editor.locator('.tool-add').count(),0);
  const trace=await editor.locator('[data-curve="a"]').getAttribute('d');assert(trace.startsWith(beforePath));const drawn=await currentPoints();for(let i=1;i<added.length;i++){const parent=drawn[added[i-1]],child=drawn[added[i]];assert(trace.includes('M'+parent.x+','+parent.y+' L'+child.x+','+child.y))}
  await clickPixel(82,33);assert.equal(Object.keys(await currentPoints()).length,Object.keys(beforeChain).length+3);assert.equal(report.writes.length,0);check('连续加点只连前驱，双击仅加入一个末点并退出，不自动提交或继续加点');
  await btn('↶ 撤销').click();assert.equal(Object.keys(await currentPoints()).length,Object.keys(beforeChain).length+2);await btn('↷ 重做').click();assert.equal(Object.keys(await currentPoints()).length,Object.keys(beforeChain).length+3);await shot('chain-ended');check('连续描线可逐点撤销重做，原路径保留');
  const chainPoints=await currentPoints(),lastId=added.at(-1),targetId='a:p100',snapCoordinates=chainPoints[targetId];
  await page.locator(`[data-row="${lastId}"]`).click();await btn('＋ 增加点').click();
  await stableCanvas();const targetScreen=await canvas.evaluate((el,p)=>{const c=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return {x:c.x,y:c.y,scale:el.getScreenCTM().a}},snapCoordinates);
  const previewPosition=await canvas.evaluate((el,p)=>{const c=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return {x:c.x,y:c.y}},chainPoints[added[0]]);
  await page.mouse.move(previewPosition.x+9,previewPosition.y);assert.equal(await editor.getByTestId('snap-target').count(),0);
  await page.mouse.move(previewPosition.x+7,previewPosition.y);await editor.getByTestId('snap-target').waitFor();assert.equal(await editor.getByTestId('snap-target').getAttribute('data-point-id'),added[0]);check('8px外不吸附、8px内高亮最近目标，阈值按屏幕距离');
  await page.mouse.move(targetScreen.x,targetScreen.y+3);await editor.getByTestId('snap-target').waitFor();assert.equal(await editor.getByTestId('snap-target').getAttribute('data-point-id'),targetId);
  await shot('snap-preview');await page.mouse.dblclick(targetScreen.x,targetScreen.y+3);assert.equal(await editor.locator('.tool-add').count(),0);
  assert.deepEqual(await currentPoints(),chainPoints);assert.equal(report.writes.length,0);
  const snappedPath=await editor.locator('[data-curve="a"]').getAttribute('d');assert(snappedPath.includes('M'+chainPoints[lastId].x+','+chainPoints[lastId].y+' L'+snapCoordinates.x+','+snapCoordinates.y));check('双击吸附复用已有目标，坐标和点数不变，只新增连接且不自动提交');
  await btn('↶ 撤销').click();assert(!(await editor.locator('[data-curve="a"]').getAttribute('d')).includes('M'+chainPoints[lastId].x+','+chainPoints[lastId].y+' L'+snapCoordinates.x+','+snapCoordinates.y));await btn('↷ 重做').click();assert.equal(await editor.locator('[data-curve="a"]').getAttribute('d'),snappedPath);check('吸附连接可独立撤销/重做');
  await page.locator(`[data-row="${lastId}"]`).click();await btn('＋ 增加点').click();await page.mouse.move(previewPosition.x,previewPosition.y);await page.mouse.wheel(0,-1200);await page.waitForTimeout(100);
  const zoomed=await canvas.evaluate((el,p)=>{const c=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return {x:c.x,y:c.y}},chainPoints[added[0]]);await page.mouse.move(zoomed.x+7,zoomed.y);await editor.getByTestId('snap-target').waitFor();assert.equal(await editor.getByTestId('snap-target').getAttribute('data-point-id'),added[0]);await btn('单点选点／拖动').click();await editor.getByRole('button',{name:'适应窗口',exact:true}).click();check('缩放后仍按屏幕8px吸附，切工具不生成点或连接');


  await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.08');await btn('应用坐标到此点').click();
  await btn('保存调整').click();
  await page.waitForFunction(()=>!document.querySelector('.editor-app'));assert.equal(await page.getByTestId('saved-zero-check').count(),0);
  const after=await listing(),saved=after.items.find(i=>i.id===alpha.id);assert.notEqual(saved.run.id,alpha.run.id);assert.equal(saved.version,alpha.version+1);assert.equal(saved.result.curves[0].points[50].reconstructed_amplitude,.08);assert.deepEqual(saved.review,{});assert(page.url().includes(saved.run.id));assert.equal(await page.getByRole('slider',{name:'原图不透明度'}).inputValue(),'100');
  assert.equal(saved.result.manual_documents.a.curves[0].points.find(p=>p.id===firstId).connectTo,'a:p50');assert.equal(saved.result.curves[0].points.at(-1).connectTo,added[1]);assert.equal(saved.result.curves[0].points.at(-1).joinTo,targetId);assert.equal(saved.result.manual_documents.a.curves[0].points.at(-1).joinTo,targetId);check('保存入库及回读保留父点ID，不按最近距离改接');assert.equal(saved.result.quality.integrals.raw.status,'unavailable');check('正式详情读取真实接口文档，人工坐标保存到数据库新运行，回跳新版本，无零频核对步骤');assert.equal(await page.getByTestId('manual-integral-boundary').count(),0);assert.equal(await page.getByText('04 · 逐点数据核对',{exact:true}).count(),0);assert.equal(await page.getByText('零频位置核对完成',{exact:true}).count(),0);await btn('重新计算').waitFor();check('详情保留重算入口，无零频完成提示，移除旧解释与重复点表');await shot('saved-detail');
  await page.reload();await btn('编辑').waitFor();assert.equal(await page.getByTestId('saved-zero-check').count(),0);
  const history=(await api('/api/rag/spectra/'+alpha.id+'/runs/'+alpha.run.id+'?'+query)).data;assert.deepEqual(history.result.curves,JSON.parse(old).curves);assert.deepEqual(history.result.calibration,JSON.parse(old).calibration);check('刷新从持久数据库恢复人工结果，原始运行数值未被覆盖');
  await btn('查看提取历史').click();await page.getByRole('button',{name:/合成|时间未记录/}).count(); // 历史载入仍走正式接口。
  await btn('编辑').click();await page.getByRole('application').waitFor();await page.locator('[data-row="a:p50"]').click();await page.getByLabel('选中点幅值').fill('0.09');await btn('应用坐标到此点').click();
  const current=await listing(),item=current.items.find(i=>i.id===alpha.id);
  const input=(await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind=alpha2f&collection_version='+item.version+'&run_id='+item.run.id)).data;
  const competing=await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:input.collection_version,base_run_id:input.base_run_id,document:input.documents[0]});assert.equal(competing.status,200,JSON.stringify(competing.data));
  await btn('保存调整').click();await page.getByRole('alert').filter({hasText:'保存失败'}).waitFor();assert(await page.getByRole('application').isVisible());assert.equal(await page.getByLabel('选中点幅值').inputValue(),'0.09');check('并发新版本产生409冲突，编辑器保留用户坐标而不覆盖数据库');await shot('conflict');
  await btn('← 返回详情').click();await btn('放弃修改').click();
  const dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');await page.goto(address(dos));await btn('编辑').click();await page.getByRole('application').waitFor();
  await page.getByRole('button',{name:'H',exact:true}).click();assert.equal(await page.locator('.editor-app [data-curve]').count(),3);await page.locator('[data-row="H:p50"]').click();await page.getByLabel('选中点幅值').fill('18');await btn('应用坐标到此点').click();await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));
  const dosAfter=(await listing()).items.find(i=>i.id===dos.id);assert.equal(dosAfter.result.curves.find(c=>c.id==='H').points[50].reconstructed_amplitude,18);assert.deepEqual(dosAfter.result.curves.find(c=>c.id==='La'),dos.result.curves.find(c=>c.id==='La'));check('PhDOS分波使用自身标定保存，未编辑的La曲线逐点保持');
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('mobile-detail');await btn('编辑').click();await page.getByRole('application').waitFor();await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('mobile-editor');check('正式页面及全屏编辑器在390px无水平溢出');
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('scwiki-spectrum-manual')).length),0);assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>w.path.endsWith('/manual')));check('正式保存不访问Demo草稿、不重提取，所有写入仅到隔离manual路由');
  report.status='passed';report.database='isolated SQLite file; production SQLAlchemy models and HTTP routes';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'snap-production-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
