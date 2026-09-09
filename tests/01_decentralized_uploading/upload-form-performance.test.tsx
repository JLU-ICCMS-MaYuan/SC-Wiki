import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const counters = vi.hoisted(() => ({ cardPanels: 0, recordForms: 0 }))
const recordDefinition = vi.hoisted(() => ({
  definition_key: 'record.superconductive_properties.measured_tc.resistivity', version: 1,
  target_kind: 'property_record', module_code: 'superconductive_properties', record_type: 'measured_tc',
  method_code: 'resistivity', property_code: 'tc', core_schema: { type: 'object', properties: {} },
  json_schema: { type: 'object', properties: {} }, ui_schema: {}, status: 'published', checksum: 'performance-test',
}))

vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({
  default: () => {
    counters.cardPanels += 1
    return <div data-testid="mock-structure-panel" />
  },
}))

vi.mock('../../frontend/src/components/SchemaDrivenRecordForm', () => ({
  default: (props: { record: { record_key: string; value_raw: string }; onChange: (record: unknown) => void }) => {
    counters.recordForms += 1
    return <input data-testid={`mock-record-${props.record.record_key}`} value={props.record.value_raw}
      onChange={() => props.onChange({ ...props.record, value_raw: `${props.record.value_raw}!` })} />
  },
}))

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))

import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import { api } from '../../frontend/src/lib/api'
import { emptyPropertyModule, type PropertyModuleDraft, type PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'

const makeState = (index: number) => ({
  material: `M${index}`,
  structure_families: [],
  material_dimensionality: 'unknown',
  crystal_system: 'unknown',
  reported_space_group_number: null,
  reported_space_group_symbol: null,
  property_modules: [],
})

const spaceGroups = Array.from({ length: 230 }, (_, index) => ({ number: index + 1, symbol: `SG-${index + 1}` }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  counters.cardPanels = 0
  counters.recordForms = 0
})

describe('Issue #96 上传表单性能回归', () => {
  it('修改一个材料状态时不重新渲染其他状态卡片', async () => {
    const Harness = () => {
      const [states, setStates] = useState(() => Array.from({ length: 5 }, (_, index) => makeState(index)))
      return <MaterialStatesEditor states={states} onChange={setStates} catalogs={null} spaceGroups={spaceGroups} />
    }
    render(<Harness />)
    await waitFor(() => expect(screen.getAllByTestId('mock-structure-panel')).toHaveLength(5))
    counters.cardPanels = 0

    fireEvent.mouseDown(screen.getAllByRole('combobox', { name: '晶系' })[0])
    fireEvent.click(screen.getByRole('option', { name: '立方' }))

    expect(counters.cardPanels).toBe(1)
  })

  it('空间群自由输入不逐字符更新父级草稿', async () => {
    const onChange = vi.fn()
    render(<MaterialStatesEditor states={[makeState(0)]} onChange={onChange} catalogs={null} spaceGroups={spaceGroups} />)
    const input = screen.getAllByRole('combobox', { name: '空间群符号' })[0]

    await userEvent.setup().type(input, 'P6')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('选择空间群候选后提交最终值', async () => {
    const onChange = vi.fn()
    render(<MaterialStatesEditor states={[makeState(0)]} onChange={onChange} catalogs={null} spaceGroups={spaceGroups} />)
    const input = screen.getAllByRole('combobox', { name: '空间群符号' })[0]
    const user = userEvent.setup()
    await user.click(input)
    await user.click(await screen.findByRole('option', { name: 'SG-1' }))
    await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange.mock.calls[0][0][0]).toEqual(expect.objectContaining({ reported_space_group_symbol: 'SG-1', reported_space_group_number: 1 }))
  })

  it('编辑一条物性记录时不重绘其他记录且不增加定义请求', async () => {
    vi.mocked(api.get).mockImplementation(async path => (
      path.startsWith('/api/form-definitions?') ? [recordDefinition] as never : recordDefinition as never
    ))
    const makeRecord = (recordKey: string, value: string): PropertyRecordDraft => ({
      record_key: recordKey, module_code: 'superconductive_properties', record_type: 'measured_tc',
      property_code: 'tc', definition_key: recordDefinition.definition_key, definition_version: 1,
      method_code: 'resistivity', name_raw: 'Tc', value_kind: 'text', value_raw: value,
      value_number: null, unit_raw: 'K', canonical_unit: 'K', payload: {},
    })
    const initial: PropertyModuleDraft[] = [{
      ...emptyPropertyModule('superconductive_properties'), module_key: 'performance-module',
      records: [makeRecord('first', '4.2 K'), makeRecord('second', '3.8 K')],
    }]
    const Harness = () => {
      const [modules, setModules] = React.useState(initial)
      return <PropertyModuleEditor modules={modules} onChange={setModules} />
    }
    render(<Harness />)
    await waitFor(() => expect(screen.getByTestId('mock-record-second')).toBeInTheDocument())
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThanOrEqual(2))
    await waitFor(() => expect(counters.recordForms).toBeGreaterThanOrEqual(4))
    const requestCount = vi.mocked(api.get).mock.calls.length
    counters.recordForms = 0
    fireEvent.change(screen.getByTestId('mock-record-first'), { target: { value: '4.3 K' } })
    expect(counters.recordForms).toBe(1)
    expect(vi.mocked(api.get).mock.calls).toHaveLength(requestCount)
  })
})
