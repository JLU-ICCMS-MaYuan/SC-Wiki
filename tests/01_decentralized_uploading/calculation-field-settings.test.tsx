import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import TcScientificField from '../../frontend/src/components/TcScientificField'
import type { PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import type { ParameterValue } from '../../frontend/src/lib/tcParameters'

afterEach(cleanup)
const row = (): PropertyRecordDraft => ({ record_key: 'r', module_code: 'superconductive_properties', property_code: 'tc', record_type: 'predicted_tc',
  method_code: 'isotropic_eliashberg', name_raw: 'Tc', value_kind: 'number', value_number: 311, value_raw: '311', canonical_unit: 'K',
  payload: { parameters: { lambda_ep: 3.94, omega_log: 745, mu_star: .1 }, calculation_conditions: { calculation_code: 'Quantum ESPRESSO',
    extensions: [{ key: 'electron_phonon.energy_cutoff', value_kind: 'number', value_number: 90, value_raw: '90', unit_raw: 'Ry', evidences: [{ quote: '90 Ry' }] },
      { key: 'structural_relaxation.energy_cutoff', value_kind: 'number', value_number: 850, unit_raw: 'eV' }] } } })
let latest: PropertyRecordDraft
function Harness({ readOnly = false }: { readOnly?: boolean }) {
  const [record, setRecord] = useState(row()), [version, setVersion] = useState(0)
  latest = record
  return <><button onClick={() => { setRecord(JSON.parse(JSON.stringify(record))); setVersion(version + 1) }}>保存重开</button>
    <button onClick={() => setRecord({ ...record, payload: { ...record.payload, calculation_conditions: { ...(record.payload.calculation_conditions as any), calculation_code: '人工新值' } } })}>外部修改</button>
    <SchemaDrivenRecordForm key={version} record={record} readOnly={readOnly} onChange={setRecord} /></>
}
const openNew = () => fireEvent.click(screen.getByRole('button', { name: '＋ 新增字段' }))
const apply = () => fireEvent.click(screen.getByRole('button', { name: '应用修改', exact: true }))
const waitClosed = () => waitFor(() => { expect(screen.queryByLabelText('字段名称（key）')).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: '＋ 新增字段' })).toBeVisible() })

