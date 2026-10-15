import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import { emptyPropertyRecord, PROPERTY_MODULES, type PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import { validateRecordClient, type FormDefinition } from '../../frontend/src/lib/formDefinitions'
import { newStabilityRecord, validateStability } from '../../frontend/src/lib/thermodynamicStability'
import { materialStateSummary } from '../../frontend/src/lib/materialStateSummary'

afterEach(cleanup)
function mount(initial: PropertyRecordDraft, definition?: FormDefinition) {
  const changed = vi.fn()
  function Form() {
    const [record, setRecord] = useState(initial)
    return <SchemaDrivenRecordForm record={record} definition={definition} onChange={next => { changed(next); setRecord(next) }} />
  }
  render(<Form />)
  return () => changed.mock.calls.at(-1)?.[0] as PropertyRecordDraft
}
it.each(PROPERTY_MODULES)('$label 的参数与补充条件独立成行，编辑保留原始值及证据', module => {
  const record = { ...emptyPropertyRecord(module.code), name_raw: '自定义性质', value_raw: '2 eV', value_number: 2, unit_raw: 'eV' }
  const definition = { property_code: 'custom', json_schema: { type: 'object', additionalProperties: true } } as FormDefinition
  const latest = mount(record, definition)
  expect(screen.queryByText('参数')).not.toBeInTheDocument()
  expect(screen.queryByText('补充计算条件')).not.toBeInTheDocument()
  expect(screen.getAllByText('新增字段')).toHaveLength(2)
  fireEvent.click(screen.getAllByText('新增字段')[0])
  fireEvent.click(screen.getAllByText('新增字段')[1])
  const rows = document.querySelectorAll('[data-extension-row]')
  expect(rows).toHaveLength(2)
  fireEvent.change(within(rows[0] as HTMLElement).getByLabelText('字段名称'), { target: { value: '补充参数 A' } })
  fireEvent.change(within(rows[1] as HTMLElement).getByLabelText('字段名称'), { target: { value: '独立计算条件 B' } })
  expect((latest().payload.parameters as any).extensions[0].name_raw).toBe('补充参数 A')
  expect((latest().payload.calculation_conditions as any).extensions[0].name_raw).toBe('独立计算条件 B')
  expect(latest()).toMatchObject({ value_raw: '2 eV', value_number: 2 })
  fireEvent.change(within(rows[0] as HTMLElement).getByLabelText('值'), { target: { value: '1e-' } })
  expect(validateRecordClient(latest()).some(issue => issue.field.endsWith('extensions.0.value_raw'))).toBe(true)
  fireEvent.change(within(rows[0] as HTMLElement).getByLabelText('值'), { target: { value: '0' } })
  expect(validateRecordClient(latest())).toEqual([])
})
it('扩展编辑/删除保留其他扩展与条件证据', () => {
  const initial = { ...emptyPropertyRecord('electronic_properties'), name_raw: 'band gap', value_raw: '1', value_number: 1,
    payload: { parameters: { source: 'keep', extensions: [{ field_key: 'a', name_raw: 'A', value_kind: 'number', value_raw: '1', value_number: 1, evidences: [{ quote: 'proof' }] }, { field_key: 'b', name_raw: 'B', value_kind: 'text', value_raw: 'text', value_text: 'text' }] } } }
  const latest = mount(initial, { property_code: 'custom', json_schema: { type: 'object', properties: { parameters: { type: 'object', properties: { extensions: { type: 'array' } } } } } } as FormDefinition)
  fireEvent.change(screen.getAllByLabelText('字段名称')[0], { target: { value: 'new name' } })
  expect((latest().payload.parameters as any).extensions[0].evidences).toEqual([{ quote: 'proof' }])
  fireEvent.click(screen.getAllByLabelText('删除扩展字段')[1])
  expect((latest().payload.parameters as any).extensions).toHaveLength(1)
  expect((latest().payload.parameters as any).source).toBe('keep')
})
it('热力学按依据保存不同结论、温度与 ZPE，未知不默认室温或零值', async () => {
  const latest = mount(newStabilityRecord(emptyPropertyRecord('thermodynamical_properties')))
  expect(screen.getByLabelText('温度 (K)')).toHaveValue(null)
  const choose = async (label: string, option: string) => { await userEvent.click(screen.getByLabelText(label)); await userEvent.click(screen.getByRole('option', { name: option, exact: true })) }
  await choose('凸包依据', '形成焓 ΔH')
  expect(screen.getByLabelText('温度 (K)')).toBeDisabled()
  expect(screen.getByLabelText('温度 (K)')).toHaveValue(0)
  await choose('相对分解路径的稳定性', '不稳定')
  expect(screen.getByLabelText('Enthalpy above hull')).toHaveValue(null)
  fireEvent.change(screen.getByLabelText('Enthalpy above hull'), { target: { value: '0.025' } })
  fireEvent.change(screen.getByLabelText('分解路径'), { target: { value: 'A + B' } })
  await choose('凸包依据', '形成 Gibbs 自由能 ΔG')
  expect(screen.queryByLabelText('Gibbs free energy above hull')).not.toBeInTheDocument()
  expect(screen.getByLabelText('温度 (K)')).toHaveValue(null)
  expect(screen.getByLabelText('分解路径')).toHaveValue('')
  await choose('相对分解路径的稳定性', '不稳定')
  fireEvent.change(screen.getByLabelText('Gibbs free energy above hull'), { target: { value: '0' } })
  fireEvent.change(screen.getByLabelText('温度 (K)'), { target: { value: '500' } })
  await choose('零点振动能 ZPE', '已计入')
  await choose('凸包依据', '形成焓 ΔH')
  expect(screen.getByLabelText('Enthalpy above hull')).toHaveValue(0.025)
  expect(screen.getByLabelText('分解路径')).toHaveValue('A + B')
  expect(screen.getByLabelText('零点振动能 ZPE')).toHaveTextContent('论文未说明')
  expect(validateStability(latest())).toEqual([])
  expect((latest().payload.thermodynamic_stability as any).cases.formation_gibbs).toMatchObject({ temperature_k: 500, above_hull: 0, zpe: 'included' })
  await choose('相对分解路径的稳定性', '稳定')
  expect((latest().payload.thermodynamic_stability as any).cases.formation_enthalpy.above_hull).toBeNull()
  expect(latest()).toMatchObject({ value_raw: '稳定', value_text: '稳定' })
})
it('标题只展示现有三元信息，缺失、零压与原始单位明确区分', () => {
  expect(materialStateSummary({ material: 'LaSc2H24', reported_space_group_symbol: 'P6/mmm', pressure_value_gpa: 0 })).toBe('P6/mmm · LaSc₂H₂₄ · 0 GPa')
  expect(materialStateSummary({ material: '', pressure_raw: '20', pressure_unit_raw: 'kbar' })).toBe('空间群未填写 · 化学式未填写 · 20 kbar')
})
