// 正式UI/HTTP/存储：插入已连边与补接未连边兼容；全部API重定向测试服务。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.HOME,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(require.resolve('playwright',{paths:[runtime]}));
const backend='http://127.0.0.1:8191',frontend='http://127.0.0.1:5173';
const out=process.env.SCWIKI_SPECTRUM_BROWSER_OUT||path.resolve('docs/specs/161-spectrum-manual-editor-demo/assets');
const report={checks:[],errors:[],writes:[],screenshots:[]};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(()=>{localStorage.setItem('auth_token','isolated-test');localStorage.setItem('auth_user',JSON.stringify({id:161,username:'isolated_validation',role:'user',is_approved:true,account_status:'active',is_email_verified:true}))});
 await context.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());if(req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});const response=await route.fetch({url:backend+url.pathname+url.search});await route.fulfill({response})});
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const btn=name=>page.getByRole('button',{name,exact:true}),editor=page.locator('.editor-app'),canvas=editor.getByRole('application');
 const check=name=>{report.checks.push(name);console.log('PASS',name)};
 const shot=async name=>{const file='insertion-'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!await editor.count()});report.screenshots.push(file)};
 const target={target:'upload',target_id:'manual-test'},query=new URLSearchParams(target).toString();
 const api=async(p,body)=>{const r=await fetch(backend+p,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data};
 const listing=()=>api('/api/rag/spectra?'+query);
 const address=item=>frontend+'/spectra/'+item.id+'?'+new URLSearchParams({...target,state_key:'s1',collection_version:String(item.version),run:item.run.id,curve:item.result.curves[0].id,return:'/upload'});
 const ready=()=>page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='编辑');return b&&!b.disabled});
 const points=()=>editor.locator('[data-point]').evaluateAll(nodes=>Object.fromEntries(nodes.map(n=>[n.dataset.point,{x:Number(n.dataset.x),y:Number(n.dataset.y)}])));
 let editingVertical=process.env.SCWIKI_INSERT_VERTICAL_FIXTURES==='1';
 const pixel=async(x,y,double=false)=>{if(editingVertical){const oldX=x;x=y;y=159-oldX}const p=await canvas.evaluate((el,c)=>{const p=new DOMPoint(c.x,c.y).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y}},{x,y});if(double)await page.mouse.dblclick(p.x,p.y);else await page.mouse.click(p.x,p.y)};
 const settled=()=>canvas.evaluate(async el=>{let last='',same=0;for(let i=0;i<40;i++){await new Promise(r=>requestAnimationFrame(r));const m=el.getScreenCTM(),b=el.getBoundingClientRect(),key=JSON.stringify([m.a,m.e,m.f,b.width,b.height,el.getAttribute('viewBox')]);same=key===last?same+1:0;last=key;if(same>=3)return}throw Error('画布未稳定')});
 const zoomAt=async(x,y)=>{await settled();const p=await canvas.evaluate((el,c)=>{const p=new DOMPoint(c.x,c.y).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y}},{x,y});await page.mouse.move(p.x,p.y);for(let i=0;i<4;i++){await page.mouse.wheel(0,-2000);await settled()}};
 const begin=async(cid,a,b)=>{editingVertical=cid==='a'&&process.env.SCWIKI_INSERT_VERTICAL_FIXTURES==='1';await btn('编辑').click();await canvas.waitFor();if(cid!=='a')await btn(cid).click();const before=await points();await page.locator('[data-row="'+a+'"]').click();await btn('＋ 增加点').click();await zoomAt((before[a].x+before[b].x)/2,(before[a].y+before[b].y)/2);return before};
 const save=async()=>{await btn('保存调整').click();await page.waitForFunction(()=>!document.querySelector('.editor-app'));await ready()};
 const recalc=async()=>{const old=page.url();await btn('重新计算').click();await page.waitForURL(u=>u.href!==old);await ready()};
 const seed=async(item,kind,cid,edit)=>{
  const input=await api('/api/rag/spectra/'+item.id+'/manual?'+query+'&kind='+kind+'&collection_version='+item.version+'&run_id='+item.run.id);
  const doc=input.documents.find(d=>d.curves[0].id===cid);doc.zero={pixel:doc.curves[0].points[0][doc.calibration.direction],pointIds:[doc.curves[0].points[0].id]};edit?.(doc);
  return (await api('/api/rag/spectra/'+item.id+'/manual',{...target,expected_version:input.version,expected_collection_version:item.version,base_run_id:item.run.id,document:doc})).items.find(i=>i.id===item.id);
 };
 const oldPointsUnmoved=(before,after)=>{for(const [id,p] of Object.entries(before))assert.deepEqual(after[id],p)};
 try{
  let alpha=(await listing()).items.find(i=>i.result.curves[0].kind==='alpha2f');alpha=await seed(alpha,'alpha2f','a');
  await page.goto(address(alpha));await ready();
  let before=await begin('a','a:p50','a:p51'),writes=report.writes.length;
  await pixel(70.35,74.9);await pixel(70.7,74.9);await pixel(71,75);
  await page.waitForFunction(()=>!document.querySelector('.tool-add'));
  let after=await points(),added=Object.keys(after).filter(k=>!before[k]);assert.equal(added.length,2);oldPointsUnmoved(before,after);
  assert.equal(report.writes.length,writes);await page.getByRole('status').filter({hasText:'已在原线段中插入 2 个点'}).waitFor();
  await btn('↶ 撤销').click();assert.equal(Object.keys(await points()).length,Object.keys(before).length+2);
  await btn('↷ 重做').click();await shot('connected-forward');
  await save();await recalc();
  alpha=(await listing()).items.find(i=>i.id===alpha.id);
  let curve=alpha.result.curves[0],ids=curve.points.map(p=>p.id),at=ids.indexOf('a:p50');
  assert.deepEqual(ids.slice(at,at+4),['a:p50',...added,'a:p51']);
  assert.equal(curve.points.find(p=>p.id==='a:p51').connectTo,added[1]);
  assert.equal(alpha.result.quality.integrals.raw.parameters.lambda.status,'available');
  assert(!alpha.result.quality.trace_diagnostics.alpha2f.curves.some(c=>c.issues.some(i=>['cycle','branch'].includes(i.kind))));
  check('已连接A/B之间多点插入，单击B结束，原直连被替换、原点不动，可撤销重做并成功积分');

  await page.reload();await ready();before=await begin('a','a:p61','a:p60');
  await pixel(80.7,73.9);await pixel(80.35,73.9);await pixel(80,74);
  await page.waitForFunction(()=>!document.querySelector('.tool-add'));after=await points();added=Object.keys(after).filter(k=>!before[k]);assert.equal(added.length,2);oldPointsUnmoved(before,after);
  await save();await recalc();alpha=(await listing()).items.find(i=>i.id===alpha.id);
  assert.equal(alpha.result.quality.integrals.raw.parameters.lambda.status,'available');await shot('reverse-saved');
  check('从高频端反向插入同样形成单值路径，刷新回读后继续编辑和积分正确');

  alpha=await seed(alpha,'alpha2f','a',doc=>{const p=doc.curves[0].points.find(p=>p.id==='a:p71');p.breakBefore=true;delete p.connectTo});
  await page.goto(address(alpha));await ready();before=await begin('a','a:p70','a:p71');
  await pixel(90.5,72.9);await pixel(91,73);
  assert.equal(await editor.locator('.tool-add').count(),1);
  after=await points();added=Object.keys(after).filter(k=>!before[k]);assert.equal(added.length,1);
  await pixel(91,73,true);await page.waitForFunction(()=>!document.querySelector('.tool-add'));oldPointsUnmoved(before,await points());
  await shot('unconnected-bridge');await save();await recalc();
  alpha=(await listing()).items.find(i=>i.id===alpha.id);curve=alpha.result.curves[0];
  assert.equal(curve.points.find(p=>p.id===added[0]).joinTo,'a:p71');
  assert.equal(curve.points.find(p=>p.id==='a:p71').breakBefore,true);
  assert.equal(alpha.result.quality.integrals.raw.parameters.lambda.status,'available');
  check('原本不连接的A/B仍可加点补接，旧断边标记不被误替换，保持原吸附/双击结束并成功积分');

  await btn('编辑').click();await canvas.waitFor();before=await points();await page.locator('[data-row="a:p100"]').click();await btn('＋ 增加点').click();await settled();
  await pixel(122,50);await pixel(124,48,true);assert.equal(Object.keys(await points()).length,Object.keys(before).length+2);
  assert.equal(await editor.locator('.tool-add').count(),0);await btn('← 返回详情').click();await btn('放弃修改').click();await ready();
  check('自由连续描线和空白处双击结束继续可用，没有被限制为只能插点');

  let dos=(await listing()).items.find(i=>i.result.curves[0].kind==='phonon_dos');const originalDos=structuredClone(dos.result.curves);
  dos=await seed(dos,'phonon_dos','Sc');await page.goto(address(dos));await ready();before=await begin('Sc','Sc:p80','Sc:p81');
  await pixel(100.35,71.9);await pixel(100.7,71.9);await pixel(101,72);await page.waitForFunction(()=>!document.querySelector('.tool-add'));
  oldPointsUnmoved(before,await points());await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await shot('dos-mobile-insert');
  await save();await recalc();const fresh=(await listing()).items.find(i=>i.id===dos.id);
  assert.equal(fresh.result.curves.find(c=>c.id==='Sc').points.length,originalDos.find(c=>c.id==='Sc').points.length+2);
  assert.deepEqual(fresh.result.curves.find(c=>c.id==='La'),originalDos.find(c=>c.id==='La'));
  assert.deepEqual(fresh.result.curves.find(c=>c.id==='H'),originalDos.find(c=>c.id==='H'));
  assert.equal(fresh.result.quality.dos_mode_integral.status,'available');
  check('PhDOS相同工具插点且不影响La/H，390px保存回读及积分通过');

  assert.deepEqual(report.errors,[]);assert(report.writes.every(w=>/\/(manual|recalculate)$/.test(w.path)));report.status='passed';
 }catch(error){report.status='failed';report.failure=error.stack;await shot('failure');throw error}
 finally{fs.writeFileSync(path.join(out,'insertion-browser-validation.json'),JSON.stringify(report,null,2)+'\n');await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
