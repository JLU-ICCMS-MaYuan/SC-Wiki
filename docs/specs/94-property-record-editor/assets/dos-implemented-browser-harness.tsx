import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Box, Button, Checkbox, CssBaseline, FormControlLabel, ThemeProvider, Typography } from '@mui/material'
import theme from './src/theme'
import PropertyModuleEditor from './src/components/PropertyModuleEditor'
import EvidenceFieldMarkers from './src/components/EvidenceFieldMarkers'
import { useEvidenceWorkflow } from './src/components/EvidenceWorkflow'
import { currentEvidenceField } from './src/lib/evidenceFields'
import { api } from './src/lib/api'
import fixtures from './dos-fixtures.json'

const definition = { definition_key: 'record.electronic_properties.dos_fermi', version: 1, status: 'published',
  target_kind: 'property_record', module_code: 'electronic_properties', property_code: 'dos_fermi', record_type: 'property',
  json_schema: { type: 'object', additionalProperties: true }, core_schema: {}, ui_schema: {} }
let selected = 'conflict'
api.get = (async (path: string) => path.startsWith('/api/form-definitions?') ? [definition]
  : path.startsWith('/api/form-definitions/') ? definition
    : { ok: true, data: { items: [] } }) as typeof api.get
api.post = (async (path: string) => path.endsWith('/preflight') ? fixtures[selected].preflight : { ok: true }) as typeof api.post

function Editor({ mode, readOnly }: { mode: string; readOnly: boolean }) {
  const [modules, setModules] = useState(() => structuredClone(fixtures[mode].modules))
  const state = { state_key: 'dos-state', material: 'LaSc2H24', pressure_value_gpa: 167, property_modules: modules }
  const flow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'isolated-dos' },
    getCurrentValue: record => currentEvidenceField(record, {}, [state]) })
  return <Box data-evidence-scope="dos-implemented">
    <Typography sx={{ my: 2 }}>LaSc₂H₂₄ · 167 GPa</Typography>
    <Box data-state-key="dos-state" data-state-label="LaSc₂H₂₄ · 167 GPa">
      <PropertyModuleEditor modules={modules} readOnly={readOnly} basePath="material_states[0].property_modules" onChange={setModules} />
    </Box>
    <EvidenceFieldMarkers records={flow.records} scope="dos-implemented" onOpen={flow.openIssue} onChange={flow.invalidate} />
    {flow.dialog}
  </Box>
}

function App() {
  const [mode, setMode] = useState('conflict')
  const [readOnly, setReadOnly] = useState(false)
  return <ThemeProvider theme={theme}><CssBaseline /><Box sx={{ p: 2 }}>
    <Typography variant="h6">DOS 唯一值与冲突侧栏 · 正式共享组件验证</Typography>
    <Typography variant="body2" color="text.secondary">隔离夹具；19.10 是冲突演示值，不是论文事实。只读备份表注，不连接真实草稿或保存接口。</Typography>
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', my: 2 }}>
      <Button onClick={() => { selected = 'same'; setMode('same') }}>相同副本</Button>
      <Button onClick={() => { selected = 'conflict'; setMode('conflict') }}>不同数值</Button>
      <FormControlLabel label="只读" control={<Checkbox checked={readOnly} onChange={event => setReadOnly(event.target.checked)} />} />
    </Box>
    <Editor key={mode} mode={mode} readOnly={readOnly} />
  </Box></ThemeProvider>
}
createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>)
