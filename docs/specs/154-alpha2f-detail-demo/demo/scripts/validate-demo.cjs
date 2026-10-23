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
  const { rows, integrate, integral, reference } = await import(pathToFileURL(path.join(root, 'src/data.js')));
  const known = Array.from({ length: 1001 }, (_, i) => ({ f: 1 + i / 1000, a: 1 + i / 1000 }));
  const result = integrate(known, 'a');
  assert(Math.abs(result.lambda - 2) < 1e-10);
  assert(Math.abs(result.wlog / 47.99243073366221 - 4 / Math.E) < 1e-6);
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
      assert.equal(await detail.locator('h2').count(), 4); checks.push(`${kind}: 新标签页、原输入保留、opener 隔离、四区标题`);
      await detail.getByRole('button', { name:'叠加到原图', exact:true }).click();
      assert.equal(await detail.getByRole('button', { name:'叠加到原图', exact:true }).getAttribute('aria-pressed'), 'true');
      await detail.getByRole('heading', { name:'原图覆盖对照', exact:true }).waitFor();
      await detail.screenshot({ path:path.join(output, `${kind}-overlay.png`), fullPage:true });
      await detail.getByRole('button', { name:'单独显示数据', exact:true }).click();
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
      checks.push(`${kind}: 叠加/独立切换、定高滚动、固定表头、搜索、选点、无匹配`);
      if (kind === 'alpha') {
        for (const [state, text] of [['uncalibrated','幅值刻度待核对，暂不积分'],['stale','材料条件已变化，参考失效'],['missing','论文未报告参考值'],['zero','参考值为零：保留差值，相对偏差无定义。']]) {
          await detail.getByLabel('演示状态').selectOption(state); await detail.getByText(text, { exact:true }).waitFor();
          const cells = await detail.locator('.compare tbody tr').first().locator('td').allTextContents();
          if (state === 'uncalibrated') assert(cells.every(x => x === '—'));
          if (state === 'zero') assert.equal(cells.at(-1), '—');
        }
        await detail.getByLabel('演示状态').selectOption('valid');
        checks.push('α²F: 未标定/参考失效/缺参考/零参考分支');
      } else {
        const canvas = detail.locator('canvas').last(); const before = await canvas.evaluate(el => el.toDataURL());
        await detail.getByRole('checkbox', { name:'H 分波' }).uncheck();
        assert.notEqual(await canvas.evaluate(el => el.toDataURL()), before);
        await detail.getByRole('checkbox', { name:'H 分波' }).check();
        await detail.getByLabel('演示状态').selectOption('error'); await detail.getByText('谱数据暂时无法读取', { exact:true }).waitFor();
        await detail.getByRole('button', { name:'重新读取', exact:true }).click();
        await detail.getByRole('heading', { name:'02 · 原图与提取结果', exact:true }).waitFor();
        await detail.getByLabel('演示状态').selectOption('empty'); await detail.getByText('该材料状态尚无 DOS 数据', { exact:true }).waitFor();
        await detail.getByLabel('演示状态').selectOption('ready');
        checks.push('DOS: 分波显隐改变画布、HTTP 500 演示重试、空态');
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
      checks.push(`${kind}: CSV 279 点、原截图可加载、390px 无页面水平溢出且表内横向可滚动`);
      await detail.close();
    }
    assert.deepEqual(errors, []); assert.deepEqual(apiRequests, []);
    fs.writeFileSync(path.join(output,'validation.json'), JSON.stringify({ date:'2026-10-23', browser:'Playwright + 本机 Chrome 隔离上下文', base, checks, errors, apiRequests, integral, reference, analyticCheck:result, limits:['仅合成谱原型，不证明正式 500 修复','未部署，未接入业务数据','视觉确认由用户评审'] }, null, 2));
    console.log(JSON.stringify({ checks, errors, apiRequests, integral, reference }, null, 2));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
