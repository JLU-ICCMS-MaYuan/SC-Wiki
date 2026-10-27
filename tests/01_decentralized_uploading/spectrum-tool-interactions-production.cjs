// #165：真实正式React/HTTP/SQLite；所有API仅发往专用隔离测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8195',frontend='http://127.0.0.1:5175',out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT;
assert(out);fs.mkdirSync(out,{recursive:true});
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});
  const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response});
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true}),editor=page.locator('.editor-app'),canvas=editor.getByRole('application');
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});report.screenshots.push(name+'.png')};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:item.state_key,collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const points=()=>editor.locator('[data-point]').evaluateAll(nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.point,{x:Number(n.dataset.x),y:Number(n.dataset.y)}])));
 const settled=()=>canvas.evaluate(async el=>{let last='',same=0;for(let i=0;i<50;i++){await new Promise(r=>requestAnimationFrame(r));const m=el.getScreenCTM(),b=el.getBoundingClientRect(),key=JSON.stringify([m.a,m.e,m.f,b.width,b.height,el.getAttribute('viewBox')]);same=key===last?same+1:0;last=key;if(same>=3)return}throw Error('画布未稳定')});
 const screenPoint=async p=>canvas.evaluate((el,v)=>{const p=new DOMPoint(v.x,v.y).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y} },p);
 const pixel=async p=>{await settled();const s=await screenPoint(p);await page.mouse.click(s.x,s.y)};
 const zoomAt=async p=>{await settled();const s=await screenPoint(p);await page.mouse.move(s.x,s.y);for(let i=0;i<4;i++){await page.mouse.wheel(0,-1600);await settled()}};
 const drag=async p=>{await settled();const s=await screenPoint(p);await page.mouse.move(s.x,s.y);await page.mouse.down();await page.mouse.move(s.x+10,s.y-10,{steps:5});await page.mouse.up()};
 const idle=async()=>{assert.equal(await editor.locator('button.editor-tool[aria-pressed=true]').count(),0);assert(await canvas.evaluate(e=>e.classList.contains('tool-idle')))};
 const unchanged=(before,after)=>{for(const [id,p] of Object.entries(before))assert.deepEqual(after[id],p)};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const seed=async(item,kind,cid,edit)=>{
  const input=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
  const doc=input.documents.find(d=>d.curves[0].id===cid);
  doc.zero={pixel:doc.curves[0].points[0][doc.calibration.direction],pointIds:[doc.curves[0].points[0].id]};
  edit?.(doc);
  return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id);
 };
 try{
  let alpha=(await listing()).items.find(i=>i.result.curves[0].kind==='alpha2f');alpha=await seed(alpha,'alpha2f','a');
  assert.equal(alpha.result.curves[0].frequency_direction,'y');
  const historic=structuredClone(alpha.result.curves);
  await page.goto(address(alpha));await ready();await btn('编辑').click();await canvas.waitFor();await settled();await idle();
  const before=await points(),origin=before['a:p50'];
  await drag(origin);assert.deepEqual(await points(),before);assert(await btn('↶ 撤销').isDisabled());
  await btn('单点选点／拖动').click();await zoomAt(origin);await drag(origin);
  let after=await points();assert.notDeepEqual(after['a:p50'],origin);
  for(const id of Object.keys(before))if(id!=='a:p50')assert.deepEqual(after[id],before[id]);
  await btn('↶ 撤销').click();assert.deepEqual(await points(),before);
  await btn('↷ 重做').click();assert.deepEqual(await points(),after);await btn('↶ 撤销').click();
  check('默认无工具只选不拖；两个按钮直接进入单点/联动，单点其余坐标不变，撤销重做有效');

  await btn('联动选点／拖动').click();await drag(origin);
  after=await points();assert(Object.keys(before).filter(id=>JSON.stringify(before[id])!==JSON.stringify(after[id])).length>1);
  await page.mouse.move(10,10);
  await page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('.editor-tool')).find(b=>b.textContent==='联动选点／拖动');return getComputedStyle(b).backgroundColor==='rgb(79, 70, 229)'});
  const colors=await editor.locator('.tool-strip .editor-tool').evaluateAll(nodes=>nodes.map(n=>({label:n.textContent,pressed:n.getAttribute('aria-pressed'),background:getComputedStyle(n).backgroundColor,color:getComputedStyle(n).color})));
  assert.equal(colors.find(c=>c.pressed==='true').color,'rgb(255, 255, 255)');
  assert(colors.filter(c=>c.pressed==='false').every(c=>c.background==='rgba(79, 70, 229, 0.08)'));
  report.colors=colors;await shot('linked-dark-single-light');
  await btn('↶ 撤销').click();await btn('联动选点／拖动').click();await idle();
  check('联动沿原权重影响邻点；选中主题深紫/白字，未选中浅紫，反选退出');

  await page.keyboard.press('Escape');await btn('＋ 增加点').click();await settled();
  const s=await screenPoint(origin);
  await page.mouse.move(s.x+9,s.y);assert.equal(await editor.getByTestId('snap-target').count(),0);
  await page.mouse.move(s.x+7,s.y);await editor.getByTestId('snap-target').waitFor();
  assert.equal(await editor.getByTestId('snap-target').getAttribute('data-point-id'),'a:p50');
  assert((await editor.getByTestId('snap-target').textContent()).includes('点击设为起点'));
  await page.mouse.click(s.x+7,s.y);assert.deepEqual(await points(),before);assert(await btn('↶ 撤销').isDisabled());
  const next=before['a:p51'],addedPosition={x:origin.x+4,y:(origin.y+next.y)/2};
  await pixel(addedPosition);after=await points();const added=Object.keys(after).filter(id=>!before[id]);assert.equal(added.length,1);
  await btn('＋ 增加点').click();await idle();await pixel({x:addedPosition.x+2,y:addedPosition.y-.1});assert.deepEqual(await points(),after);
  await btn('＋ 增加点').click(); // 新会话沿用当前选中点，不能延续旧插入会话。
  await btn('＋ 增加点').click();await btn('↶ 撤销').click();assert.deepEqual(await points(),before);
  check('增加点可先激活，缩放后8px吸附，首次只确定起点；再次点按钮退出并保留已加点');

  // 用同一新入口完成原直连边插点，并验证正式保存回读。
  await page.keyboard.press('Escape');await btn('＋ 增加点').click();await pixel(origin);await pixel(addedPosition);await pixel(next);
  await page.waitForFunction(()=>document.querySelector('.tool-idle'));
  after=await points();const inserted=Object.keys(after).filter(id=>!before[id]);assert.equal(inserted.length,1);unchanged(before,after);
  await save();alpha=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(alpha.result.curves[0].points.find(p=>p.id==='a:p51').connectTo,inserted[0]);
  assert.equal(alpha.result.curves[0].points.length,historic[0].points.length+1);
  await page.reload();await ready();check('纵轴α²F：先选工具后的插点替换原直连，结束回到无工具，保存刷新保留连线');

  alpha=await seed(alpha,'alpha2f','a',doc=>{const p=doc.curves[0].points.find(p=>p.id==='a:p71');p.breakBefore=true;delete p.connectTo});
  await page.goto(address(alpha));await ready();await btn('编辑').click();await canvas.waitFor();
  let bridgeBefore=await points(),a=bridgeBefore['a:p70'],b=bridgeBefore['a:p71'];await zoomAt(a);
  await btn('＋ 增加点').click();await pixel(a);await pixel({x:a.x+3,y:(a.y+b.y)/2});await pixel(b);
  const bridgeId=Object.keys(await points()).find(id=>!bridgeBefore[id]);assert(bridgeId);
  await btn('＋ 增加点').click();await idle();await save();
  alpha=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(alpha.result.curves[0].points.find(p=>p.id===bridgeId).joinTo,'a:p71');
  check('原有未连接点加点补接保留，按钮退出后正常保存');

  let dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');dos=await seed(dos,'phonon_dos','Sc');
  const other=dos.result.curves.filter(c=>c.id!=='Sc');
  await page.goto(address(dos));await ready();await btn('编辑').click();await canvas.waitFor();await btn('Sc').click();await idle();
  const dosBefore=await points(),d=dosBefore['Sc:p50'];await zoomAt(d);
  await btn('单点选点／拖动').click();await drag(d);
  const dosAfter=await points();assert.notDeepEqual(dosBefore['Sc:p50'],dosAfter['Sc:p50']);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(500);
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+1);
  await btn('单点选点／拖动').scrollIntoViewIfNeeded();await shot('mobile-two-buttons');
  assert.equal(await btn('单点选点／拖动').getAttribute('aria-pressed'),'true');
  await save();dos=(await listing()).items.find(i=>i.id===dos.id);
  assert.deepEqual(dos.result.curves.filter(c=>c.id!=='Sc'),other);
  check('横轴DOS单点拖动保存不影响其他分波；390px双按钮可达且无整体溢出');
  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>w.path.endsWith('/manual')));
  report.status='passed';
 }catch(e){report.status='failed';report.failure=e.stack;await shot('failure');throw e}
 finally{fs.writeFileSync(path.join(out,'tool-interactions-browser.json'),JSON.stringify(report,null,2));await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
