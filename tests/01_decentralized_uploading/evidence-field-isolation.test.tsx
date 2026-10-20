import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { changedScientificFields, currentEvidenceField, evidenceFieldAffected } from '../../frontend/src/lib/evidenceFields'
import { api } from '../../frontend/src/lib/api'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() } }))
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks() })

const state = (): DraftMaterialState => ({ state_key: 's', material: 'LaSc2H24', element_count: 3,
  crystal_system: 'hexagonal', reported_space_group_symbol: 'P6/mmm', reported_space_group_number: 191,
  state_kind: 'theoretical', structure_optimization: 'classical_static', structure_families: [], property_modules: [] })
const fields = ['material', 'element_count', 'reported_space_group_symbol', 'reported_space_group_number', 'crystal_system', 'structure_optimization']
const records = (): EvidenceRecord[] => fields.map(field => ({ key: field, item_key: field, state_key: 's',
  field: `material_states[0].${field}`, label: field, current_value: state()[field as keyof DraftMaterialState],
  status: 'supported', reason: '已核验', evidences: [], human_confirmed: true, resolution: '保留的人工说明',
  ...(['element_count', 'reported_space_group_number', 'crystal_system'].includes(field) ? {
    dependency: field === 'element_count' ? 'material' : 'reported_space_group_symbol', provenance: { kind: 'derived' },
  } : {}),
}))

function Form() {
  const [states, setStates] = useState([state()])
  const flow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'isolation' },
    getCurrentValue: record => currentEvidenceField(record, {}, states) })
  return <div data-evidence-scope="isolation">
    <MaterialStatesEditor states={states} onChange={setStates} onScientificEdit={flow.invalidate} />
    <EvidenceFieldMarkers scope="isolation" records={flow.records} onOpen={flow.openIssue} onChange={flow.invalidate} />
    <output data-testid="records">{JSON.stringify(flow.records)}</output>
    <button onClick={() => flow.invalidate('material_states[0].structure_optimization')}>同值通知</button>
    <button onClick={() => {
      flow.invalidate('material_states[0].structure_optimization')
      setStates(current => current.map(row => ({ ...row, structure_optimization: 'sscha' })))
    }}>程序修改</button>
    <button onClick={() => { flow.invalidate('material_states[0].material'); setStates(current => current.map(row => ({ ...row, material: 'LaH10' }))) }}>修改化学式</button>
    <button onClick={() => void flow.restore({ target: 'upload', target_id: 'isolation' })}>重新读取</button>
  </div>
}

it('真实编辑器只改核处理时，三个派生项及其人工说明保持有效；重复通知不误标', async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: records() })
  await act(async () => { render(<Form />) })
  fireEvent.mouseDown(screen.getByLabelText('结构优化核处理'))
  await act(async () => { fireEvent.click(screen.getByRole('option', { name: '量子非谐优化（SSCHA）' })); await vi.advanceTimersByTimeAsync(1) })
  const current = JSON.parse(screen.getByTestId('records').textContent!) as EvidenceRecord[]
  expect(current.find(r => r.key === 'structure_optimization')?.stale).toBe(true)
  for (const key of ['element_count', 'reported_space_group_number', 'crystal_system']) {
    expect(current.find(r => r.key === key)).toMatchObject({ human_confirmed: true, resolution: '保留的人工说明' })
    expect(current.find(r => r.key === key)?.stale).not.toBe(true)
  }
})

it('原生同值事件和显式重复通知不清除确认，也不产生新失效', async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: records() })
  await act(async () => { render(<Form />) })
  await act(async () => { fireEvent.click(screen.getByText('同值通知')); await vi.advanceTimersByTimeAsync(1) })
  expect(JSON.parse(screen.getByTestId('records').textContent!).every((r: EvidenceRecord) => !r.stale && r.human_confirmed)).toBe(true)
})

it('真实派生输入变化仍影响对应字段，核处理不扩散到无关派生项', () => {
  const [formula, count, symbol, number, crystal] = records()
  expect(evidenceFieldAffected(count, formula.field, records())).toBe(true)
  expect(evidenceFieldAffected(number, symbol.field, records())).toBe(true)
  expect(evidenceFieldAffected(crystal, symbol.field, records())).toBe(true)
  expect(evidenceFieldAffected(count, symbol.field, records())).toBe(false)
  expect(evidenceFieldAffected(number, 'material_states[0].structure_optimization', records())).toBe(false)
})

