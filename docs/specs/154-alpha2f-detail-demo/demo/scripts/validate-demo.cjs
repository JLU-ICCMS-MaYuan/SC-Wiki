// 隔离 Demo 浏览器核验；不连接业务接口、不使用用户浏览器会话。
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../assets');
const base = process.env.SPECTRUM_DEMO_URL || 'http://127.0.0.1:5194/';
async function main() {
  const { rows, integrate, integral, reference, area, dosModel } = await import(pathToFileURL(path.join(root, 'src/data.js')));
  const known = Array.from({ length: 1001 }, (_, i) => ({ f: 1 + i / 1000, a: 1 + i / 1000 }));
  const result = integrate(known, 'a');
  assert(Math.abs(result.lambda - 2) < 1e-10);
  assert(Math.abs(result.wlog / 47.99243073366221 - 4 / Math.E) < 1e-6);
  assert.equal(rows[0].f, 0); assert.equal(rows[0].a, 0);
  assert(rows.every(row => row.diff >= 0));
  assert(Math.abs(area(rows, ['d0','d1','d2']) - dosModel.target) < 1e-10);
  assert(Math.abs(area(rows, ['e0','e1','e2']) - dosModel.target) > dosModel.tolerance);
  assert.equal(area([{f:0,a:0},{f:1,a:null}], ['a']), null);
  assert.equal(integrate(rows, 'a').lambda, null);
  const zeroKnown = Array.from({length:2001}, (_, i) => ({f:i/1000,a:(i/1000)**2}));
  const zeroIntegral = integrate(zeroKnown, 'a', {zeroLimitKnown:true});
  assert(Math.abs(zeroIntegral.lambda - 4) < 1e-10);
  assert(Math.abs(zeroIntegral.wlog / 47.99243073366221 - 2 / Math.sqrt(Math.E)) < 1e-6);
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [], apiRequests = [], checks = [];
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
  context.on('page', p => p.on('pageerror', error => errors.push(error.message)));
  context.on('request', request => { if (request.url().includes('/api/')) apiRequests.push(request.url()); });
  const page = await context.newPage();
  try {
    await page.goto(base); await page.getByPlaceholder('在这里输入临时备注，再打开详情').fill('保留此未保存备注');
    for (const [kind, button] of [['alpha','查看 α²F'],['dos','查看声子 DOS']]) {
      const opened = context.waitForEvent('page'); await page.getByRole('link', { name: button, exact: true }).click();
      const detail = await opened; await detail.waitForLoadState();
      assert(detail.url().includes(`page=${kind}`)); assert.equal(await detail.evaluate(() => window.opener), null);
      assert.equal(await page.getByPlaceholder('在这里输入临时备注，再打开详情').inputValue(), '保留此未保存备注');
      assert.equal(await detail.locator('h2').count(), 4);
      for (const mode of ['仅原图','仅提取数据','原图与数据叠加']) {
        await detail.getByRole('button',{name:mode,exact:true}).click();
        assert.equal(await detail.locator('canvas').count(),1);
        assert((await detail.locator('canvas').getAttribute('aria-label')).includes('纵轴为频率'));
      } checks.push(`${kind}: 新标签页、原输入保留、opener 隔离、四区标题`);
      await detail.getByRole('button', { name:'原图与数据叠加', exact:true }).click();
      assert.equal(await detail.getByRole('button', { name:'原图与数据叠加', exact:true }).getAttribute('aria-pressed'), 'true');
      await detail.getByRole('heading', { name:/原图与提取数据叠加/ }).waitFor();
      await detail.screenshot({ path:path.join(output, `${kind}-overlay.png`), fullPage:true });
      await detail.getByRole('button', { name:'仅提取数据', exact:true }).click();
      const table = detail.getByRole('region', { name:'可滚动的逐点数据表' });
      const scroll = await table.evaluate(el => { el.scrollTop = 500; return { top:el.scrollTop, height:el.clientHeight, full:el.scrollHeight }; });
      assert(scroll.top > 0 && scroll.height <= 330 && scroll.full > scroll.height);
      assert.equal(await detail.locator('.points thead th').first().evaluate(el => getComputedStyle(el).position), 'sticky');
      await detail.getByRole('textbox', { name:'查找频率' }).fill('20.50');
      assert.equal(await detail.locator('.points tbody tr').count(), 1);
      await detail.locator('.row-button').click(); assert((await detail.locator('.table-footer').textContent()).includes('20.50'));
      await detail.getByRole('textbox', { name:'查找频率' }).fill('999'); await detail.getByText('没有匹配的频率').waitFor();
      await detail.getByRole('textbox', { name:'查找频率' }).fill('');
      await table.evaluate(el => { el.scrollTop = 0; });
      checks.push(`${kind}: 单图三模式、来源轴向保持、定高滚动、固定表头、搜索、选点、无匹配`);
      if (kind === 'alpha') {
        for (const [state, text] of [['uncalibrated','幅值刻度待核对，暂不积分'],['stale','材料条件已变化，参考失效'],['missing','论文未报告参考值'],['zero','参考值为零：仍可计算绝对偏差。']]) {
          await detail.getByLabel('演示状态').selectOption(state); await detail.getByText(text, { exact:true }).waitFor();
          const cells = await detail.locator('.compare tbody tr').first().locator('td').allTextContents();
          if (state === 'uncalibrated') assert(cells.every(x => x === '—'));
          if (state === 'zero') assert(Number(cells.at(-1)) > 0);
        }
        await detail.getByLabel('演示状态').selectOption('valid');
        assert.deepEqual(await detail.locator('.compare thead th').allTextContents(), ['参数','提取谱积分值','参考值','绝对偏差']);
        assert.equal(await detail.getByText('λ（无量纲）', {exact:true}).count(),0);
        const pointDeltas = await detail.locator('.points tbody tr td:nth-child(5)').allTextContents();
        assert(pointDeltas.every(value => Number(value) >= 0));
        checks.push('α²F: 未标定/参考失效/缺参考/零参考分支');
      } else {
        const canvas = detail.locator('canvas').last(); const before = await canvas.evaluate(el => el.toDataURL());
        await detail.getByLabel('分波态密度', {exact:true}).selectOption('La');
        assert.notEqual(await canvas.evaluate(el => el.toDataURL()), before);
        const modesBefore = await detail.locator('.dos-integral').textContent();
        for (const projection of ['Sc','H','all']) {
          await detail.getByLabel('分波态密度', {exact:true}).selectOption(projection);
          assert.equal(await detail.locator('.dos-integral').textContent(),modesBefore);
        }
        assert((await detail.locator('.dos-integral').textContent()).includes('不满足 3N'));
        await detail.getByLabel('演示状态').selectOption('gap');
        assert((await detail.locator('.dos-integral').textContent()).includes('无法核验'));
        await detail.getByLabel('演示状态').selectOption('unknown');
        assert((await detail.locator('.dos-integral').textContent()).includes('无法核验'));
        await detail.getByLabel('演示状态').selectOption('error'); await detail.getByText('谱数据暂时无法读取', { exact:true }).waitFor();
        await detail.getByRole('button', { name:'重新读取', exact:true }).click();
        await detail.getByRole('heading', { name:'02 · 原图与提取结果', exact:true }).waitFor();
        await detail.getByLabel('演示状态').selectOption('empty'); await detail.getByText('该材料状态尚无 DOS 数据', { exact:true }).waitFor();
        await detail.getByLabel('演示状态').selectOption('ready');
        checks.push('DOS: 单分波/全部、3N不符、缺口/缺依据不可核验、重试与空态');
      }
      const downloaded = detail.waitForEvent('download'); await detail.getByRole('button', { name:'导出示例 CSV', exact:true }).click();
      const download = await downloaded; const csv = fs.readFileSync(await download.path(), 'utf8');
      assert(csv.includes('DEMO_ONLY_SYNTHETIC_DATA')); assert.equal(csv.trim().split('\n').length, rows.length + 2);
      await detail.getByRole('button', { name:'查看提供的截图', exact:true }).click();
      await detail.locator('.evidence').evaluate(el => el.decode());
      assert(await detail.locator('.evidence').evaluate(el => el.complete && el.naturalWidth === 1400));
      await detail.getByRole('button', { name:'收起提供的截图', exact:true }).click();
      await detail.evaluate(() => window.scrollTo(0, 0));
      await detail.screenshot({ path:path.join(output, `${kind}-desktop.png`), fullPage:true });
      await detail.setViewportSize({ width:390, height:844 });
      assert.equal(await detail.evaluate(() => document.documentElement.scrollWidth), 390);
      const horizontal = await table.evaluate(el => { el.scrollLeft=200; return el.scrollLeft; }); assert(horizontal > 0);
      await detail.screenshot({ path:path.join(output, `${kind}-mobile.png`), fullPage:true });
      checks.push(`${kind}: CSV 281 点、原截图可加载、390px 无页面水平溢出且表内横向可滚动`);
      await detail.close();
    }
    assert.deepEqual(errors, []); assert.deepEqual(apiRequests, []);
    fs.writeFileSync(path.join(output,'validation.json'), JSON.stringify({ date:'2026-10-23', browser:'Playwright + 本机 Chrome 隔离上下文', base, checks, errors, apiRequests, integral, reference, analyticCheck:result, limits:['仅合成谱原型，不证明正式 500 修复','未部署，未接入业务数据','视觉确认由用户评审'] }, null, 2));
    console.log(JSON.stringify({ checks, errors, apiRequests, integral, reference }, null, 2));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