it('固定字段改名和单位只经侧栏提交，取消保留原值且保存重开保留设置', async () => {
  render(<Harness />)
  expect(screen.queryByLabelText('字段名称')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '设置字段：计算软件' }))
  expect(within(screen.getByRole('dialog')).getByLabelText('值类型')).toHaveAttribute('aria-disabled', 'true')
  fireEvent.change(screen.getByLabelText('值'), { target: { value: '取消值' } })
  fireEvent.click(screen.getByRole('button', { name: '取消', exact: true })); await waitClosed()
  expect((latest.payload.calculation_conditions as any).calculation_code).toBe('Quantum ESPRESSO')
  fireEvent.click(screen.getByRole('button', { name: '设置字段：计算软件' }))
  fireEvent.change(screen.getByLabelText('字段名称（key）'), { target: { value: 'EPC 软件' } })
  fireEvent.change(screen.getByLabelText('单位'), { target: { value: '版本说明' } }); apply(); await waitClosed()
  fireEvent.click(screen.getByText('保存重开'))
  expect(screen.getByRole('button', { name: '设置字段：EPC 软件' })).toBeInTheDocument()
  expect((latest.payload.calculation_conditions as any).field_settings.calculation_code.unit_raw).toBe('版本说明')
  expect((latest.payload.calculation_conditions as any).extensions[1].value_number).toBe(850)
  expect(screen.queryByRole('button', { name: /设置字段：结构优化/ })).not.toBeInTheDocument()
})
it('新增先在侧栏设置，取消不产生空字段，范围非法不写入，保存和删除保留别的来源', async () => {
  render(<Harness />); openNew()
  fireEvent.click(screen.getByRole('button', { name: '取消', exact: true })); await waitClosed()
  expect((latest.payload.calculation_conditions as any).extensions).toHaveLength(2)
  openNew(); fireEvent.change(screen.getByLabelText('字段名称（key）'), { target: { value: '能量窗' } })
  fireEvent.mouseDown(within(screen.getByRole('dialog')).getByLabelText('值类型')); fireEvent.click(screen.getByRole('option', { name: '范围' }))
  fireEvent.change(screen.getByLabelText('值（下界..上界）'), { target: { value: '40..20' } })
  fireEvent.click(screen.getByRole('button', { name: '添加到表单' })); expect(screen.getByText(/范围格式/)).toBeInTheDocument()
  expect((latest.payload.calculation_conditions as any).extensions).toHaveLength(2)
  fireEvent.change(screen.getByLabelText('值（下界..上界）'), { target: { value: '20..40' } })
  fireEvent.change(screen.getByLabelText('单位'), { target: { value: 'meV' } })
  fireEvent.click(screen.getByRole('button', { name: '添加到表单' })); await waitClosed()
  fireEvent.click(screen.getByText('保存重开'))
  expect(screen.getByLabelText('能量窗')).toHaveValue('20..40')
  fireEvent.click(screen.getByRole('button', { name: '设置字段：能量窗' }))
  expect(screen.getByLabelText('单位')).toHaveValue('meV')
  fireEvent.click(screen.getByRole('button', { name: '删除这个补充字段' })); await waitClosed()
  expect((latest.payload.calculation_conditions as any).extensions).toHaveLength(2)
  expect((latest.payload.calculation_conditions as any).extensions[0].evidences).toEqual([{ quote: '90 Ry' }])
})
it('侧栏拒绝覆盖打开后被修改的字段；只读可查看但不能应用', async () => {
  const { unmount } = render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: '设置字段：计算软件' }))
  fireEvent.click(screen.getByText('外部修改')); apply()
  expect(screen.getByText('字段已发生变化，请关闭后重新打开')).toBeInTheDocument()
  expect((latest.payload.calculation_conditions as any).calculation_code).toBe('人工新值')
  unmount(); render(<Harness readOnly />)
  fireEvent.click(screen.getByRole('button', { name: '设置字段：计算软件' }))
  expect(screen.getByLabelText('字段名称（key）')).toBeDisabled()
  expect(screen.queryByRole('button', { name: '应用修改' })).not.toBeInTheDocument()
})
it('补充字段保存布尔false，切换文本时清除旧类型槽位且保留稳定身份', async () => {
  render(<Harness />); openNew()
  fireEvent.change(screen.getByLabelText('字段名称（key）'), { target: { value: '补充标记' } })
  fireEvent.mouseDown(within(screen.getByRole('dialog')).getByLabelText('值类型'))
  fireEvent.click(screen.getByRole('option', { name: '布尔' }))
  fireEvent.mouseDown(within(screen.getByRole('dialog')).getByLabelText('值'))
  fireEvent.click(screen.getByRole('option', { name: '否' }))
  fireEvent.click(screen.getByRole('button', { name: '添加到表单' })); await waitClosed()
  const original = (latest.payload.calculation_conditions as any).extensions.at(-1)
  expect(original.value_boolean).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: '设置字段：补充标记' }))
  fireEvent.mouseDown(within(screen.getByRole('dialog')).getByLabelText('值类型'))
  fireEvent.click(screen.getByRole('option', { name: '文本' }))
  fireEvent.change(within(screen.getByRole('dialog')).getByLabelText('值'), { target: { value: '手工备注' } })
  apply(); await waitClosed()
  const current = (latest.payload.calculation_conditions as any).extensions.at(-1)
  expect(current.field_key).toBe(original.field_key)
  expect(current.value_text).toBe('手工备注')
  expect(current).not.toHaveProperty('value_boolean')
})
it('具体Tc在侧栏改名与标注保持数值类型，不接受非法值', async () => {
  let value: ParameterValue = 311, metadata: any
  function TcHarness() {
    const [number, setNumber] = useState<ParameterValue>(311), [settings, setSettings] = useState<any>()
    return <TcScientificField value={number} label="Tc" unit="K" field="point-1" readOnly={false} currentTc settings={settings}
      onChange={setNumber} onApply={(n, s) => { value = n; metadata = s; setNumber(n); setSettings(s) }} />
  }
  render(<TcHarness />)
  fireEvent.click(screen.getByRole('button', { name: '设置字段：Tc' }))
  fireEvent.change(screen.getByLabelText('值'), { target: { value: '-1' } }); apply()
  expect(screen.getByText('请输入完整的非负数值')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('值'), { target: { value: '312' } })
  fireEvent.change(screen.getByLabelText('字段名称（key）'), { target: { value: '选定 Tc' } }); apply(); await waitFor(() => expect(screen.getByRole('button', { name: '设置字段：选定 Tc' })).toBeVisible())
  expect(value).toBe(312); expect(metadata).toEqual({ name_raw: '选定 Tc', unit_raw: 'K' })
})
