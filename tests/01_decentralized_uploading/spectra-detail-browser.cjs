// 使用正式 App 路由和组件；网络只读取此前生成的本机业务只读快照，不写业务接口。
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const data = JSON.parse(fs.readFileSync(process.env.SPECTRA_SNAPSHOT || '/tmp/scwiki-spectra-production/snapshot.json', 'utf8'));
const base = process.env.SPECTRA_FRONTEND || 'http://127.0.0.1:5173';
const out = path.join(root, 'docs/specs/154-alpha2f-detail-demo/assets');
async function main() {
  const browser = await chromium.launch({ headless: true, channel:'chrome' });
  const context = await browser.newContext({ viewport:{width:1440,height:1000} });
  const errors = [], writes = [], checks = [];
  const user = { id:1, username:'spectrum_validation', role:'user', is_approved:true, email_verified:true };
  await context.addInitScript(user => { localStorage.setItem('auth_token','isolated-fixture-token'); localStorage.setItem('auth_user',JSON.stringify(user)); }, user);
  await context.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), p = url.pathname;
    if (request.method() !== 'GET') { writes.push(p); return route.fulfill({status:403,json:{detail:'只读验证禁止写入'}}); }
    if (p === '/api/auth/me') return route.fulfill({json:{user}});
    if (p === '/api/rag/spectra') return route.fulfill({json:data.listing});
    if (p.endsWith('/draft')) return route.fulfill({json:{data:{material_states:data.states}}});
    const match = p.match(/^\/api\/rag\/spectra\/([^/]+)\/(.*)$/);
    if (match) {
      const [, id, operation] = match;
      if (operation === 'image') return route.fulfill({contentType:'image/png',body:fs.readFileSync(data.images[id])});
      if (operation === 'history') return route.fulfill({json:{items:data.histories[id]}});
      if (operation.startsWith('runs/')) return route.fulfill({json:data.history_data[operation.slice(5)]});
      if (operation === 'export') return route.fulfill({contentType:'application/json',body:JSON.stringify(data.listing.items.find(item => item.id === id))});
    }
    return route.fulfill({json:{items:[],count:0,unread_count:0}});
  });
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  try {
    for (const [kind,id] of [['alpha','c340f3c41b144662808c0933d1e75248'],['dos','17d6b76963e2486aa5c4afbcbcf20d60']]) {
      const item=data.listing.items.find(item=>item.id===id);
      const curve=item.result.curves.find(c=>c.kind===(kind==='dos'?'phonon_dos':'alpha2f'));
      const query=new URLSearchParams({target:'upload',target_id:'c16cc627a0c04dc8ad4289624d1da80a',state_key:item.state_key,curve:curve.id,run:item.run.id,collection_version:String(item.version),return:'/upload'});
      await page.goto(base+'/spectra/'+id+'?'+query);
      await page.getByRole('heading',{name:'02 · 原图与提取结果'}).waitFor();
      for (const mode of ['仅原图','仅提取数据','原图与数据叠加']) {
        await page.getByRole('button',{name:mode,exact:true}).click();
        await page.waitForTimeout(100);
        assert.equal(await page.locator('main svg[role="img"]').count(),1);
      }
      await page.getByRole('button',{name:'仅提取数据',exact:true}).click();
      assert((await page.locator('svg[role="img"]').getAttribute('aria-label')).includes('频率沿竖轴'));
      if(kind==='dos') {
        await page.getByRole('combobox',{name:/分波态密度/}).click();
        await page.getByRole('option',{name:'仅 H',exact:true}).click();
        assert.equal(await page.locator('svg[role="img"] path[stroke="#38a477"]').count(),1);
        await page.getByRole('combobox',{name:/分波态密度/}).click(); await page.getByRole('option',{name:'全部分波',exact:true}).click();
      }
      await page.getByRole('button',{name:'查看提取历史',exact:true}).click();
      const history = page.getByRole('button').filter({hasText:/2026-10-15.*290 GPa/});
      await history.first().waitFor();
      assert(await history.count()>1); await history.last().click();
      await page.getByText('历史提取',{exact:true}).waitFor();
      await page.getByRole('button',{name:'返回打开时的版本',exact:true}).click();
      const table=page.getByRole('region',{name:'可滚动的逐点数据表'});
      assert(await table.evaluate(el=>{el.scrollTop=500;return el.scrollTop>0&&el.clientHeight<=330}));
      await table.evaluate(el=>el.scrollTop=0);
      await page.screenshot({path:path.join(out,`production-${kind}-desktop.png`),fullPage:true});
      await page.setViewportSize({width:390,height:844});
      await page.waitForTimeout(300);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
      await page.evaluate(()=>window.scrollTo(0,0));
      await page.screenshot({path:path.join(out,`production-${kind}-mobile.png`)});
      await page.locator('svg[role="img"]').screenshot({path:path.join(out,`production-${kind}-mobile-plot.png`)});
      await page.setViewportSize({width:1440,height:1000});
      checks.push(kind+': 正式路由、真实谱快照、三模式、来源轴向、历史、定高点表、390px');
    }
    assert.deepEqual(errors,[]); assert.deepEqual(writes,[]);
    fs.writeFileSync(path.join(out,'production-browser.json'),JSON.stringify({checks,errors,writes,network:'本机数据库只读快照，浏览器网络隔离；非真实生产 HTTP 验收'},null,2));
    console.log(JSON.stringify({checks,errors,writes}));
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