it.each(['pressure_value_gpa', 'structure_optimization', 'note'])(
  '编辑 %s 不误伤三个程序派生项，物性仅按明确的状态依赖失效', field => {
    for (const row of records().filter(row => row.provenance?.kind === 'derived')) {
      expect(evidenceFieldAffected(row, `material_states[0].${field}`, records())).toBe(false)
    }
    const property = { ...records()[0], field: 'material_states[0].property_modules[0].records[0]', record_key: 'p' }
    expect(evidenceFieldAffected(property, `material_states[0].${field}`, records())).toBe(field === 'pressure_value_gpa')
    expect(evidenceFieldAffected(property, `material_states[1].${field}`, records())).toBe(false)
  },
)

it('旧派生记录只回退已知规则，单位变化仍影响换算，其他记录及排序保持隔离', () => {
  const count = { ...records()[1], dependency: undefined }
  expect(evidenceFieldAffected(count, 'material_states[0].reported_space_group_symbol', records())).toBe(false)
  expect(evidenceFieldAffected(count, 'material_states[0].material', records())).toBe(true)
  const converted = { ...count, field: 'material_states[0].pressure_value_gpa' }
  expect(evidenceFieldAffected(converted, 'material_states[0].pressure_unit_raw')).toBe(true)
  const before = [{ state_key: 'a', material: 'Sn' }, { state_key: 'b', material: 'Pb' }]
  expect(changedScientificFields(before, [...before].reverse(), 'material_states')).toEqual([])
  expect(changedScientificFields(null, '', 'paper.doi')).toEqual([])
})

it('迟到核对不能覆盖请求之后的编辑，失败恢复也保留无关项', async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: records() })
  await act(async () => { render(<Form />) })
  let resolve!: (value: unknown) => void
  vi.mocked(api.post).mockImplementationOnce(() => new Promise(done => { resolve = done }) as never)
  await act(async () => { fireEvent.click(screen.getByText('重新读取')) })
  await act(async () => { fireEvent.click(screen.getByText('程序修改')); await vi.advanceTimersByTimeAsync(1) })
  await act(async () => { resolve({ version: 'old', records: records() }) })
  let current = JSON.parse(screen.getByTestId('records').textContent!) as EvidenceRecord[]
  expect(current.find(r => r.key === 'structure_optimization')?.stale).toBe(true)
  expect(current.find(r => r.key === 'element_count')?.human_confirmed).toBe(true)
  vi.mocked(api.post).mockRejectedValueOnce(new Error('保存/读取失败'))
  await act(async () => { fireEvent.click(screen.getByText('重新读取')) })
  current = JSON.parse(screen.getByTestId('records').textContent!) as EvidenceRecord[]
  expect(current.find(r => r.key === 'element_count')?.human_confirmed).toBe(true)
  await act(async () => { fireEvent.click(screen.getByText('修改化学式')); await vi.advanceTimersByTimeAsync(1) })
  expect((JSON.parse(screen.getByTestId('records').textContent!) as EvidenceRecord[]).find(r => r.key === 'element_count')?.stale).toBe(true)
})

it('删除前一材料状态后，不用旧数组下标误伤移到该位置的状态', async () => {
  vi.useFakeTimers()
  const rows = [state(), { ...state(), state_key: 'second', material: 'Sn', element_count: 1 }]
  const checks = [...records(), ...records().map(r => ({ ...r, key: 'second-' + r.key, item_key: 'second-' + r.item_key,
    state_key: 'second', field: r.field.replace('[0]', '[1]') }))]
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: checks })
  function Remove() {
    const [states, setStates] = useState(rows)
    const flow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'remove' },
      getCurrentValue: r => currentEvidenceField(r, {}, states) })
    return <><button onClick={() => { setStates(current => current.slice(1)); flow.invalidate('material_states[0]') }}>删除前项</button>
      <output data-testid="remaining">{JSON.stringify(flow.records)}</output></>
  }
  await act(async () => { render(<Remove />) })
  await act(async () => { fireEvent.click(screen.getByText('删除前项')); await vi.advanceTimersByTimeAsync(1) })
  const current = JSON.parse(screen.getByTestId('remaining').textContent!) as EvidenceRecord[]
  expect(current.filter(r => r.state_key === 'second').every(r => !r.stale && r.human_confirmed)).toBe(true)
})
