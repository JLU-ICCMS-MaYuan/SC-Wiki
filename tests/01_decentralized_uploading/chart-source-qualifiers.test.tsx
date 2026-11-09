import { expect, it } from 'vitest'
import { emptyPropertyRecord, propertyRecordSummaryValue, normalizeCurrentTcValue } from '../../frontend/src/lib/propertyModules'
import { setTcParameter } from '../../frontend/src/lib/tcParameters'
import { collectPropertyRows } from '../../frontend/src/lib/paperDetailView'

const tc = () => ({ ...emptyPropertyRecord('superconductive_properties'), record_type: 'predicted_tc' as const,
  value_kind: 'number' as const, value_number: 100, value_raw: '~100 K', property_code: 'tc' })

it('表单摘要与公开详情均保留当前读图约数', () => {
  const record = tc()
  expect(propertyRecordSummaryValue(record)).toBe('≈100 K')
  const rows = collectPropertyRows({ material_states: [{ material: 'YH10', pressure_value_gpa: 400,
    property_modules: [{ records: [record] }] }] })
  expect(rows[0].value).toBe('≈100 K')
})

it('旧原文约数不能改写新值或复活已清空数值', () => {
  expect(propertyRecordSummaryValue({ ...tc(), value_number: 120 })).toBe('120 K')
  expect(propertyRecordSummaryValue({ ...tc(), value_number: null })).toBe('待填写 Tc')
  expect(normalizeCurrentTcValue(tc()).value_raw).toBe('~100')
  expect(normalizeCurrentTcValue({ ...tc(), value_number: 120 }).value_raw).toBe('120')
  expect(propertyRecordSummaryValue({ ...tc(), value_raw: '~100 mK' })).toBe('100 K')
})

it('参数同值事件保留约数及引用，改值清除过时限定', () => {
  const record = { ...tc(), payload: { parameters: { lambda_ep: {
    value_kind: 'number', value_number: 2.5, value_raw: '~2.5', evidences: [{ paper_evidence_id: 8 }],
  } } } }
  expect((setTcParameter(record, 'lambda_ep', 2.5).parameters as any).lambda_ep).toEqual(record.payload.parameters.lambda_ep)
  expect((setTcParameter(record, 'lambda_ep', 2.7).parameters as any).lambda_ep.value_raw).toBe('2.7')
})

it('公开计算参数使用既有数量对象保留约数，不显示为测量误差', () => {
  const record = { ...tc(), payload: { parameters: { lambda_ep: {
    value_kind: 'number', value_number: 2.5, value_raw: '~2.5', unit_raw: '1',
  } } } }
  const rows = collectPropertyRows({ material_states: [{ material: 'YH10', property_modules: [{ records: [record] }] }] })
  const lambda = rows.find(row => row.key.includes('parameter-'))
  expect(lambda?.value).toBe('≈2.5')
  expect(lambda?.note).not.toContain('±')
})
