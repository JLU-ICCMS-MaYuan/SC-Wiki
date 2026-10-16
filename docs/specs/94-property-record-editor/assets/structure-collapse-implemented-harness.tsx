// 仅供隔离浏览器验证：真实共享组件及 3Dmol，模拟结构与来源，不访问业务 API。
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Box, Button, CssBaseline, Dialog, DialogTitle, ThemeProvider, Typography } from '@mui/material'
import theme from '../../../../frontend/src/theme'
import { LanguageProvider } from '../../../../frontend/src/context/LanguageContext'
import MaterialStatesEditor from '../../../../frontend/src/components/MaterialStatesEditor'
import EvidenceFieldMarkers from '../../../../frontend/src/components/EvidenceFieldMarkers'
import PaperEditView from '../../../../frontend/src/components/PaperEditView'
import type { EvidenceRecord } from '../../../../frontend/src/components/EvidenceWorkflow'
import type { DraftMaterialState, StructureCandidate } from '../../../../frontend/src/lib/paperProcessing'

const cif = (length: number) => `data_fixture
_cell_length_a ${length}
_cell_length_b 8
_cell_length_c 8
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Sn1 Sn 0 0 0
Sn2 Sn 0.5 0.5 0.5
`
const poscar = `Sn fixture
1
8 0 0
0 8 0
0 0 8
Sn
2
Direct
0 0 0
0.5 0.5 0.5
`
const candidates: StructureCandidate[] = ['first', 'second'].map(id => ({
  candidate_id: id, material_state_ref: 'material_states[0]', status: 'valid', confirmation: 'unreviewed',
  validation: { ase_valid: true, structure_hash: `fixture-${id}` }, sources: [{ filename: `${id}-synthetic.cif` }],
  representations: { conventional: { cif: { text: cif(8) }, poscar: { text: poscar } }, primitive: { cif: { text: cif(7) }, poscar: { text: poscar.replace('8 0 0', '7 0 0') } } },
}))
const state: DraftMaterialState = { state_key: 'fixture', material: 'Sn', material_name: '模拟材料', state_kind: 'experimental', structure_families: [], tc_results: [], properties: [], property_modules: [
  { module_key: 'fixture-module', module_code: 'electronic_properties', definition_key: 'module.electronic_properties', definition_version: 1, display_order: 0, records: [] },
] }
const records: EvidenceRecord[] = candidates.map(item => ({ key: item.candidate_id, state_key: 'fixture', structure_hash: item.validation!.structure_hash,
  field: 'material_states[0].structures[0]', label: '晶体结构', status: 'uncertain', reason: '模拟来源核对', evidences: [] }))

function Harness() {
  const [mode, setMode] = useState('edit')
  const [source, setSource] = useState('')
  const [writes, setWrites] = useState(0)
  const [uploads, setUploads] = useState(0)
  const [items, setItems] = useState(candidates)
  const changed = () => setWrites(value => value + 1)
  return <ThemeProvider theme={theme}><CssBaseline /><BrowserRouter><LanguageProvider>
    <Box sx={{ maxWidth: 1100, m: 'auto', p: 2, minWidth: 0 }}>
      <Typography variant="h6">晶体结构正式组件验证（模拟数据）</Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', my: 1 }}>
        {['edit', 'readonly', 'empty', 'detail'].map(value => <Button key={value} onClick={() => setMode(value)}>{value}</Button>)}
        <Button onClick={() => setItems([...items, { ...candidates[0], candidate_id: `added-${items.length}` }])}>模拟新增候选</Button>
      </Box>
      <Typography data-validation-counts>科学修改 {writes} · 上传 {uploads}</Typography>
      {mode === 'detail' ? <PaperEditView paper={{ id: 1, title: '模拟论文', material_states: [{ ...state, structures: [{ id: 1, filename: 'synthetic.cif', structure_text: cif(8), structure_format: 'cif' }] }] }} onBack={() => setMode('edit')} />
        : <Box key={mode} data-evidence-scope="fixture">
          <EvidenceFieldMarkers records={mode === 'empty' ? [] : records} scope="fixture" onOpen={key => setSource(key)} onChange={changed} />
          <MaterialStatesEditor states={[state]} catalogs={{ material_families: [], structure_families: [], material_dimensionalities: [] }}
            readOnly={mode === 'readonly'} structureCandidates={mode === 'empty' ? [] : items} onChange={changed} onStructureCandidatesChange={changed}
            onUploadStructure={async () => { setUploads(value => value + 1) }} />
        </Box>}
      <Dialog open={Boolean(source)} onClose={() => setSource('')}><DialogTitle>模拟来源：{source}</DialogTitle><Button onClick={() => setSource('')}>关闭来源</Button></Dialog>
    </Box>
  </LanguageProvider></BrowserRouter></ThemeProvider>
}

// 拦截所有网络请求，记录请求但不向业务服务发送。
const requests: string[] = []
window.fetch = async (input, init) => {
  requests.push(`${init?.method || 'GET'} ${String(input)}`)
  document.documentElement.dataset.fixtureRequests = JSON.stringify(requests)
  return new Response(JSON.stringify({ definitions: [], items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } })
}
window.addEventListener('error', event => { document.documentElement.dataset.fixtureError = event.message })
window.addEventListener('unhandledrejection', event => { document.documentElement.dataset.fixtureError = String(event.reason) })
createRoot(document.getElementById('root')!).render(<Harness />)
