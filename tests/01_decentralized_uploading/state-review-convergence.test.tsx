import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { evidenceFieldAffected } from '../../frontend/src/lib/evidenceFields'
import type { EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import PaperStructuralWorkspace from '../../frontend/src/components/PaperStructuralWorkspace'
import PressureEditor from '../../frontend/src/components/PressureEditor'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'

afterEach(cleanup)
const row = (field: string, dependencies: string[] = []) => ({ key: field, item_key: field, field: `material_states[0].property_modules[0].records[0].${field}`,
  record_key: 'r', record_field: field, record_dependencies: dependencies, state_dependencies: ['material', 'pressure_value_gpa'], status: 'supported', reason: '', evidences: [] } as EvidenceRecord)

it('核处理和备注不使同状态预测值、软件或电子记录失效，明确状态依赖仍生效', () => {
  for (const record of [row('value_number'),row('payload.calculation_conditions.k_grid'),{ ...row('value_number'),record_field:undefined }]) {
    expect(evidenceFieldAffected(record, 'material_states[0].structure_optimization')).toBe(false)
    expect(evidenceFieldAffected(record, 'material_states[0].note')).toBe(false)
    expect(evidenceFieldAffected(record, 'material_states[0].pressure_value_gpa')).toBe(true)
  }
  expect(evidenceFieldAffected({...row('value_number'),state_dependencies:['structure_optimization']}, 'material_states[0].structure_optimization')).toBe(true)
})
it('Tc与μ*只按明确配对依赖，不监听整个条件对象', () => {
  const record=row('value_number',['payload.parameters.mu_star'])
  expect(evidenceFieldAffected(record,'material_states[0].property_modules[0].records[0].payload.parameters.mu_star')).toBe(true)
  expect(evidenceFieldAffected(record,'material_states[0].property_modules[0].records[0].payload.calculation_conditions.extensions.0')).toBe(false)
})
it('完整独立结构显示，已归属模型及不完整资料不重复展示', () => {
  const valid:any={candidate_id:'independent',status:'valid',retention:'retained',material_state_ref:'unassigned:paper',reported_structure:{material:'LaSc2'},representations:{conventional:{cif:{text:'data_x'}}},sources:[]}
  render(<PaperStructuralWorkspace candidates={[valid,{...valid,candidate_id:'assigned',material_state_ref:'material_states[0]',reported_structure:{material:'LaSc2H24'}},{candidate_id:'failed',status:'blocked'} as any]} observations={[{record_key:'s2',material:'LaSc2H24',cell_parameters:{a:4.7},sources:[]}]} onCandidates={()=>{}} onObservations={()=>{}} />)
  expect(screen.getByText(/LaSc2 ·/)).toBeVisible()
  expect(screen.queryByText(/LaSc2H24 ·/)).not.toBeInTheDocument()
  expect(screen.queryByText(/晶格与几何参数/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button',{name:'保留这条参数'})).not.toBeInTheDocument()
})
it('压强只保留主控件，不显示原始值单位上下限编辑区', () => {
  render(<LanguageProvider><PressureEditor state={{pressure_value_gpa:200,pressure_raw:'200 GPa',pressure_unit_raw:'GPa'} as any} index={0} onChange={()=>{}} /></LanguageProvider>)
  expect(screen.getByLabelText('压强 (GPa)')).toHaveValue('200')
  expect(screen.queryByText('原始压强、单位与范围')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('压强下限 (GPa)')).not.toBeInTheDocument()
})
