import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { TextField } from '@mui/material'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({api:{post:vi.fn(),get:vi.fn(),del:vi.fn()}}))
const record: EvidenceRecord = {key:'pressure',item_key:'pressure',field:'material_states[0].pressure_value_gpa',label:'压强',current_value:1,status:'uncertain',reason:'需确认',evidences:[]}
function Form() {
  const flow=useEvidenceWorkflow({target:{target:'paper',target_id:'fixture'}})
  return <div data-evidence-scope="drawer-close">
    {flow.dialog}
    <TextField label="压强" inputProps={{'data-issue-field':record.field}} defaultValue="1" />
    <button onClick={()=>flow.openIssue('other')}>另一个项目</button>
    <EvidenceFieldMarkers records={flow.records} scope="drawer-close" onOpen={flow.openIssue} />
  </div>
}
beforeEach(()=>{
  vi.useFakeTimers()
  vi.mocked(api.post).mockImplementation(async(path,body)=>path.endsWith('/preflight')?{version:'v1',records:[record],needs_check:true}:{draft:body})
})
afterEach(()=>{cleanup();vi.useRealTimers();vi.restoreAllMocks();vi.resetAllMocks()})
async function open() {
  await act(async()=>render(<Form />))
  const trigger=screen.getByRole('button',{name:'压强',exact:true})
  await act(async()=>fireEvent.click(trigger))
  await act(async()=>fireEvent.change(screen.getByLabelText('人工核对理由'),{target:{value:'已核验原始条件'}}))
  return trigger
}
async function exitTransition(){await act(async()=>vi.advanceTimersByTimeAsync(400))}

it('完成保存成功后自动关闭，重新打开仍可撤销接受',async()=>{
  await open()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  await exitTransition()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  const accepted=screen.getByRole('button',{name:/压强 · 已接受/})
  await act(async()=>fireEvent.click(accepted))
  expect(screen.getByRole('button',{name:'撤销接受并修改'})).toBeVisible()
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('已核验原始条件')
  expect(vi.mocked(api.post).mock.calls.some(([path])=>/jobs|review$/.test(path))).toBe(false)
})

it('关闭回到原字段并禁止焦点滚动，不跳到顶部已接受按钮',async()=>{
  await open()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  // 兼容旧行为以独立复现关闭后的错误焦点。
  const close=screen.queryByLabelText('关闭来源详情')
  if(close) await act(async()=>fireEvent.click(close))
  const focus=vi.spyOn(HTMLElement.prototype,'focus')
  await exitTransition()
  expect(screen.getByLabelText('压强')).toHaveFocus()
  expect(focus).toHaveBeenCalledWith({preventScroll:true})
  expect(screen.getByRole('button',{name:/压强 · 已接受/})).not.toHaveFocus()
})

it('保存失败保留抽屉和理由，重试成功才关闭',async()=>{
  await open()
  vi.mocked(api.post).mockRejectedValueOnce(new Error('保存暂不可用'))
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  await exitTransition()
  expect(screen.getByRole('dialog')).toBeVisible()
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('已核验原始条件')
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  await exitTransition()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('完成请求迟到不能关闭后来打开的另一个项目',async()=>{
  let resolve!: (value: unknown)=>void
  vi.mocked(api.post).mockImplementation(async(path,body:any)=>path.endsWith('/preflight')
    ? {version:'v1',needs_check:true,records:[record,{...record,key:'other',item_key:'other',field:'paper.note',label:'另一项'}]}
    : body.accepted ? await new Promise(r=>{resolve=r}) : {draft:body})
  await open()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  await act(async()=>fireEvent.click(screen.getByLabelText('关闭来源详情')))
  await exitTransition()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'另一个项目'})))
  await act(async()=>resolve({draft:{accepted:true,values:{},reason:'已核验原始条件'}}))
  await exitTransition()
  expect(screen.getByRole('dialog')).toHaveTextContent('另一项')
})

it('同框多个核对项全部保存成功才关闭',async()=>{
  let resolve!: (value: unknown)=>void
  vi.mocked(api.post).mockImplementation(async(path,body:any)=>path.endsWith('/preflight')
    ? {version:'v1',needs_check:true,records:[record,{...record,key:'pressure-source',item_key:'pressure-source'}]}
    : body.accepted && body.key==='pressure-source' ? await new Promise(r=>{resolve=r}) : {draft:body})
  await act(async()=>render(<Form />))
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'压强',exact:true})))
  for(const input of screen.getAllByLabelText('人工核对理由')) await act(async()=>fireEvent.change(input,{target:{value:'核对本项依据'}}))
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'完成',exact:true})))
  await exitTransition()
  expect(screen.getByRole('dialog')).toBeVisible()
  expect(screen.getByRole('button',{name:'完成',exact:true})).toBeDisabled()
  await act(async()=>resolve({draft:{accepted:true,values:{},reason:'核对本项依据'}}))
  await exitTransition()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
