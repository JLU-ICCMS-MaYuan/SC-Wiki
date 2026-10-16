import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../frontend/src/lib/api'
import { DOS_SOURCE_KEY, dosSourceGroups, hasDosConflict, normalizeDosRecords } from '../../frontend/src/lib/fermiDos'
import { convertLegacyPropertyModules, emptyPropertyModule, type PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import { currentEvidenceField } from '../../frontend/src/lib/evidenceFields'
import DosFermiConflict from '../../frontend/src/components/DosFermiConflict'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
const dos = (record_key = 'dos', raw = '18.76'): PropertyRecordDraft => ({
  record_key, module_code: 'electronic_properties', record_type: 'property', property_code: 'dos_fermi',
  definition_key: 'record.electronic_properties.dos_fermi', definition_version: 1, name_raw: 'N(Ef)',
  value_kind: 'text', value_raw: raw, value_text: raw, unit_raw: 'states/spin/Ry/f.u.', payload: {},
  evidences: [{ file_id: 'main', source_name: '来源 A.pdf', page_start: 4, chunk_index: 0, quote: 'DOS fixture source A' }],
})
const definition = { definition_key: dos().definition_key, version: 1, status: 'published',
  module_code: 'electronic_properties', record_type: 'property', property_code: 'dos_fermi',
  json_schema: { type: 'object', additionalProperties: true }, core_schema: {}, ui_schema: {} }
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async path => path.startsWith('/api/form-definitions?') ? [definition] as never
    : path.startsWith('/api/form-definitions/') ? definition as never : { ok: true, data: { items: [] } } as never)
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: [] })
})
afterEach(() => { cleanup(); vi.resetAllMocks(); clearFormDefinitionCache() })

it('相同副本归为一条，保留身份、原记录与所有出处，规范化幂等', () => {
  const original = [dos(), dos('copy1'), dos('copy2')]
  original[1].evidences = [{ file_id: 'supplement', quote: 'source B' }]
  const before = structuredClone(original)
  const normalized = normalizeDosRecords(original)
  expect(normalized).toHaveLength(1)
  expect(normalized[0].record_key).toBe('dos')
  expect(normalized[0].payload[DOS_SOURCE_KEY]).toEqual({ version: 1, records: original })
  expect(dosSourceGroups(normalized[0])).toHaveLength(1)
  expect(normalized[0].evidences).toHaveLength(2)
  expect(normalizeDosRecords(normalized)).toEqual(normalized)
  expect(original).toEqual(before)
})

it('不同来源不选择第一值，修改后的当前值和来源分别保留，状态间不归并', () => {
  const normalized = normalizeDosRecords([dos(), dos('other', '19.10')])
  expect(normalized[0].value_raw).toBe('')
  expect(hasDosConflict(normalized[0])).toBe(true)
  normalized[0] = { ...normalized[0], value_raw: '18.80', value_text: '18.80' }
  expect(normalizeDosRecords(normalized)[0].value_raw).toBe('18.80')
  const anotherState = convertLegacyPropertyModules({ property_modules: [{ ...emptyPropertyModule('electronic_properties'), records: [dos('150', '18.44')] }] })
  expect(anotherState[0].records[0].value_raw).toBe('18.44')
  expect(hasDosConflict(normalized[0])).toBe(true)
})

it('后端空字段及数据库身份不会把相同 DOS 变成冲突', () => {
  const copy = { ...dos('copy'), value_number: null, canonical_unit: null, method_code: null, is_representative: false }
  expect(hasDosConflict(normalizeDosRecords([dos(), copy])[0])).toBe(false)
})

function Harness({ readOnly = false }: { readOnly?: boolean }) {
  const second = dos('other', '19.10')
  second.evidences = []
  const [modules, setModules] = useState([{ ...emptyPropertyModule('electronic_properties'), module_key: 'electronic', records: [dos(), second] }])
  const flow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'fixture' },
    getCurrentValue: record => currentEvidenceField(record, {}, [{ state_key: 'state-dos', property_modules: modules }]) })
  return <div data-evidence-scope="fermi-dos">
    <div data-state-key="state-dos"><PropertyModuleEditor modules={modules} readOnly={readOnly} onChange={setModules} /></div>
    <EvidenceFieldMarkers records={flow.records} scope="fermi-dos" onOpen={flow.openIssue} onChange={flow.invalidate} />
    {flow.dialog}
  </div>
}

