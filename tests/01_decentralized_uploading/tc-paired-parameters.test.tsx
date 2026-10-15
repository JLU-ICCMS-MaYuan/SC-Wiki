import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { writeFileSync } from 'node:fs'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import { validateRecordClient } from '../../frontend/src/lib/formDefinitions'
import type { PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import { collectPropertyRows } from '../../frontend/src/lib/paperDetailView'

afterEach(cleanup)
const initial = (): PropertyRecordDraft => ({
  record_key: 'tc-pairs', module_code: 'superconductive_properties', record_type: 'predicted_tc', property_code: 'tc',
  definition_key: 'record.superconductive_properties.predicted_tc.allen_dynes', definition_version: 1,
  method_code: 'allen_dynes', name_raw: 'critical temperature', value_kind: 'range', value_number: null,
  value_min: 281, value_max: 311, value_raw: '281–311', unit_raw: 'K', canonical_unit: 'K',
  payload: { calculation_conditions: { calculation_code: 'QE' }, parameters: { lambda_ep: { value_number: 2.1, evidences: [{ paper_evidence_id: 81 }] }, omega_log_k: 1200,
    extensions: [ { field_key: 'other', name_raw: '其他参数', value_kind: 'number', value_number: 4, value_raw: '4' },
      { key: 'mu_star', field_key: 'mu-range', name_raw: 'μ*', value_kind: 'range', value_min: 0.10, value_max: 0.13, value_raw: '0.10–0.13', unit_raw: '1', evidences: [{ paper_evidence_id: 82 }] } ] } },
})
function mount(record = initial(), readOnly = false) {
  const changed = vi.fn()
  function Harness() {
    const [value, setValue] = useState(record)
    return <SchemaDrivenRecordForm record={value} readOnly={readOnly} onChange={next => { changed(next); setValue(next) }} />
  }
  render(<Harness />)
  return { latest: () => changed.mock.calls.at(-1)?.[0] as PropertyRecordDraft, changed }
}
const group = (index: 0 | 1) => within(screen.getByTestId(`tc-pair-${index}`))
const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } })

describe('预测 Tc 与 μ* 配对', () => {
  it('直接显示旧包装参数及 μ* 范围，常用参数只有一个入口且无上下界标签', () => {
    mount()
    expect(screen.getByLabelText('电声耦合强度 λ')).toHaveValue('2.1')
    expect(screen.getByLabelText('ωlog')).toHaveValue('1200')
    expect(group(0).getByLabelText('Tc')).toHaveValue('281')
    expect(group(0).getByLabelText('μ*')).toHaveValue('0.13')
    expect(group(1).getByLabelText('μ*')).toHaveValue('0.1')
    expect(screen.getAllByLabelText('μ*')).toHaveLength(2)
    expect(screen.queryByText(/上界|下界/)).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('其他参数')).toBeInTheDocument()
    const labels = [...screen.getByTestId('tc-input-line').querySelectorAll('input')].map(input => input.value)
    expect(labels.slice(0, 3)).toEqual(['2.1', '1200', 'critical temperature'])
  })

  it('交换两组的大小次序时不移动输入，但整体映射 Tc/μ* 规范端点并保留证据', () => {
    const { latest } = mount()
    change(group(0).getByLabelText('Tc'), '320')
    change(group(0).getByLabelText('μ*'), '0.08')
    expect(group(0).getByLabelText('Tc')).toHaveValue('320')
    expect(group(0).getByLabelText('μ*')).toHaveValue('0.08')
    expect(latest()).toMatchObject({ value_min: 311, value_max: 320, value_raw: '311–320' })
    const parameters = latest().payload.parameters as any
    expect(parameters.extensions[0]).toEqual((initial().payload.parameters as any).extensions[0])
    expect(parameters.extensions[1]).toMatchObject({ field_key: 'mu-range', value_min: 0.08, value_max: 0.10, evidences: [{ paper_evidence_id: 82 }] })
    expect(validateRecordClient(latest())).toEqual([])
    if (process.env.TC_PAIRED_PAYLOAD) writeFileSync(process.env.TC_PAIRED_PAYLOAD, JSON.stringify(latest()))
  })

  it('参数清空、零值、临时指数可校验，编辑 λ 不丢失包装证据', () => {
    const { latest } = mount()
    const lambda = screen.getByLabelText('电声耦合强度 λ')
    change(lambda, '1e')
    expect(validateRecordClient(latest())).toEqual(expect.arrayContaining([expect.objectContaining({ field: 'payload.parameters.lambda_ep' })]))
    change(lambda, '0')
    expect((latest().payload.parameters as any).lambda_ep).toMatchObject({ value_number: 0, evidences: [{ paper_evidence_id: 81 }] })
    change(group(0).getByLabelText('μ*'), '')
    expect((latest().payload.parameters as any).extensions[1]).toMatchObject({ value_min: 0.1, value_max: null })
    expect(validateRecordClient(latest())).toEqual([])
    change(group(0).getByLabelText('μ*'), '1e-')
    expect(group(0).getByLabelText('μ*')).toHaveValue('1e-')
    expect(validateRecordClient(latest())).not.toEqual([])
    change(group(0).getByLabelText('μ*'), '0.13')
    expect(validateRecordClient(latest())).toEqual([])
  })

  it('数值/范围切换只保留相应 μ* 表示，标量历史记录无需自动改写', async () => {
    const { latest } = mount()
    await userEvent.click(screen.getByRole('combobox', { name: '值类型' }))
    await userEvent.click(screen.getByRole('option', { name: '数值', exact: true }))
    change(screen.getByLabelText('Tc 值'), '300')
    const parameters = latest().payload.parameters as any
    expect(parameters.mu_star).toMatchObject({ value_number: 0.13, evidences: [{ paper_evidence_id: 82 }] })
    expect(parameters.extensions).toHaveLength(1)
    expect(screen.getAllByLabelText('μ*')).toHaveLength(1)
    expect(validateRecordClient(latest())).toEqual([])
  })

  it('只读禁用全部新增字段，外部重载按规范端点显示', () => {
    const { changed } = mount(initial(), true)
    for (const input of screen.getAllByRole('textbox').filter(input => input.closest('[data-testid="tc-input-line"]'))) expect(input).toBeDisabled()
    expect(changed).not.toHaveBeenCalled()
  })

  it('标量历史 μ* 仍为共用参数，未编辑不重写；详情摘要包含范围 μ*', () => {
    const record = initial(), parameters = record.payload.parameters as any
    parameters.mu_star = 0.12
    parameters.extensions = []
    const { changed } = mount(record)
    for (const input of screen.getAllByLabelText('μ*')) expect(input).toHaveValue('0.12')
    expect(changed).not.toHaveBeenCalled()
    const rows = collectPropertyRows({ material_states: [{ property_modules: [{ records: [initial()] }] }] })
    expect(rows.find(row => row.label === 'μ*')).toMatchObject({ value: '0.1–0.13' })
  })
})
