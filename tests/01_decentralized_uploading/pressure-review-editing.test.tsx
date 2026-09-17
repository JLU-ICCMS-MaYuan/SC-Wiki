import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'
import { currentEvidenceField } from '../../frontend/src/lib/evidenceFields'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
vi.mock('../../frontend/src/components/PropertyModuleEditor', () => ({ default: () => null }))
vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

const state = { state_key: 'tin', material: 'Sn', pressure_value_gpa: 0.000101, pressure_raw: '0.000101', pressure_unit_raw: 'GPa', pressure_min_gpa: 0.0001, pressure_max_gpa: 0.0002, property_modules: [] }
const record: EvidenceRecord = { key: 'pressure', item_key: 'pressure', state_key: 'tin', field: 'material_states[0].pressure_value_gpa', label: '压力', current_value: 0.000101, status: 'uncertain', reason: '派生值的输入来源尚未通过核对', evidences: [], provenance: {kind: 'derived', verified: true} }

function Editor({save = async () => true, reversed = false}: {save?: (states: DraftMaterialState[]) => Promise<boolean>; reversed?: boolean}) {
  const [states, setStates] = useState<DraftMaterialState[]>(() => {
    const initial = [state, {...state, state_key:'lead', material:'Pb'}]
    return reversed ? initial.reverse() : initial
  })
  const flow = useEvidenceWorkflow({ target: {target: 'paper', target_id: '29'}, getCurrentValue: r => currentEvidenceField(r, {}, states), saveCurrent: () => save(states) })
  return <div data-evidence-scope="pressure-test">
    <MaterialStatesEditor states={states} onChange={setStates} onScientificEdit={flow.invalidate} catalogs={null} />
    <EvidenceFieldMarkers records={flow.records} scope="pressure-test" onOpen={flow.openIssue} onChange={flow.invalidate} />
    <output data-testid="states">{JSON.stringify(states)}</output>{flow.dialog}
    <output data-testid="records">{JSON.stringify(flow.records)}</output>
    <button onClick={async () => { const revision = flow.getEditRevision(); if (await save(states)) await flow.refreshAfterSave(revision) }}>保存测试表单</button>
  </div>
}
const current = () => JSON.parse(screen.getByTestId('states').textContent!)[0]
function setup() {
  vi.mocked(api.post).mockImplementation(async () => ({version: 'v1', needs_check: false, records: [record]}))
  render(<Editor />)
  return userEvent.setup()
}

it('真实 input 事件清空带红框压强时五个字段同步清空，不影响其他状态', async () => {
  const user = setup()
  await screen.findByRole('button', {name: '压强 (GPa)'})
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  await user.clear(input)
  expect(input).toHaveValue('')
  expect(current()).toMatchObject({pressure_value_gpa: null, pressure_raw: null, pressure_unit_raw: null, pressure_min_gpa: null, pressure_max_gpa: null})
  expect(JSON.parse(screen.getByTestId('states').textContent!)[1]).toEqual({...state, state_key:'lead', material:'Pb'})
})

it('带核对标记的小数输入不跳回旧值，零有效，标签仍打开抽屉', async () => {
  const user = setup()
  await screen.findByRole('button', {name: '压强 (GPa)'})
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  await user.clear(input)
  await user.type(input, '0.0025')
  expect(input).toHaveValue('0.0025')
  expect(current().pressure_value_gpa).toBe(0.0025)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await user.clear(input)
  await user.type(input, '0')
  expect(current().pressure_value_gpa).toBe(0)
  await user.click(screen.getByRole('button', {name:'压强 (GPa)'}))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  expect(screen.getByLabelText('人工核对理由')).toBeEnabled()
})

it('输入未完成的指数不清空任何条件，直接替换数值保留原始记录', async () => {
  setup()
  await screen.findByRole('button', {name: '压强 (GPa)'})
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  fireEvent.change(input, {target:{value:'1e-'}})
  expect(current()).toEqual(state)
  expect(input).toBeInvalid()
  fireEvent.change(input, {target:{value:'1e-3'}})
  expect(current()).toMatchObject({...state, pressure_value_gpa:0.001})
  expect(input).toBeValid()
  expect(screen.getByText(/当前压强与原始值换算或范围不一致/)).toBeVisible()
})

function reviewSetup(fail = false) {
  let version = 'v1'
  let records: EvidenceRecord[] = [{...record, proposal_draft:{accepted:true, reason:'旧理由', values:{}}}]
  const save = vi.fn(async (states: DraftMaterialState[]) => {
    if (fail) return false
    version = 'v2'
    records = states[0].pressure_value_gpa == null ? [] : [{...record, stale:true, current_value:states[0].pressure_value_gpa}]
    return true
  })
  vi.mocked(api.post).mockImplementation(async (path, body: any) => {
    if (path.endsWith('preflight')) return {version, records, needs_check:records.some(r=>r.stale)}
    if (path.endsWith('proposals')) {
      expect(body.expected_version).toBe(version)
      records = records.map(r => r.key === body.key ? {...r, stale:false, proposal_draft:body} : r)
      return {draft:body}
    }
    throw new Error(`意外请求 ${path}`)
  })
  render(<Editor save={save} />)
  return {save, user:userEvent.setup(), recover:()=>{fail=false}}
}

