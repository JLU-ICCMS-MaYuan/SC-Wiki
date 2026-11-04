import "@testing-library/jest-dom/vitest"
import React from "react"
import {act,cleanup,render,waitFor,fireEvent,screen} from "@testing-library/react"
import {afterEach,expect,it,vi} from "vitest"
import {useEvidenceWorkflow,type EvidenceRecord} from "../../frontend/src/components/EvidenceWorkflow"
import {evidenceProblem} from "../../frontend/src/components/EvidenceFieldMarkers"
import {evidenceStatus} from "../../frontend/src/lib/evidenceStatus"
import {createManualEvidenceDrafts,manualDraftKey} from "../../frontend/src/lib/manualEvidenceDrafts"
import {api} from "../../frontend/src/lib/api"
import EvidenceFieldMarkers from "../../frontend/src/components/EvidenceFieldMarkers"
import {TextField} from "@mui/material"
vi.mock("../../frontend/src/lib/api",()=>({api:{get:vi.fn(),post:vi.fn(),put:vi.fn(),patch:vi.fn(),del:vi.fn()}}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
const base:EvidenceRecord={key:"method",item_key:"method",field:"paper.title",label:"预测方法",current_value:"unknown",required:false,status:"unchecked",human_modified:false,evidences:[],reason:""}
it.each([false,true])("原免审=%s：实际改值红，恢复值不制造通过，保存和迟到摘要不能消红",async optional=>{
  const row={...base,required:!optional,status:optional?"unchecked":"supported"} as EvidenceRecord
  let value="unknown",flow:ReturnType<typeof useEvidenceWorkflow>
  vi.mocked(api.post).mockResolvedValue({version:"v1",records:[row],needs_check:false})
  function Host(){flow=useEvidenceWorkflow({target:{target:"revision",target_id:"isolated"},getCurrentValue:r=>({field:r.field,value})});return null}
  render(<Host/>);await waitFor(()=>expect(flow.records).toHaveLength(1))
  const edit=async(next:string)=>act(async()=>{value=next;flow.invalidate(row.field);await new Promise(r=>setTimeout(r,10))})
  await edit("isotropic_eliashberg")
  expect(evidenceProblem(flow.records[0])).toBe(true)
  await act(async()=>{await flow.refreshAfterSave(flow.getEditRevision())})
  expect(evidenceProblem(flow.records[0])).toBe(true)
  await edit("unknown")
  expect(evidenceProblem(flow.records[0])).toBe(false)
  expect(flow.records[0].status).toBe(row.status)
  expect(api.post).toHaveBeenCalledTimes(1)
})
it("处理中不抹掉旧问题；原通过主动查询不制造红框",()=>{
  expect(evidenceStatus({...base,required:true,review_in_progress:true})).toBe("processing")
  expect(evidenceProblem({...base,required:true,review_in_progress:true})).toBe(true)
  expect(evidenceProblem({...base,status:"supported",review_in_progress:true})).toBe(false)
})
it("未改免审空项保持正常，本地改动和人工资料待保存独立于旧免审",()=>{
  expect(evidenceProblem({...base,pending_review:true})).toBe(false)
  expect(evidenceProblem({...base,local_modified:true} as EvidenceRecord)).toBe(true)
  expect(evidenceProblem({...base,manual_pending:true} as EvidenceRecord)).toBe(true)
})
it("原空项输入后清空，null 与空文本按既有等价规则恢复免审",async()=>{
  let value="",flow:ReturnType<typeof useEvidenceWorkflow>
  vi.mocked(api.post).mockResolvedValue({version:"v1",records:[{...base,current_value:null}],needs_check:false})
  function Host(){flow=useEvidenceWorkflow({target:{target:"revision",target_id:"empty"},getCurrentValue:r=>({field:r.field,value})});return null}
  render(<Host/>);await waitFor(()=>expect(flow.records).toHaveLength(1))
  await act(async()=>{value="filled";flow.invalidate(base.field);await new Promise(r=>setTimeout(r,10))})
  expect(evidenceProblem(flow.records[0])).toBe(true)
  await act(async()=>{value="";flow.invalidate(base.field);await new Promise(r=>setTimeout(r,10))})
  expect(evidenceProblem(flow.records[0])).toBe(false)
})
it("人工草稿快照按字段稳定身份汇总，逐字修改不改变待处理成员",()=>{
  const store=createManualEvidenceDrafts(),target={target:"revision",target_id:"220"}
  const key=manualDraftKey(target,base,"old")
  const read=()=>store.pendingFieldSignature()
  expect(read()).toBe("[]")
  store.edit(key,{reason:"a"});const first=read()
  store.edit(key,{reason:"ab"});expect(read()).toBe(first)
  store.edit(manualDraftKey(target,base,"new"),{reason:"new"});expect(read()).toBe(first)
  store.discard(key);expect(read()).toBe(first)
  store.discard(manualDraftKey(target,base,"new"));expect(read()).toBe("[]")
})

it("人工说明未保存归到本字段，连续理由输入不重绘宿主，提交定位并保留输入",async()=>{
  const row={...base,item_key:"a".repeat(64),status:"supported",required:true,human_modified:true,current_value:"old"} as EvidenceRecord
  let flow:ReturnType<typeof useEvidenceWorkflow>,renders=0
  const target={target:"revision",target_id:"220"}
  const read=vi.fn(r=>({field:r.field,value:"old"}))
  vi.mocked(api.post).mockResolvedValue({version:"v1",records:[row],needs_check:false})
  vi.mocked(api.get).mockImplementation(async path=>path.includes("/field-detail")?{record:row,review_token:"token",approval_state:"supported",source_state:"empty"} as never:{data:{changed:true,reason:"",no_evidence_reason:"",items:[]}} as never)
  function Host(){renders++;flow=useEvidenceWorkflow({target,getCurrentValue:read,saveCurrent:async()=>true});return <><button onClick={()=>flow.openIssue(row.key)}>打开</button>{flow.dialog}</>}
  render(<Host/>);await waitFor(()=>expect(flow.records).toHaveLength(1))
  expect(evidenceProblem(flow.records[0])).toBe(false)
  fireEvent.click(screen.getByText("打开"))
  const input=await screen.findByLabelText("人工修改判断理由（必填）")
  fireEvent.change(input,{target:{value:"a"}})
  await waitFor(()=>expect(evidenceProblem(flow.records[0])).toBe(true))
  const count=renders;read.mockClear()
  fireEvent.change(input,{target:{value:"ab"}})
  fireEvent.change(input,{target:{value:"abc"}})
  expect(renders).toBe(count);expect(read).not.toHaveBeenCalled()
  fireEvent.click(screen.getByLabelText("关闭来源详情"))
  await act(async()=>{await flow.gate(target)})
  expect(await screen.findByLabelText("人工修改判断理由（必填）")).toHaveValue("abc")
  expect(flow.saveError).toContain("预测方法")
  expect(vi.mocked(api.post).mock.calls.filter(([path])=>/jobs|submit-check/.test(path))).toHaveLength(0)
})

it("当前版本通过结果消红，再次编辑重新红；输入本身不发起审核",async()=>{
  let value="unknown",flow:ReturnType<typeof useEvidenceWorkflow>
  const target={target:"revision",target_id:"current"}
  vi.mocked(api.post).mockImplementation(async path=>path.endsWith("/summary")
    ? {version:"v1",records:[base],needs_check:false} as never
    : {id:"completed",status:"completed",version:"v2",records:[{...base,current_value:"isotropic_eliashberg",required:true,status:"supported"}]} as never)
  function Host(){flow=useEvidenceWorkflow({target,getCurrentValue:r=>({field:r.field,value})});return null}
  render(<Host/>);await waitFor(()=>expect(flow.records).toHaveLength(1))
  await act(async()=>{value="isotropic_eliashberg";flow.invalidate(base.field);await new Promise(r=>setTimeout(r,10))})
  expect(evidenceProblem(flow.records[0])).toBe(true)
  expect(api.post).toHaveBeenCalledTimes(1)
  await act(async()=>{await flow.gate(target)})
  expect(evidenceProblem(flow.records[0])).toBe(false)
  await act(async()=>{value="anisotropic_eliashberg";flow.invalidate(base.field);await new Promise(r=>setTimeout(r,10))})
  expect(evidenceProblem(flow.records[0])).toBe(true)
})

it("同一控件的多个问题必须分别解除，任一子项存疑仍保留红框",async()=>{
  const passed={...base,required:true,status:"supported"} as EvidenceRecord
  const form=(records:EvidenceRecord[])=><div data-evidence-scope="multiple"><TextField label="方法" data-issue-field="paper.title"/>
    <EvidenceFieldMarkers scope="multiple" records={records} onOpen={()=>{}} onChange={()=>{}}/></div>
  const view=render(form([passed,{...passed,key:"unit",status:"uncertain"}]))
  const field=await screen.findByRole('button',{name:'方法'})
  await waitFor(()=>expect(field).toHaveAttribute("data-evidence-caption-problem","true"))
  view.rerender(form([{...passed,status:"unsupported"},{...passed,key:"unit"}]))
  expect(field).toHaveAttribute("data-evidence-caption-problem","true")
  view.rerender(form([passed,{...passed,key:"unit"}]))
  await waitFor(()=>expect(field).toHaveAttribute("data-evidence-caption-problem","false"))
})