it('正式共享表单只显示一行，侧栏原文区只读对照，并返回原始值输入', async () => {
  render(<Harness />)
  fireEvent.click(screen.getByText('电子性质'))
  expect(screen.getAllByLabelText('原始值')).toHaveLength(1)
  expect(screen.getByLabelText('原始值')).toHaveValue('')
  const trigger = screen.getByRole('button', { name: '数值有矛盾 · 查看来源对照', exact: true })
  fireEvent.click(trigger)
  const drawer = await screen.findByRole('dialog')
  const candidates = drawer.querySelector('[data-dos-conflict-sources]')!
  expect(candidates.closest('details')?.querySelector('summary')).toHaveTextContent('系统找到的原文')
  expect(drawer.querySelectorAll('[data-dos-source-candidate]')).toHaveLength(2)
  expect(candidates.querySelectorAll('input,textarea,select')).toHaveLength(0)
  expect(within(drawer).getByText(/DOS fixture source A/)).toBeInTheDocument()
  expect(within(drawer).getByText(/此候选缺少可核验的出处/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /采用此值/ })).not.toBeInTheDocument()
  fireEvent.click(within(drawer).getByRole('button', { name: '返回主表单修改' }))
  await waitFor(() => expect(screen.getByLabelText('原始值')).toHaveFocus())
  fireEvent.change(screen.getByLabelText('原始值'), { target: { value: '18.80' } })
  fireEvent.click(screen.getByRole('button', { name: '数值有矛盾 · 查看来源对照', exact: true }))
  expect((await screen.findByRole('dialog')).querySelectorAll('[data-dos-source-candidate]')).toHaveLength(2)
  expect(screen.getByLabelText('原始值')).toHaveValue('18.80')
  expect(api.post).not.toHaveBeenCalledWith(expect.stringMatching(/jobs|review$/), expect.anything())
})

it('已存在 DOS 时禁止新增第二条，其他电子性质仍可添加', async () => {
  render(<Harness />)
  fireEvent.click(screen.getByText('电子性质'))
  await waitFor(() => expect(api.get).toHaveBeenCalled())
  fireEvent.mouseDown(screen.getByRole('combobox', { name: '添加记录' }))
  expect(screen.queryByRole('option', { name: 'dos_fermi' })).not.toBeInTheDocument()
})

it('只读仍能看冲突，但侧栏不提供返回修改动作', async () => {
  render(<Harness readOnly />)
  fireEvent.click(screen.getByText('电子性质'))
  fireEvent.click(screen.getByRole('button', { name: '数值有矛盾 · 查看来源对照', exact: true }))
  const drawer = await screen.findByRole('dialog')
  expect(within(drawer).queryByRole('button', { name: '返回主表单修改' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('原始值')).toBeDisabled()
})

it('真实形状的核对快照能定位规范 DOS，已修改后立即出现人工说明', async () => {
  const current = normalizeDosRecords([dos(), dos('other', '19.10')])[0]
  const record: EvidenceRecord = { key: 'check-dos', item_key: 'a'.repeat(64),
    module_code: 'electronic_properties', module_key: 'electronic', state_key: 'state-dos', record_key: 'dos',
    field: 'material_states[0].property_modules[0].records[0]', label: 'N(Ef)', status: 'uncertain',
    reason: '不同 DOS 数值', current_value: { record: { ...current, module_code: undefined }, state: { material: 'LaSc2H24', pressure_value_gpa: 167 } }, evidences: [] }
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', records: [record], needs_check: false })
  render(<Harness />)
  fireEvent.click(screen.getByText('电子性质'))
  await waitFor(() => expect(api.post).toHaveBeenCalled())
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '名称', exact: true })))
  expect((await screen.findByRole('dialog')).querySelectorAll('[data-dos-source-candidate]')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: '返回主表单修改' }))
  await waitFor(() => expect(screen.getByLabelText('原始值')).toHaveFocus())
  fireEvent.change(screen.getByLabelText('原始值'), { target: { value: '19.10' } })
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '数值有矛盾 · 查看来源对照' })))
  expect(await screen.findByLabelText('人工修改判断理由（必填）')).toBeVisible()
})

it('正式记录的来源 ID 只关联本条已授权证据，不借用其他候选出处', () => {
  const current = normalizeDosRecords([dos(), dos('other', '19.10')])[0]
  const archive = current.payload[DOS_SOURCE_KEY] as { records: PropertyRecordDraft[] }
  archive.records[0].evidences = [{ paper_evidence_id: 7 }]
  archive.records[1].evidences = [{ paper_evidence_id: 8 }]
  const record: EvidenceRecord = { key: 'dos', field: 'dos', label: 'N(Ef)', reason: 'conflict',
    status: 'uncertain', current_value: { record: current },
    evidences: [{ paper_evidence_id: 7, file_id: 'main', source_name: '来源 A.pdf', chunk_index: 0, page_start: 4, quote: 'Only source A' }] }
  render(<DosFermiConflict record={record} />)
  const candidates = document.querySelectorAll('[data-dos-source-candidate]')
  expect(candidates[0]).toHaveTextContent('Only source A')
  expect(candidates[1]).not.toHaveTextContent('Only source A')
  expect(candidates[1]).toHaveTextContent('来源信息不完整')
})

it('有效人工确认会说明当前值已核对，但来源差异保留；旧确认不能为新值背书', () => {
  const current = normalizeDosRecords([dos(), dos('other', '19.10')])[0]
  const record: EvidenceRecord = { key: 'dos', field: 'dos', label: 'N(Ef)', reason: '人工判断',
    status: 'supported', human_confirmed: true, current_value: { record: current }, evidences: [] }
  const view = render(<DosFermiConflict record={record} />)
  expect(screen.getByText(/当前值已完成人工核对/)).toBeInTheDocument()
  expect(document.querySelectorAll('[data-dos-source-candidate]')).toHaveLength(2)
  view.rerender(<DosFermiConflict record={{ ...record, stale: true }} />)
  expect(screen.queryByText(/当前值已完成人工核对/)).not.toBeInTheDocument()
  expect(screen.getByText(/发现不同 DOS 数值，待人工核对/)).toBeInTheDocument()
})
