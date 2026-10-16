import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache, type FormDefinition } from '../../frontend/src/lib/formDefinitions'
import { type PropertyModuleDraft, type PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import { expandTcPoints, newTcPoint, selectTcPoint, tcPointViews } from '../../frontend/src/lib/predictedTcGroups'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))
const definition = (method: string): FormDefinition => ({ definition_key: `record.superconductive_properties.predicted_tc.${method}`,
  version: 1, target_kind: 'property_record', module_code: 'superconductive_properties', record_type: 'predicted_tc',
  method_code: method, property_code: 'tc', status: 'published', checksum: 'fixture', core_schema: {}, json_schema: { type: 'object' }, ui_schema: {} })
const defs = ['unknown', 'allen_dynes', 'isotropic_eliashberg'].map(definition)
const range = (): PropertyRecordDraft => ({ record_key: 'source', module_code: 'superconductive_properties', record_type: 'predicted_tc',
  property_code: 'tc', definition_key: defs[2].definition_key, definition_version: 1, method_code: 'isotropic_eliashberg',
  name_raw: 'Tc', value_kind: 'range', value_min: 281, value_max: 311, value_raw: '281–311', canonical_unit: 'K', unit_raw: 'K',
  payload: { parameters: { lambda_ep: 3.94, omega_log: 745, extensions: [{ key: 'mu_star', value_kind: 'range', value_min: 0.1, value_max: 0.16, unit_raw: '1' }] },
    calculation_conditions: { calculation_code: 'Quantum ESPRESSO', k_grid: '24×24×24' }, approximation: 'anharmonic' },
  evidences: [{ file_id: 'main', quote: 'Anharmonic 150 3.94 745 18.44 281 to 311' }] })
beforeEach(() => { vi.mocked(api.get).mockImplementation(async path => (path.includes('?') ? defs : defs.find(d => path.includes(encodeURIComponent(d.definition_key)))) as never) })
afterEach(() => { cleanup(); clearFormDefinitionCache(); vi.clearAllMocks() })

it('旧范围只读投影不改值，显式拆分保留证据及原范围，不猜未配对μ', () => {
  const original = range(), snapshot = structuredClone(original)
  expect(tcPointViews(original).map(p => [p.tc, p.mu])).toEqual([[281, 0.16], [311, 0.1]])
  const points = expandTcPoints([original])
  expect(original).toEqual(snapshot)
  expect(points.map(r => [r.value_number, (r.payload.parameters as any).mu_star])).toEqual([[281, 0.16], [311, 0.1]])
  expect(points[1].evidences).toEqual(original.evidences)
  expect(points[1].payload.tc_range_origin).toMatchObject({ value_min: 281, value_max: 311 })
  const extra = newTcPoint(points[0], 'other-method', definition('allen_dynes'))
  expect(extra.value_number).toBeNull()
  expect(extra.evidences).toEqual([])
  expect(extra.payload).not.toHaveProperty('source_associations')
  ;(original.payload.parameters as any).extensions[0].key = 'mu_star_reported_range'
  expect(tcPointViews(original).map(p => p.mu)).toEqual([null, null])
  expect(selectTcPoint([original], 'source:0', true).some(r => r.is_representative)).toBe(false)
})

it('生产共享表单保存三组与两种方法，按具体组合互斥选择并显式删除', async () => {
  const other = { ...expandTcPoints([{ ...range(), record_key: 'independent' }])[0], is_representative: true }
  let latest: PropertyModuleDraft[] = [], deletion: any
  function Harness() {
    const [modules, setModules] = useState<PropertyModuleDraft[]>([{ module_key: 'm', module_code: 'superconductive_properties',
      definition_key: 'module.superconductive_properties', definition_version: 1, display_order: 0, records: [range(), other] }])
    latest = modules
    return <><button onClick={() => setModules(JSON.parse(JSON.stringify(modules)))}>保存重开</button><PropertyModuleEditor modules={modules}
      basePath="material_states.0.property_modules" onChange={(next, removed) => { deletion = removed; setModules(next) }} /></>
  }
  render(<Harness />)
  fireEvent.click(screen.getByText('超导性质'))
  await waitFor(() => expect(screen.getAllByLabelText('预测方法')).toHaveLength(2))
  const core = () => within(screen.getByTestId('property-record-source')).getByTestId('predicted-tc-core')
  fireEvent.click(within(core()).getByRole('button', { name: '添加 Tc／μ* 组合' }))
  let third = within(core()).getByRole('group', { name: '第3组 Tc 与 μ*' })
  fireEvent.change(within(third).getByLabelText('Tc'), { target: { value: '300' } })
  third = within(core()).getByRole('group', { name: '第3组 Tc 与 μ*' })
  fireEvent.change(within(third).getByLabelText('μ*'), { target: { value: '0.13' } })
  fireEvent.click(within(core()).getByLabelText('选择第1种方法第3组为代表结果'))
  expect(latest[0].records.filter(r => r.is_representative).map(r => r.value_number)).toEqual([300])
  expect(latest[0].records.map(r => r.value_kind)).toEqual(['number', 'number', 'number', 'number'])
  fireEvent.click(within(core()).getByRole('button', { name: '新增字段', exact: true }))
  const secondMethod = within(core()).getByRole('group', { name: '第2种预测方法' })
  fireEvent.mouseDown(within(secondMethod).getByLabelText('预测方法'))
  fireEvent.click(await screen.findByRole('option', { name: 'Allen–Dynes' }))
  fireEvent.change(within(secondMethod).getByLabelText('Tc'), { target: { value: '250' } })
  fireEvent.change(within(secondMethod).getByLabelText('μ*'), { target: { value: '0.12' } })
  fireEvent.click(within(core()).getByLabelText('选择第2种方法第1组为代表结果'))
  fireEvent.click(screen.getByText('保存重开'))
  expect(latest[0].records.filter(r => r.is_representative).map(r => [r.method_code, r.value_number, (r.payload.parameters as any).mu_star])).toEqual([['allen_dynes', 250, 0.12]])
  expect(within(core()).getByText(/代表结果：Allen–Dynes/)).toBeVisible()
  const removedKey = latest[0].records.find(r => r.method_code === 'allen_dynes')!.record_key
  fireEvent.click(within(core()).getByRole('button', { name: '删除第2种方法' }))
  expect(deletion.deletedRecordKeys).toEqual([removedKey])
  expect(latest[0].records.some(r => r.is_representative)).toBe(false)
  expect(latest[0].records.find(r => r.record_key === 'independent')).toBeDefined()
})

it('只读不选择、不拆分旧范围且所有输入禁用', async () => {
  const changed = vi.fn()
  render(<PropertyModuleEditor modules={[{ module_key: 'm', module_code: 'superconductive_properties', definition_key: 'module.superconductive_properties',
    definition_version: 1, display_order: 0, records: [{ ...range(), is_representative: true }] }]} readOnly onChange={changed} />)
  fireEvent.click(screen.getByText('超导性质'))
  expect(await screen.findByText('旧范围尚未明确代表端点，请选择具体 Tc／μ* 组合。')).toBeVisible()
  expect(screen.getAllByRole('checkbox').every(input => (input as HTMLInputElement).disabled && !(input as HTMLInputElement).checked)).toBe(true)
  expect(screen.queryByRole('button', { name: '新增字段' })).not.toBeInTheDocument()
  expect(changed).not.toHaveBeenCalled()
})
