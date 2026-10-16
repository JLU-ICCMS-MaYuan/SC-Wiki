// 隔离验收夹具：正式材料状态及谱组件；模拟数据和响应，不访问业务服务。
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Box, Button, CssBaseline, ThemeProvider, Typography } from '@mui/material'
import theme from '../../../../frontend/src/theme'
import { LanguageProvider } from '../../../../frontend/src/context/LanguageContext'
import MaterialStatesEditor from '../../../../frontend/src/components/MaterialStatesEditor'
import { emptyPropertyModule, emptyPropertyRecord, type PropertyModuleCode } from '../../../../frontend/src/lib/propertyModules'
import type { DraftMaterialState } from '../../../../frontend/src/lib/paperProcessing'

const codes: PropertyModuleCode[] = ['superconductive_properties', 'electronic_properties', 'dynamical_properties', 'thermodynamical_properties']
const definitions = codes.map(module_code => ({ definition_key: `record.${module_code}.custom`, version: 1,
  target_kind: 'property_record', module_code, record_type: 'property', property_code: 'custom',
  core_schema: {}, json_schema: { type: 'object', additionalProperties: true }, ui_schema: {}, status: 'published', checksum: 'fixture' }))
const initial = (): DraftMaterialState[] => [1, 2].map(index => ({ state_key: `fixture-${index}`, material: 'Sn', material_name: `模拟材料 ${index}`,
  pressure_value_gpa: index * 100, state_kind: 'theoretical', structure_optimization: 'unknown', structure_families: [], tc_results: [], properties: [],
  property_modules: [{ ...emptyPropertyModule('electronic_properties'), module_key: `electronic-${index}`,
    records: [{ ...emptyPropertyRecord('electronic_properties'), record_key: `record-${index}`, name_raw: `模拟记录 ${index}`, value_kind: 'text', value_raw: '模拟值', value_text: '模拟值' }] }],
}))
const requests: string[] = []
window.fetch = async (input, init) => {
  const path = String(input), method = init?.method || 'GET'
  requests.push(`${method} ${path}`)
  document.documentElement.dataset.fixtureRequests = JSON.stringify(requests)
  if (method !== 'GET') throw Error('本夹具禁止业务写入')
  const url = new URL(path, location.origin)
  const data = url.pathname === '/api/form-definitions'
    ? definitions.filter(item => item.module_code === url.searchParams.get('module_code'))
    : url.pathname.startsWith('/api/form-definitions/') ? definitions.find(item => path.includes(item.definition_key))
      : { version: 'fixture', jobs: [], can_edit: false, can_review: false, items: [{ id: 'fixture-spectrum', version: 1, state_key: 'fixture-1', stale: false,
        source: { source_name: '模拟来源.pdf', pdf_page: 1 }, run: { id: 'fixture-run', status: 'needs_review' }, review: {},
        result: { curves: [], calibration: { curves: [{ kind: 'phonon_dos' }] } } }] }
  return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function Harness() {
  const [states, setStates] = useState(initial)
  const [readOnly, setReadOnly] = useState(false)
  const [empty, setEmpty] = useState(false)
  return <ThemeProvider theme={theme}><CssBaseline /><BrowserRouter><LanguageProvider>
    <Box sx={{ maxWidth: 1180, p: 2, m: 'auto' }}>
      <Typography variant="h6">各材料状态底部添加模块 · 正式组件（模拟数据）</Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', my: 1 }}>
        <Button onClick={() => setReadOnly(value => !value)}>切换只读</Button>
        <Button onClick={() => { setStates(empty ? initial() : states.map(state => ({ ...state, property_modules: [] }))); setEmpty(value => !value) }}>切换无模块</Button>
        <Button onClick={() => { setStates(initial()); setReadOnly(false); setEmpty(false) }}>恢复示例</Button>
      </Box>
      <MaterialStatesEditor key={String(empty)} states={states}
        readOnly={readOnly} onChange={setStates} catalogs={{ material_families: [], structure_families: [], material_dimensionalities: [] }}
        propertySpectra={{ target: { target: 'upload', target_id: 'fixture-only' } }} />
    </Box>
  </LanguageProvider></BrowserRouter></ThemeProvider>
}
createRoot(document.getElementById('root')!).render(<Harness />)
