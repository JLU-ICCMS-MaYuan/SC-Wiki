import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import type { PropertyModuleDraft, PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import { applyEvidencePatches } from '../../frontend/src/lib/evidenceProposals'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))
const definitions = ['other', 'mcmillan', 'unknown'].map(method => ({
  definition_key: `record.superconductive_properties.predicted_tc.${method}`, version: 1,
  target_kind: 'property_record', module_code: 'superconductive_properties', record_type: 'predicted_tc',
  method_code: method, property_code: 'tc', status: 'published', core_schema: {},
  json_schema: { type: 'object', properties: {} }, ui_schema: {}, checksum: method,
}))
beforeEach(() => {
  clearFormDefinitionCache()
  vi.mocked(api.get).mockImplementation(async path => (path.includes('?') ? definitions : definitions.find(d => path.includes(encodeURIComponent(d.definition_key)))) as never)
})
afterEach(() => { cleanup(); clearFormDefinitionCache(); vi.clearAllMocks() })

it.each([1, 2])('计算方法标题对%d个温度使用同一格式，方法名称不随数量变化', async count => {
  const value = module(); value.records = value.records.slice(0, count)
  render(<PropertyModuleEditor modules={[value]} onChange={vi.fn()} />)
  fireEvent.click(screen.getByText('超导性质'))
  expect(await screen.findByText(`计算方法 · ${count} 个温度`)).toBeInTheDocument()
  expect(await screen.findByLabelText('具体方法名称')).toHaveValue('solver A')
})

it.each([1, 2])('未知具体类别的%d个温度不新增方法描述输入，历史资料不丢', async count => {
  const value=module();value.records=value.records.slice(0,count)
  for(const r of value.records){r.method_code='unknown';r.definition_key=definitions[2].definition_key;(r.payload.tc_group as any).method_name='Eliashberg equations, variant unspecified'}
  const change=vi.fn();render(<PropertyModuleEditor modules={[value]} onChange={change}/>);fireEvent.click(screen.getByText('超导性质'))
  expect(await screen.findByRole('combobox',{name:'预测方法'})).toHaveTextContent('未说明方法')
  expect(screen.queryByLabelText('方法描述')).not.toBeInTheDocument()
  expect(screen.queryByDisplayValue('Eliashberg equations, variant unspecified')).not.toBeInTheDocument()
  expect(screen.getByRole('combobox',{name:'预测方法'})).toHaveTextContent('未说明方法')
  expect(value.records.map(r=>r.method_code)).toEqual(Array(count).fill('unknown'))
  expect(change).not.toHaveBeenCalled()
})

it('清空共同名称保留空输入，切换标准方法保持原文、来源与方法编号', async () => {
  const original=module();let latest=original
  function Host(){const [value,setValue]=useState(original);latest=value;return <PropertyModuleEditor modules={[value]} onChange={values=>setValue(values[0])}/>}
  render(<Host/>);fireEvent.click(screen.getByText('超导性质'))
  const name=(await screen.findAllByLabelText('具体方法名称'))[0]
  fireEvent.change(name,{target:{value:''}})
  expect(name).toHaveValue('')
  expect(latest.records.map(r=>r.method_raw)).toEqual(original.records.map(r=>r.method_raw))
  const group=within(screen.getByRole('group',{name:'第1种预测方法'}))
  fireEvent.mouseDown(group.getByRole('combobox',{name:'预测方法'}))
  fireEvent.click(await screen.findByRole('option',{name:'McMillan'}))
  expect(latest.records.slice(0,2).map(r=>r.method_code)).toEqual(['mcmillan','mcmillan'])
  expect(latest.records.map(r=>r.method_raw)).toEqual(original.records.map(r=>r.method_raw))
  expect(latest.records.map(r=>r.evidences)).toEqual(original.records.map(r=>r.evidences))
  expect(latest.records.slice(0,2).map(r=>r.payload.tc_group?.method_key)).toEqual(['method-a','method-a'])
  expect(latest.records[2]).toEqual(original.records[2])
})

