import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { currentEvidenceField } from '../../frontend/src/lib/evidenceFields'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn() } }))
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks() })

const condition = (key: string, software = 'SSCHA') => ({record_key:key, value_number:key==='old'?331:296,
  payload:{tc_group:{version:1,group_key:'g',method_key:'m'},calculation_conditions:{calculation_code:software}}})
const states = () => [{state_key:'s', property_modules:[{module_key:'m',records:[condition('old'),condition('new')]}]}]
const record = (): EvidenceRecord => ({key:'condition',item_key:'condition',state_key:'s',module_key:'m',record_key:'old',record_group_key:'g',
  record_field:'payload.calculation_conditions.calculation_code',field:'material_states[0].property_modules[0].records[0].payload.calculation_conditions.calculation_code',
  label:'计算软件',current_value:'SSCHA',status:'supported',reason:'规则通过',evidences:[],adopted_basis:'paper_inference'})

it('共用字段按组寻找新承载记录，结果字段不借用其他点', () => {
  const state=states();state[0].property_modules[0].records.shift()
  expect(currentEvidenceField(record(),{},state)).toMatchObject({value:'SSCHA',record_key:'new'})
  expect(currentEvidenceField({...record(),record_group_key:undefined,record_field:'value_number'}, {},state)).toBeUndefined()
  state[0].property_modules[0].records[0].payload.tc_group.group_key='another'
  expect(currentEvidenceField(record(),{},state)).toBeUndefined()
})

it('重排只更新定位路径；原承载点移到另一组时不串组', () => {
  const state=states();state[0].property_modules[0].records.reverse()
  expect(currentEvidenceField(record(),{},state)?.field).toContain('records[1]')
  state[0].property_modules[0].records[1].payload.tc_group.group_key='another'
  expect(currentEvidenceField(record(),{},state)).toMatchObject({value:'SSCHA',record_key:'new'})
})

it('删除组首点不撤销共用条件；剩余点的条件真正变化仍失效', async () => {
  vi.useFakeTimers()
  vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:false,records:[record()]})
  function Form() {
    const [value,setValue]=useState(states())
    const flow=useEvidenceWorkflow({target:{target:'upload',target_id:'fixture'},getCurrentValue:r=>currentEvidenceField(r,{},value)})
    return <><output data-testid="records">{JSON.stringify(flow.records)}</output>
      <button onClick={()=>{flow.invalidate('material_states[0].property_modules[0].records[0]');setValue(old=>[{...old[0],property_modules:[{module_key:'m',records:[condition('new')]}]}])}}>删除首点</button>
      <button onClick={()=>{flow.invalidate('material_states[0].property_modules[0].records[0].payload.calculation_conditions.calculation_code');setValue(old=>[{...old[0],property_modules:[{module_key:'m',records:[condition('new','QE')]}]}])}}>改变软件</button></>
  }
  await act(async()=>{render(<Form />)})
  await act(async()=>{fireEvent.click(screen.getByText('删除首点'));await vi.advanceTimersByTimeAsync(1)})
  let row=JSON.parse(screen.getByTestId('records').textContent!)[0]
  expect(row.record_key).toBe('new');expect(row.stale).not.toBe(true);expect(row.status).toBe('supported')
  await act(async()=>{fireEvent.click(screen.getByText('改变软件'));await vi.advanceTimersByTimeAsync(1)})
  row=JSON.parse(screen.getByTestId('records').textContent!)[0]
  expect(row.stale).toBe(true)
})