it('修改后填写理由先保留本地，完成保存新值并绑定 v2，零模型和批准请求', async () => {
  const {save, user} = reviewSetup()
  await screen.findByText(/压力 · 已接受/)
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  fireEvent.change(input, {target:{value:'0.002'}})
  await user.click(await screen.findByRole('button', {name:'压强 (GPa)'}))
  expect(screen.getByText('0.002', {exact:true})).toBeVisible()
  const reason = screen.getByLabelText('人工核对理由')
  expect(reason).toHaveValue('')
  await user.type(reason, '根据实验记录更正压强')
  await new Promise(resolve=>setTimeout(resolve,600))
  expect(api.post).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', {name:'完成', exact:true}))
  await waitFor(()=>expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals', expect.objectContaining({expected_version:'v2', values:{}, accepted:true, reason:'根据实验记录更正压强'})))
  expect(save).toHaveBeenCalledTimes(1)
  expect(save.mock.calls[0][0][0].pressure_value_gpa).toBe(0.002)
  expect(vi.mocked(api.post).mock.calls.every(([path])=>!path.endsWith('/jobs')&&!path.endsWith('/review'))).toBe(true)
})

it('保存失败保留新值和理由，重试完成时不复用旧接受状态', async () => {
  const {user, recover} = reviewSetup(true)
  await screen.findByText(/压力 · 已接受/)
  fireEvent.change(screen.getAllByLabelText('压强 (GPa)')[0], {target:{value:'0.003'}})
  await user.click(await screen.findByRole('button', {name:'压强 (GPa)'}))
  await user.type(screen.getByLabelText('人工核对理由'), '新理由')
  await user.click(screen.getByRole('button', {name:'完成',exact:true}))
  await screen.findByText(/当前编辑尚未保存成功/)
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('新理由')
  expect(api.post).toHaveBeenCalledTimes(1)
  recover()
  await user.click(screen.getByRole('button', {name:'完成',exact:true}))
  await screen.findByRole('button', {name:/压力 · 已接受/})
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('普通保存刷新后不再展示已清空的压强问题', async () => {
  const {save, user} = reviewSetup()
  await screen.findByText(/压力 · 已接受/)
  await user.clear(screen.getAllByLabelText('压强 (GPa)')[0])
  await user.click(screen.getByRole('button', {name:'保存测试表单'}))
  await waitFor(()=>expect(screen.queryByRole('button', {name:'压强 (GPa)'})).not.toBeInTheDocument())
  expect(save.mock.calls[0][0][0]).toMatchObject({pressure_value_gpa:null,pressure_raw:null,pressure_unit_raw:null,pressure_min_gpa:null,pressure_max_gpa:null})
})

it('当前值按稳定身份读取，材料和记录排序后仍定位正确字段', () => {
  expect(currentEvidenceField(record, {}, [{...state,state_key:'lead'}, {...state,pressure_value_gpa:2}])).toEqual({value:2,field:'material_states[1].pressure_value_gpa'})
})

it('排序后实际修改锡压强只失效锡，另一状态的已接受结果保留', async () => {
  const lead = {...record, key:'lead-pressure', item_key:'lead-pressure', state_key:'lead', field:'material_states[1].pressure_value_gpa', proposal_draft:{accepted:true,values:{},reason:'铅已确认'}}
  vi.mocked(api.post).mockResolvedValue({version:'v1',records:[record,lead]})
  render(<Editor reversed />)
  const user = userEvent.setup()
  await screen.findByRole('button', {name:'压强 (GPa)'})
  await user.clear(screen.getAllByLabelText('压强 (GPa)')[1])
  await user.type(screen.getAllByLabelText('压强 (GPa)')[1], '0.002')
  const records = JSON.parse(screen.getByTestId('records').textContent!)
  expect(records.find((r:EvidenceRecord)=>r.state_key==='tin').stale).toBe(true)
  expect(records.find((r:EvidenceRecord)=>r.state_key==='lead')).toEqual(lead)
})

it('普通保存刷新保留尚未提交的新理由，不继承旧候选', async () => {
  const {user} = reviewSetup()
  await screen.findByText(/压力 · 已接受/)
  fireEvent.change(screen.getAllByLabelText('压强 (GPa)')[0], {target:{value:'0.003'}})
  await user.click(await screen.findByRole('button', {name:'压强 (GPa)'}))
  await user.type(screen.getByLabelText('人工核对理由'), '核实后的新理由')
  fireEvent.click(screen.getByText('保存测试表单'))
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('核实后的新理由')
  expect(screen.getByLabelText('人工核对理由')).toBeEnabled()
})

it('完成保存期间继续编辑时保留最新值和理由，不确认较早内容', async () => {
  let resolveSave!: (ok:boolean) => void
  const save = vi.fn(() => new Promise<boolean>(resolve => {resolveSave = resolve}))
  vi.mocked(api.post).mockResolvedValue({version:'v1',records:[record]})
  render(<Editor save={save} />)
  const user = userEvent.setup()
  await screen.findByRole('button', {name:'压强 (GPa)'})
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  fireEvent.change(input, {target:{value:'0.003'}})
  await user.click(screen.getByRole('button', {name:'压强 (GPa)'}))
  await user.type(screen.getByLabelText('人工核对理由'), '保留的新理由')
  await user.click(screen.getByRole('button', {name:'完成', exact:true}))
  await waitFor(() => expect(save).toHaveBeenCalledOnce())
  fireEvent.change(input, {target:{value:'0.004'}})
  await act(async () => resolveSave(true))
  await screen.findByText(/保存期间内容又发生变化/)
  expect(input).toHaveValue('0.004')
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('保留的新理由')
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('普通保存的迟到快照不能覆盖更晚编辑及理由', async () => {
  let resolvePreflight!: (result:unknown) => void
  vi.mocked(api.post).mockResolvedValueOnce({version:'v1',records:[record]})
    .mockImplementationOnce(() => new Promise(resolve => {resolvePreflight = resolve}))
  render(<Editor />)
  const user = userEvent.setup()
  await screen.findByRole('button', {name:'压强 (GPa)'})
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  fireEvent.change(input, {target:{value:'0.003'}})
  await user.click(screen.getByRole('button', {name:'保存测试表单'}))
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
  fireEvent.change(input, {target:{value:'0.004'}})
  await user.click(screen.getByRole('button', {name:'压强 (GPa)'}))
  await user.type(screen.getByLabelText('人工核对理由'), '最新理由')
  await act(async () => resolvePreflight({version:'v2',records:[{...record,proposal_draft:{accepted:true,reason:'迟到旧理由',values:{}}}]}))
  expect(input).toHaveValue('0.004')
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('最新理由')
  expect(screen.getByRole('button', {name:'完成',exact:true})).toBeEnabled()
})

it('重新查找先保存，保存失败不会请求模型且保留理由', async () => {
  const {user,save} = reviewSetup(true)
  await screen.findByText(/压力 · 已接受/)
  fireEvent.change(screen.getAllByLabelText('压强 (GPa)')[0], {target:{value:'0.003'}})
  await user.click(await screen.findByRole('button', {name:'压强 (GPa)'}))
  await user.type(screen.getByLabelText('人工核对理由'), '仍然保留')
  await user.click(screen.getByRole('button', {name:'让系统重新查找',exact:true}))
  await screen.findByText(/当前编辑尚未保存成功/)
  expect(save).toHaveBeenCalledOnce()
  expect(api.post).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', {name:'取消',exact:true}))
  await user.click(await screen.findByRole('button', {name:'压强 (GPa)'}))
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('仍然保留')
})

it.each(['完成', '让系统重新查找'])('%s 等待队列时切换论文不会误保存新论文', async action => {
  let resolveProposal: (()=>void) | undefined
  vi.mocked(api.post).mockImplementation(async (path, body:any) => {
    if (path.endsWith('/preflight')) return {version:body.target_id,records:[record]}
    if (path.endsWith('/proposals')) return new Promise(resolve => {resolveProposal=()=>resolve({draft:body})})
    throw new Error(`意外请求 ${path}`)
  })
  const saveA = vi.fn().mockResolvedValue(true), saveB = vi.fn().mockResolvedValue(true)
  function Target({id,save}:{id:string;save:()=>Promise<boolean>}) {
    const flow = useEvidenceWorkflow({target:{target:'paper',target_id:id},saveCurrent:save,getCurrentValue:()=>({field:record.field,value:0.000101})})
    return <>{flow.dialog}<button onClick={()=>flow.openIssue(record.key)}>打开</button></>
  }
  const view = render(<Target id="A" save={saveA} />)
  const user = userEvent.setup()
  await waitFor(()=>expect(api.post).toHaveBeenCalledOnce())
  await user.click(screen.getByRole('button',{name:'打开'}))
  await user.type(screen.getByLabelText('人工核对理由'),'依据')
  fireEvent.click(screen.getByRole('button',{name:action,exact:true}))
  view.rerender(<Target id="B" save={saveB} />)
  await act(async()=>{resolveProposal?.()})
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/preflight',{target:'paper',target_id:'B'}))
  expect(saveA).not.toHaveBeenCalled()
  expect(saveB).not.toHaveBeenCalled()
})
