// 真实 Chromium 加载共享生产组件；隔离所有 API，不读写论文数据。
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] })
try {
  for (const mode of ['light', 'dark']) {
    const page = await browser.newPage({ viewport: { width: 960, height: 1050 } })
    await page.route('**/api/**', route => route.fulfill({ contentType: 'application/json', body: '{}' }))
    await page.goto(process.env.FRONTEND_URL || 'http://127.0.0.1:5173')
    await page.evaluate(async mode => {
      const { default: React } = await import('/node_modules/.vite/deps/react.js')
      const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
      const { Box, TextField, MenuItem, ThemeProvider, createTheme } = await import('/node_modules/.vite/deps/@mui_material.js')
      const { default: EvidenceFieldMarkers } = await import('/src/components/EvidenceFieldMarkers.tsx')
      document.getElementById('root').hidden = true
      const host = document.createElement('div'); document.body.append(host)
      window.borderOpened = []; window.borderChanged = []
      const fields = [
        { id: 'pressure', label: '压强 (GPa)', value: '0.000101' },
        { id: 'summary', label: 'Summary', value: 'A multiline scientific statement.\nSecond line.', multiline: true },
        { id: 'system', label: '晶系 / Crystal system', value: 'cubic', select: true },
        { id: 'empty', label: '待填写', value: '' },
        { id: 'readonly', label: '只读 Tc', value: '3.78', disabled: true },
      ]
      const records = fields.map(f => ({ key: f.id, field: f.id, label: f.label, status: 'missing', reason: '缺少证据', evidences: [] }))
      function Fixture() {
        const [resolved, setResolved] = React.useState(false)
        window.resolveBorder = () => setResolved(true)
        return React.createElement(ThemeProvider, { theme: createTheme({ palette: { mode, background: { paper: mode === 'light' ? '#f0f5fa' : '#20242a' } } }) },
          React.createElement(Box, { 'data-evidence-scope': 'border-fixture', sx: { bgcolor: 'background.paper', color: 'text.primary', p: 3, width: 'min(580px, 100%)', boxSizing: 'border-box', display: 'grid', gap: 3 } },
            ...fields.map(f => React.createElement(TextField, { key: f.id, label: f.label, defaultValue: f.value,
              multiline: f.multiline, select: f.select, disabled: f.disabled, 'data-issue-field': f.id },
            f.select ? React.createElement(MenuItem, { value: 'cubic' }, 'Cubic') : undefined)),
            React.createElement('section', { 'data-issue-field': 'region' }, React.createElement('h3', {}, '结构区域')),
            React.createElement(EvidenceFieldMarkers, { scope: 'border-fixture',
              records: resolved ? [] : [...records, { key: 'region', field: 'region', label: '结构区域', status: 'missing', evidences: [] }],
              onOpen: key => window.borderOpened.push(key), onChange: field => window.borderChanged.push(field) })))
      }
      ReactDOM.createRoot(host).render(React.createElement(Fixture))
    }, mode)
    const fixture = page.locator('[data-evidence-scope="border-fixture"]')
    await fixture.getByRole('button', { name: '压强 (GPa)', exact: true }).waitFor()
    if (process.env.EVIDENCE_BORDER_SCREENSHOT) await fixture.screenshot({ path: `${process.env.EVIDENCE_BORDER_SCREENSHOT}-${mode}.png` })
    const check = async () => {
      const styles = await fixture.locator('.MuiOutlinedInput-root').evaluateAll(controls => controls.map(control => {
        const label = control.closest('.MuiFormControl-root').querySelector('label')
        const border = control.querySelector('fieldset'), legend = border.querySelector('legend')
        const labelRect = label.getBoundingClientRect(), legendRect = legend.getBoundingClientRect()
        return { text: label.textContent, outline: getComputedStyle(control).outlineStyle,
          border: getComputedStyle(border).borderTopColor, width: getComputedStyle(border).borderTopWidth,
          labelBackground: getComputedStyle(label).backgroundColor, front: Number(getComputedStyle(label).zIndex) > 0,
          shrink: label.dataset.shrink === 'true', gap: legendRect.left <= labelRect.left + 1 && legendRect.right >= labelRect.right - 1 }
      }))
      for (const s of styles) {
        assert.equal(s.outline, 'none', `${mode} ${s.text} 不叠加穿字的完整外框`)
        assert.equal(s.border, 'rgb(211, 47, 47)'); assert.equal(s.width, '2px')
        assert(s.front, `${s.text} 文字位于边框前景`)
        assert.equal(s.labelBackground, 'rgba(0, 0, 0, 0)', '无需白底遮挡')
        if (s.shrink) assert(s.gap, `${s.text} 边框缺口应覆盖浮动标签宽度`)
      }
    }
    await check()
    const input = fixture.getByLabel('压强 (GPa)', { exact: true })
    await input.fill('0.0025')
    assert.equal(await input.inputValue(), '0.0025')
    assert.deepEqual(await page.evaluate(() => window.borderOpened), [])
    await fixture.getByRole('button', { name: '压强 (GPa)', exact: true }).click()
    assert.deepEqual(await page.evaluate(() => window.borderOpened), ['pressure'])
    await fixture.getByRole('button', { name: 'Summary', exact: true }).focus()
    await page.keyboard.press('Enter')
    assert.deepEqual(await page.evaluate(() => window.borderOpened), ['pressure', 'summary'])
    await fixture.getByLabel('待填写', { exact: true }).focus()
    await page.waitForTimeout(250) // 等待 MUI 浮动标签和缺口的过渡结束。
    await check()
    await page.setViewportSize({ width: 360, height: 1050 }); await check()
    const region = fixture.locator('[data-issue-field="region"]')
    assert.equal(await region.evaluate(el => getComputedStyle(el).outlineColor), 'rgb(211, 47, 47)')
    const before = await fixture.boundingBox()
    await page.evaluate(() => window.resolveBorder())
    await page.waitForFunction(() => !document.querySelector('[data-evidence-problem]'))
    const after = await fixture.boundingBox()
    assert.equal(after.height, before.height, '解除标记不移动表单布局')
    assert.notEqual(await fixture.locator('fieldset').first().evaluate(el => getComputedStyle(el).borderTopColor), 'rgb(211, 47, 47)')
    console.log(JSON.stringify({ mode, borderAndLabels: 'passed' }))
    await page.close()
  }
} finally { await browser.close() }
