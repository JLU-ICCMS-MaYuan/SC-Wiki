import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { validateRecordClient } from '../../frontend/src/lib/formDefinitions'
import { applyEvidencePatches } from '../../frontend/src/lib/evidenceProposals'
import { normalizePropertyRecordIdentity, type PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'

afterEach(cleanup)
const record = (patch: Partial<PropertyRecordDraft> = {}): PropertyRecordDraft => ({
  record_key: 'tc-one', module_code: 'superconductive_properties', record_type: 'measured_tc',
  property_code: 'tc', definition_key: 'record.superconductive_properties.measured_tc.resistivity',
  definition_version: 1, method_code: 'resistivity', name_raw: 'critical temperature', value_kind: 'number',
  value_raw: 'about 3.78 K', unit_raw: 'K', canonical_unit: 'K', value_number: 3.78,
  payload: { experimental_conditions: { description: 'Four-probe measurement' } },
  ...patch,
})
function mount(initial = record()) {
  const changed = vi.fn()
  function Harness() {
    const [value, setValue] = useState(initial)
    return <SchemaDrivenRecordForm record={value} onChange={next => { changed(next); setValue(next) }} />
  }
  render(<Harness />)
  return { changed, latest: () => changed.mock.calls.at(-1)![0] as PropertyRecordDraft }
}

describe('Issue #94 Tc 紧凑输入', () => {
  it('只显示当前值入口，不再渲染原始记录及重复输入', () => {
    mount()
    expect(screen.getByLabelText('Tc 值')).toHaveValue('3.78')
    expect(screen.queryByLabelText('数值')).not.toBeInTheDocument()
    expect(screen.queryByText('原始记录')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('原始值')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('原始单位')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '代表结果' })).not.toBeChecked()
  })

  it('全选、连续小数和粘贴更新当前 Tc，并覆盖旧值及单位', async () => {
    const user = userEvent.setup()
    const { latest } = mount(record({ unit_raw: 'mK' }))
    const input = screen.getByLabelText('Tc 值')
    await user.clear(input)
    await user.type(input, '0.003')
    expect(input).toHaveValue('0.003')
    await user.click(input)
    await user.keyboard('{Control>}a{/Control}')
    await user.paste('4.25')
    expect(latest()).toMatchObject({ value_number: 4.25, value_raw: '4.25', unit_raw: 'K' })
    await user.click(screen.getByRole('checkbox', { name: '代表结果' }))
    expect(latest().is_representative).toBe(true)
  })

  it('临时指数不回填旧值，清空及非法值不能通过校验，零值有效', async () => {
    const user = userEvent.setup()
    const { latest } = mount()
    const input = screen.getByLabelText('Tc 值')
    await user.clear(input)
    await user.type(input, '1e')
    expect(input).toHaveValue('1e')
    expect(latest().value_number).toBeNull()
    expect(validateRecordClient(latest())).toContainEqual(expect.objectContaining({ field: 'value_number' }))
    // 其他控件更新不抹掉正在输入的指数。
    await user.click(screen.getByRole('checkbox', { name: '代表结果' }))
    expect(input).toHaveValue('1e')
    await user.type(input, '-2')
    expect(latest().value_number).toBe(0.01)
    await user.clear(input)
    expect(latest()).toMatchObject({ value_number: null, value_raw: '' })
    await user.type(input, '0')
    expect(validateRecordClient(latest())).toEqual([])
    expect(latest().value_number).toBe(0)
    expect(latest().value_raw).toBe('0')
    for (const text of ['-1', 'Infinity', '1e999', 'NaN']) {
      fireEvent.change(input, { target: { value: text } })
      expect(input).toHaveValue(text)
      expect(latest().value_number).toBeNull()
      expect(validateRecordClient(latest())).not.toEqual([])
    }
  })

  it('类型切换清理旧规范值，范围与布尔不会留下数值字段', async () => {
    const user = userEvent.setup()
    const { latest } = mount()
    await user.click(screen.getByRole('combobox', { name: '值类型' }))
    await user.click(screen.getByRole('option', { name: '范围', exact: true }))
    await user.type(screen.getByLabelText('下界'), '2')
    await user.type(screen.getByLabelText('上界'), '4')
    expect(latest()).toMatchObject({ value_kind: 'range', value_number: null, value_min: 2, value_max: 4, value_raw: '2–4', unit_raw: 'K' })
    expect(validateRecordClient(latest())).toEqual([])
    fireEvent.change(screen.getByLabelText('上界'), { target: { value: '1' } })
    expect(validateRecordClient(latest())).not.toEqual([])
    await user.click(screen.getByRole('combobox', { name: '值类型' }))
    await user.click(screen.getByRole('option', { name: '布尔', exact: true }))
    expect(latest()).toMatchObject({ value_number: null, value_min: null, value_max: null, value_boolean: false, value_raw: 'false', unit_raw: null })
    expect(validateRecordClient(latest())).toEqual([])
  })

  it('新建只填当前值即可通过校验，不再要求隐藏的原始字段', async () => {
    const { latest } = mount(record({ value_raw: '', value_number: null }))
    expect(screen.queryByText('原始值不能为空')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Tc 值'), { target: { value: '9' } })
    expect(latest().value_raw).toBe('9')
    expect(validateRecordClient(latest())).toEqual([])
    expect(validateRecordClient(record({ value_raw: '' }))).toEqual([])
  })

  it('外部新值更新输入，只读状态没有原始记录且不能编辑', () => {
    const change = vi.fn()
    const { rerender } = render(<SchemaDrivenRecordForm record={record()} onChange={change} />)
    rerender(<SchemaDrivenRecordForm record={record({ value_number: 5 })} onChange={change} readOnly />)
    expect(screen.getByLabelText('Tc 值')).toHaveValue('5')
    expect(screen.getByLabelText('Tc 值')).toBeDisabled()
    expect(screen.queryByLabelText('原始值')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '代表结果' })).toBeDisabled()
    expect(change).not.toHaveBeenCalled()
  })

  it.each([
    [{ value_number: 0 }, '0', 'K'],
    [{ value_number: 1e-7 }, '1e-7', 'K'],
    [{ value_number: 1e-6 }, '0.000001', 'K'],
    [{ value_number: 1e20 }, '100000000000000000000', 'K'],
    [{ value_number: 1e21 }, '1e+21', 'K'],
    [{ value_number: null }, '', 'K'],
    [{ value_kind: 'range', value_number: null, value_min: 0, value_max: 5 }, '0–5', 'K'],
    [{ value_kind: 'text', value_number: null, value_text: '未观察到超导' }, '未观察到超导', null],
    [{ value_kind: 'boolean', value_number: null, value_boolean: false }, 'false', null],
  ] as const)('载入表单时当前值统一为兼容表示：%j', (patch, raw, unit) => {
    const original = record(patch)
    const normalized = normalizePropertyRecordIdentity(original)
    expect(normalized).toMatchObject({ value_raw: raw, unit_raw: unit })
    expect(original.value_raw).toBe('about 3.78 K')
    expect(normalized.record_key).toBe(original.record_key)
  })

  it('应用核对建议后立即同步当前值，不把旧候选的 raw 留给下次保存', () => {
    const draft = { paper: {}, material_states: [{ state_key: 'tin', property_modules: [{ module_key: 'tc', records: [record()] }] }] }
    const updated = applyEvidencePatches(draft, [{ key: 'tc', item_key: 'tc', field: 'record',
      state_key: 'tin', module_key: 'tc', record_key: 'tc-one', values: { value_number: 8.5, value_raw: 'outdated', unit_raw: 'mK' } }])
    expect(updated.material_states[0].property_modules[0].records[0]).toMatchObject({ value_number: 8.5, value_raw: '8.5', unit_raw: 'K' })
    expect(draft.material_states[0].property_modules[0].records[0].value_number).toBe(3.78)
  })

  it('旧原始字段的核对定位到当前 Tc，不生成重复区域，数字仍可直接编辑', async () => {
    const open = vi.fn()
    render(<div data-evidence-scope="tc-test">
      <div data-state-key="tin"><div data-module-key="module-tc">
        <SchemaDrivenRecordForm record={record()} basePath="material_states[0].property_modules.0.records.0" onChange={vi.fn()} />
      </div></div>
      <EvidenceFieldMarkers scope="tc-test" records={[{
        key: 'raw-tc', field: 'material_states[0].property_modules[0].records[0]',
        fields: ['material_states[0].property_modules[0].records[0].unit_raw'],
        state_key: 'tin', module_key: 'module-tc', record_key: 'tc-one', label: 'Tc',
        status: 'uncertain', current_value: record(), reason: '旧单位需要核对', evidences: [],
      }]} onOpen={open} onChange={vi.fn()} />
    </div>)
    const label = await screen.findByRole('button', { name: 'Tc 值', exact: true })
    await userEvent.click(screen.getByLabelText('Tc 值'))
    expect(open).not.toHaveBeenCalled()
    await userEvent.click(label)
    expect(open).toHaveBeenCalledWith('raw-tc', ['raw-tc'])
  })
})