function module(): PropertyModuleDraft {
  const records = [131, 114, 150].map((tc, i) => ({
    record_key: `p${i}`, module_code: 'superconductive_properties', record_type: 'predicted_tc', property_code: 'tc',
    definition_key: definitions[0].definition_key, definition_version: 1, name_raw: 'Tc',
    value_kind: 'number', value_number: tc, value_raw: `${tc} K`, canonical_unit: 'K',
    method_code: 'other', method_raw: ['Original short', 'Original full name', 'Separate solver'][i],
    payload: { parameters: { mu_star: i === 1 ? .13 : .1 }, calculation_conditions: {},
      tc_group: { version: 1, group_key: 'g', method_key: i < 2 ? 'method-a' : 'method-b', point_key: `p${i}`, method_name: i < 2 ? 'solver A' : 'solver B' } },
    evidences: [{ file_id: 'si', pdf_page: 5, quote: `original source ${i}` }],
  } as PropertyRecordDraft))
  return { module_key: 'm', module_code: 'superconductive_properties', definition_key: 'module.superconductive_properties', definition_version: 1, display_order: 0, records }
}

it('修改方法及增删温度保持逐点原文、来源、稳定身份和其他方法', async () => {
  const original = module()
  let latest: PropertyModuleDraft[] = []
  function Host() {
    const [modules, setModules] = useState([structuredClone(original)])
    latest = modules
    return <><button onClick={() => setModules(JSON.parse(JSON.stringify(modules)))}>重开</button>
      <PropertyModuleEditor modules={modules} onChange={setModules} /></>
  }
  render(<Host />)
  fireEvent.click(screen.getByText('超导性质'))
  await waitFor(() => expect(screen.getAllByLabelText('具体方法名称')).toHaveLength(2))
  fireEvent.change(screen.getAllByLabelText('具体方法名称')[0], { target: { value: 'Corrected solver A' } })
  expect(latest[0].records.map(r => r.method_raw)).toEqual(original.records.map(r => r.method_raw))
  expect(latest[0].records[2]).toEqual(original.records[2])
  const method = () => within(screen.getByRole('group', { name: '第1种预测方法' }))
  fireEvent.click(method().getByRole('button', { name: '添加 Tc／μ* 组合' }))
  const added = latest[0].records.at(-1)!
  expect(added.payload.tc_group).toMatchObject({ group_key: 'g', method_key: 'method-a', method_name: 'Corrected solver A' })
  expect(added.value_number).toBeNull()
  expect(added.evidences).toEqual([])
  fireEvent.click(method().getByRole('button', { name: '删除第1组组合' }))
  fireEvent.click(screen.getByText('重开'))
  const second = latest[0].records.find(r => r.record_key === 'p1')!
  expect(second.method_raw).toBe('Original full name')
  expect(second.evidences).toEqual(original.records[1].evidences)
  expect(second.payload.tc_group).toMatchObject({ method_key: 'method-a', point_key: 'p1', method_name: 'Corrected solver A' })
})

it('现有候选应用与共享编辑器采用同一方法归属规则且不覆盖原文', () => {
  const original = module()
  const draft = { paper: {}, material_states: [{ state_key: 's', property_modules: [original] }] }
  const next = applyEvidencePatches(draft, [{ key: 'k', item_key: 'k', field: 'method_code',
    state_key: 's', module_key: 'm', record_key: 'p0', record_group_key: 'g', record_method_key: 'method-a',
    record_field: 'method_code', values: { '': 'other', method_raw: 'Corrected solver A' } }])
  const rows = next.material_states[0].property_modules[0].records
  expect(rows.map(r => r.method_raw)).toEqual(original.records.map(r => r.method_raw))
  expect(rows.slice(0, 2).map(r => (r.payload.tc_group as any).method_name)).toEqual(['Corrected solver A', 'Corrected solver A'])
  expect(rows[2]).toEqual(original.records[2])
})
