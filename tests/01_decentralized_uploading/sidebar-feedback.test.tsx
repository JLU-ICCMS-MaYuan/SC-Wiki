import "@testing-library/jest-dom/vitest"
import React from "react"
import {act,render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react"
import {afterEach,it,expect,vi} from "vitest"
import ManualEvidenceSection from "../../frontend/src/components/ManualEvidenceSection"
import {api} from "../../frontend/src/lib/api"
import {createManualEvidenceDrafts,manualDraftKey} from "../../frontend/src/lib/manualEvidenceDrafts"
import FieldReviewFeedback from "../../frontend/src/components/FieldReviewFeedback"
import {createFieldDraftSaver} from "../../frontend/src/lib/fieldDrafts"
vi.mock("../../frontend/src/lib/api",()=>({api:{get:vi.fn(),post:vi.fn(),put:vi.fn(),patch:vi.fn(),del:vi.fn()}}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
const row={key:"title",item_key:"a".repeat(64),field:"paper.knowledge_graph_title",label:"图谱科学标题",current_value:"Original",status:"unsupported" as const,reason:"未通过",evidences:[]}
const saved={id:"stored",changed:true,status:"draft",reason:"原文概括",no_evidence_reason:"逻辑归纳",items:[],after_value:"Original"}
const target={target:"revision",target_id:"feedback"}
it("载入已保存资料即显示状态并禁用保存；修改后可保存、完成后恢复禁用",async()=>{
 vi.mocked(api.get).mockResolvedValue({data:saved} as never)
 vi.mocked(api.put).mockResolvedValue({data:{...saved,reason:"新的说明"}} as never)
 render(<ManualEvidenceSection record={row} target={target} version="v1"/>)
 await waitFor(()=>expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue(saved.reason))
 const button=screen.getByRole("button",{name:"保存",exact:true})
 expect(button).toBeDisabled();expect(screen.getByText("已保存")).toBeVisible()
 fireEvent.change(screen.getByLabelText("人工修改判断理由（必填）"),{target:{value:"新的说明"}})
 expect(button).toBeEnabled();fireEvent.click(button)
 await waitFor(()=>expect(api.put).toHaveBeenCalledTimes(1))
 await waitFor(()=>expect(button).toBeDisabled())
})
it("未保存新值不加载旧值的人工理由作为新依据",async()=>{
 vi.mocked(api.get).mockResolvedValue({data:saved} as never)
 render(<ManualEvidenceSection record={row} target={target} version="v1" value="Changed" localChanged valueDirty/>)
 await waitFor(()=>expect(screen.queryByText("正在读取人工修改记录…")).not.toBeInTheDocument())
 expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue("")
 expect(screen.queryByLabelText("不提供证据的理由（必填）")).not.toBeInTheDocument()
})
it("只读取当前字段保存基线，删除前项后按稳定身份判断，不扫描其他值",()=>{
 const saver=createFieldDraftSaver(target)
 saver.initialize({material_states:[{state_key:"a",pressure:1},{state_key:"b",pressure:2}]})
 expect(saver.hasFieldChanges({material_states:[{state_key:"b",pressure:2}]},"material_states[0].pressure")).toBe(false)
 expect(saver.hasFieldChanges({material_states:[{state_key:"b",pressure:3}]},"material_states[0].pressure")).toBe(true)
})

it("保存失败保留输入和可重试按钮；成功后改回保存值不再重复写入",async()=>{
 vi.mocked(api.get).mockResolvedValue({data:saved} as never)
 vi.mocked(api.put).mockRejectedValueOnce(new Error("隔离网络故障")).mockResolvedValue({data:{...saved,reason:"新说明"}} as never)
 render(<ManualEvidenceSection record={row} target={target} version="v1"/>)
 const input=await screen.findByLabelText("人工修改判断理由（必填）")
 await waitFor(()=>expect(input).toHaveValue(saved.reason))
 fireEvent.change(input,{target:{value:"新说明"}})
 const save=screen.getByRole("button",{name:"保存",exact:true});fireEvent.click(save)
 await screen.findByText(/隔离网络故障/)
 expect(save).toBeEnabled();expect(input).toHaveValue("新说明")
 fireEvent.click(save);await waitFor(()=>expect(save).toBeDisabled())
 fireEvent.change(input,{target:{value:"暂时修改"}});expect(save).toBeEnabled()
 fireEvent.change(input,{target:{value:"新说明"}});expect(save).toBeDisabled()
 expect(api.put).toHaveBeenCalledTimes(2)
})
it("保存期间新输入未被旧成功响应确认，仍需再次保存",async()=>{
 vi.mocked(api.get).mockResolvedValue({data:saved} as never)
 let release!:(v:any)=>void
 vi.mocked(api.put).mockImplementationOnce(()=>new Promise(resolve=>{release=resolve}))
 render(<ManualEvidenceSection record={row} target={target} version="v1"/>)
 const input=await screen.findByLabelText("人工修改判断理由（必填）")
 await waitFor(()=>expect(input).toHaveValue(saved.reason))
 fireEvent.change(input,{target:{value:"送出的说明"}})
 fireEvent.click(screen.getByRole("button",{name:"保存",exact:true}))
 await waitFor(()=>expect(api.put).toHaveBeenCalledTimes(1))
 fireEvent.change(input,{target:{value:"期间的新说明"}})
 await act(async()=>release({data:{...saved,reason:"送出的说明"}}))
 expect(input).toHaveValue("期间的新说明")
 expect(screen.getByRole("button",{name:"保存",exact:true})).toBeEnabled()
 expect(document.querySelector('[data-manual-save-state="unsaved"]')).toBeVisible()
})
it("附件部分成功只移除成功文件，剩余文件保留并允许重试",async()=>{
 const store=createManualEvidenceDrafts(),key=manualDraftKey(target,row,row.current_value)
 vi.mocked(api.get).mockResolvedValue({data:{...saved,no_evidence_reason:""}} as never)
 vi.mocked(api.put).mockResolvedValue({data:{...saved,no_evidence_reason:""}} as never)
 const a=new File(["a"],"a.txt"),b=new File(["b"],"b.txt")
 vi.mocked(api.post).mockResolvedValueOnce({data:{...saved,no_evidence_reason:"",items:[{id:"a",kind:"text_file",filename:"a.txt"}]}} as never).mockRejectedValueOnce(new Error("第二份文件失败"))
 render(<ManualEvidenceSection record={row} target={target} version="v1" drafts={store}/>)
 await waitFor(()=>expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue(saved.reason))
 act(()=>store.edit(key,{choice:"provide",files:[a,b]}))
 fireEvent.click(screen.getByRole("button",{name:"保存",exact:true}))
 await screen.findByText(/第二份文件失败/)
 expect(store.read(key).files).toEqual([b]);expect(store.read(key).saved?.items[0].id).toBe("a")
 expect(screen.getByRole("button",{name:"保存",exact:true})).toBeEnabled()
})
it("模型阶段只在进行中显示，完成后保留最终结论",()=>{
 const onCancel=vi.fn(),onRetry=vi.fn()
 const {rerender}=render(<FieldReviewFeedback record={row} progress={{phase:"running",elapsed:3,activity:{stage:"tool",message:"正在读取正文第2页",summary:"核实当前字段"},activity_log:[{stage:"model",message:"开始核对当前字段"}]}} onCancel={onCancel} onRetry={onRetry}/>)
 expect(screen.getByText("正在读取正文第2页")).toBeVisible();expect(screen.getByText(/核实当前字段/)).toBeVisible()
 rerender(<FieldReviewFeedback record={{...row,status:"supported",reason:"原文支持"}} onCancel={onCancel} onRetry={onRetry}/>)
 expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
 expect(screen.queryByText("正在读取正文第2页")).not.toBeInTheDocument()
 expect(screen.getByText("核对通过（结果已保存）")).toBeVisible()
})
