import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import defs from '../fixtures/issue176/form-definitions.json'

const auth=vi.hoisted(()=>({role:'admin'}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:auth.role,is_admin:true,is_approved:true}})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),patch:vi.fn(),put:vi.fn(),del:vi.fn()}}))
let sourceOverrides:any = {},detailOverrides:any = {}
const item='a'.repeat(64)
const field='material_states[0].property_modules[0].records[0].payload.parameters.mu_star'
let draft:any,manual:any,order:string[],finishJob:(value:any)=>void,poll:Promise<any>,failSave=false
const record=()=>({key:item,item_key:item,field,fields:[field],label:'μ*',state_key:'s',module_key:'m',record_key:'r',
 record_field:'payload.parameters.mu_star',current_value:draft.material_states[0].property_modules[0].records[0].payload.parameters.mu_star,
 status:'uncertain',reason:'需核对',evidences:[],human_modified:true,required:true,...sourceOverrides})
beforeEach(()=>{
 vi.mocked(api.del).mockResolvedValue({status:'cancelled'} as never)
 sourceOverrides={};detailOverrides={};failSave=false;order=[];manual={changed:true,reason:'',no_evidence_reason:'',items:[]}
 draft={paper:{id:177,title:'Original title',authors:[],year:2026,paper_type:'theoretical',
  material_families:[],review_status:'pending',uploaded_by_user_id:8},
 material_states:[{id:1,state_key:'s',material:'CaH6',material_name:'CaH6',state_kind:'theoretical',pressure_value_gpa:150,
  structure_optimization:'classical_static',crystal_system:'cubic',element_count:2,
  material_dimensionality:'three_dimensional',superconductor:{chemical_formula:'CaH6'},
  property_modules:[{module_key:'m',module_code:'superconductive_properties',
   definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[{
    record_key:'r',module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',
    definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version:1,
    method_code:'isotropic_eliashberg',name_raw:'Tc',value_kind:'number',value_number:220,value_raw:'220 K',unit_raw:'K',
    payload:{parameters:{lambda_ep:2.69,mu_star:.13},calculation_conditions:{},
     tc_group:{version:1,group_key:'g',method_key:'method',point_key:'r'}},
   }]}]}],structure_candidates:[]}
 poll=new Promise(resolve=>{finishJob=value=>{if(value.status==='completed'&&value.records?.[0])sourceOverrides={...sourceOverrides,...value.records[0]};resolve(value)}})
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path==='/api/admin/papers/177')return {...draft.paper,material_states:structuredClone(draft.material_states)} as never
  if(path.includes('/classification-catalogs'))return {material_families:[],structure_families:[],material_dimensionalities:[]} as never
  if(path.includes('/form-definitions?'))return defs as never
  if(path.includes('/form-definitions/'))return defs.find(d=>path.includes(d.definition_key)) as never
  if(path.includes('/draft-state'))return {version:'draft-before',draft:structuredClone(draft),staged:false} as never
  if(path.endsWith('/draft'))return {data:structuredClone(draft)} as never
  if(path.includes('/field-detail'))return {record:{...record(),...detailOverrides},review_token:'review',approval_state:'modification_required',source_state:'empty'} as never
  if(path.includes('/manual-context'))return {version:'manual-field-v1:fixture',record:record()} as never
  if(path.includes('/manual/'))return {data:manual} as never
  if(path.includes('/field-input')){
   // 模拟保存联动的同值输入通知；不是等待期间用户编辑背景。
   fireEvent.input(screen.getByDisplayValue('Local title'),{target:{value:'Local title'}})
   order.push('field-input');return {field_token:'field-only',version:'field-only',records:[record()],needs_check:true} as never}
  if(path.includes('/jobs/'))return poll
  return {data:{},items:[],jobs:[],space_groups:[]} as never
 })
 vi.mocked(api.post).mockImplementation(async(path,body:any)=>{
  if(path.endsWith('/summary'))return {version:'old-global',records:[record()],needs_check:false} as never
  if(path.endsWith('/jobs')){
   order.push('job')
   expect(body.retry_keys).toEqual([item]);expect(body.expected_field_token).toBe('field-only')
   expect(body).not.toHaveProperty('expected_draft_version')
   expect(manual.reason).toBe('最新人工理由');expect(manual.no_evidence_reason).toBe('沿用原文')
   return {id:'job',status:'queued',timeout_seconds:60} as never
  }
  return {data:structuredClone(draft),revision_id:'revision177',draft_version:1} as never
 })
 vi.mocked(api.patch).mockImplementation(async(_path,body:any)=>{
  order.push('value-save')
  if(failSave)throw new Error('network save failed')
  expect(body.field_scope).toBe(true)
  expect(body.changes).toHaveLength(1)
  expect(body.changes[0].path.at(-1)).toBe('mu_star')
  draft.material_states[0].property_modules[0].records[0].payload.parameters.mu_star=body.changes[0].value
  return {version:'changed-global',changed:true,draft_version:2} as never
 })
 vi.mocked(api.put).mockImplementation(async(_path,body:any)=>{
  order.push('manual-save')
  expect(record().current_value).toBe(.12)
  manual={...manual,...body}
  return {data:manual} as never
 })
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})

it.each(['admin','superadmin'])('%s 恢复不含程序身份的审核工作稿仍显示整稿，当前空值不回退正式缓存',async role=>{
 auth.role=role
 delete draft.paper.id
 delete draft.paper.review_status
 delete draft.paper.uploaded_by_user_id
 draft.paper.title='Saved working title'
 draft.paper.summary=null
 const original=vi.mocked(api.get).getMockImplementation()!
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path==='/api/admin/papers/177')return {...structuredClone(draft.paper),id:177,
   title:'Formal cached title',summary:'Old summary',review_status:'pending',created_at:'2026-11-05T00:00:00Z',
   material_states:structuredClone(draft.material_states)} as never
  if(path.includes('/draft-state'))return {version:'staged-current',draft:structuredClone(draft),staged:true} as never
  return original(path)
 })
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/177/edit']}>
  <Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
 </MemoryRouter></LanguageProvider>)
 expect(await screen.findByDisplayValue('Saved working title')).toBeVisible()
 expect(screen.getByText('ID: 177')).toBeVisible()
 expect(screen.getByText(/^创建:/)).toHaveTextContent('2026')
 expect(document.querySelector('[data-issue-field="paper.summary"] textarea')).toHaveValue('')
 expect(vi.mocked(api.patch)).not.toHaveBeenCalled()
 expect(vi.mocked(api.put)).not.toHaveBeenCalled()
})

async function open(kind:string,edit=true){
 auth.role=kind==='superadmin'?'superadmin':'admin'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/177/edit']}>
  {['admin','superadmin'].includes(kind)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
   :<UploadTaskEditor taskId="task177" revisionPaperId={kind==='revision'?177:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Original title')
 if(edit)fireEvent.change(screen.getByDisplayValue('Original title'),{target:{value:'Local title'}})
 fireEvent.click(screen.getAllByText('超导性质').find(n=>n.closest('[data-property-module-toggle]'))!)
 await screen.findByLabelText('μ*')
 if(edit)fireEvent.change(screen.getByLabelText('μ*'),{target:{value:'0.12'}})
 await waitFor(()=>expect(document.querySelector(`[data-evidence-key="${item}"]`)).not.toBeNull())
 fireEvent.click(document.querySelector(`[data-evidence-key="${item}"]`)!)
 await screen.findByLabelText('人工修改判断理由（必填）')
 if(!edit)return
 fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'),{target:{value:'最新人工理由'}})
 fireEvent.click(screen.getByLabelText('不提供证据'))
 fireEvent.change(screen.getByLabelText('不提供证据的理由（必填）'),{target:{value:'沿用原文'}})
}

it.each(['upload','revision','admin','superadmin'])('%s 单字段自动保存最新依据、只排一个任务并隔离返回',async kind=>{
 await open(kind)
 fireEvent.click(screen.getByRole('button',{name:'大模型核对',exact:true}))
 await waitFor(()=>expect(order).toContain('job'))
 expect(order).toEqual(['value-save','manual-save','field-input','job'])
 expect(draft.paper.title).toBe('Original title')
 expect(screen.getByRole('progressbar')).toBeVisible()
 expect(screen.queryByText('正在保存当前字段及人工依据…')).not.toBeInTheDocument()
 const overlay=screen.getByRole('progressbar').closest('.evidence-review-drawer')!
 expect(overlay).toBeVisible()
 expect(document.querySelector('[aria-labelledby="evidence-workflow-title"]')).toBeNull()
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toBeDisabled()
 await act(async()=>finishJob({id:'job',status:'completed',records:[{...record(),status:'supported',pending_review:false,stale:false}]}))
 await screen.findByText('核对通过（结果已保存）')
 await waitFor(()=>expect(document.querySelector(`[data-evidence-key="${item}"]`)).toHaveAttribute('data-evidence-status','passed'))
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith('/jobs'))).toHaveLength(1)
 expect(vi.mocked(api.patch).mock.calls).toHaveLength(1)
 expect(screen.getByDisplayValue('Local title')).toBeInTheDocument()
})

it('保存失败保留最新理由且不启动模型任务',async()=>{
 await open('upload');failSave=true
 fireEvent.click(screen.getByRole('button',{name:'大模型核对',exact:true}))
 await waitFor(()=>expect(within(document.querySelector('.evidence-review-drawer')! as HTMLElement)
  .getAllByText(/保存失败，尚未开始核对/).at(-1)).toBeVisible())
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('最新人工理由')
 expect(order).toEqual(['value-save'])
 expect(api.put).not.toHaveBeenCalled()
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs'))).toBe(false)
})

it.each(['upload','revision','admin','superadmin'])('%s 技术失败落在原字段，不隐藏成无问题',async kind=>{
 await open(kind)
 fireEvent.click(screen.getByRole('button',{name:'大模型核对',exact:true}))
 await waitFor(()=>expect(order).toContain('job'))
 await act(async()=>finishJob({id:'job',status:'failed',error:{code:'evidence_model_timeout',message:'隔离模型超时，请重试当前字段'}}))
 await screen.findByText('隔离模型超时，请重试当前字段')
 await waitFor(()=>expect(document.querySelector(`[data-evidence-key="${item}"]`)).toHaveAttribute('data-evidence-status','failed'))
 expect(document.querySelector('[data-evidence-pending-navigation]')).toBeNull()
})

it.each(['upload','revision','admin','superadmin'])('%s 原文区只显示当前字段相关依据且不显示整包兜底与信息框',async kind=>{
 sourceOverrides={stale:true,pending_review:true,reason:'当前字段的独立核对理由',
  evidences:[],legacy_evidences:[{file_id:'main',quote:'Unrelated Tc and cutoff paragraph'}]}
 await open(kind)
 const drawer=document.querySelector('.evidence-review-drawer') as HTMLElement
 const source=within(drawer).getByText('系统找到的原文',{selector:'summary'}).parentElement!
 expect(within(source).queryByText(/Unrelated Tc and cutoff paragraph/)).not.toBeInTheDocument()
 expect(within(source).queryByText(/旧整条记录原文/)).not.toBeInTheDocument()
 expect(source.querySelector('[data-evidence-review-summary]')).toBeNull()
 expect(drawer.querySelector('.MuiAlert-standardInfo')).toBeNull()
 expect(within(drawer).getByText('当前字段的独立核对理由',{exact:true})).toBeVisible()
 expect(within(drawer).getByRole('button',{name:'大模型核对',exact:true})).toBeVisible()
 expect(within(drawer).getByRole('button',{name:'人工审核通过',exact:true})).toBeVisible()
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith('/jobs'))).toHaveLength(0)
})

it.each(["upload","revision","admin","superadmin"])("221 %s 取消侧栏核对后解锁，迟到结果不覆盖，人工输入保留",async kind=>{
 await open(kind)
 fireEvent.click(screen.getByRole("button",{name:"大模型核对",exact:true}))
 await waitFor(()=>expect(order).toContain("job"))
 const side=document.querySelector(".evidence-review-drawer") as HTMLElement
 fireEvent.click(within(side).getByRole("button",{name:"取消",exact:true}))
 expect(await screen.findByText("本次核对已取消，输入已保留。")).toBeVisible()
 expect(screen.getByLabelText("人工修改判断理由（必填）")).toBeEnabled()
 expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue("最新人工理由")
 await act(async()=>finishJob({id:"job",status:"completed",records:[{...record(),status:"supported",pending_review:false}]}))
 expect(screen.queryByText("核对通过（结果已保存）")).not.toBeInTheDocument()
 expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue("最新人工理由")
 expect(api.del).toHaveBeenCalledWith("/api/rag/evidence/jobs/job")
})

it.each(["upload","revision","admin","superadmin"])("221 %s 保存状态：全部保存后禁用，再次实际编辑恢复，不启动模型",async kind=>{
 await open(kind)
 const save=screen.getByRole("button",{name:"保存",exact:true})
 fireEvent.click(save)
 await waitFor(()=>expect(order).toContain("manual-save"))
 await waitFor(()=>expect(save).toBeDisabled())
 expect(screen.getByText("已保存")).toBeVisible()
 fireEvent.change(screen.getByLabelText("人工修改判断理由（必填）"),{target:{value:"新的人工判断理由"}})
 expect(save).toBeEnabled()
 fireEvent.click(save)
 await waitFor(()=>expect(save).toBeDisabled())
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith("/jobs"))).toHaveLength(0)
})
it.each(["upload","revision","admin","superadmin"])("221 %s 核对未通过：侧栏显示具体理由、保留人工资料，不弹中央框",async kind=>{
 await open(kind)
 fireEvent.click(screen.getByRole("button",{name:"大模型核对",exact:true}))
 await waitFor(()=>expect(order).toContain("job"))
 expect(document.querySelector(".evidence-review-drawer")).toBeVisible()
 expect(document.querySelector('[aria-labelledby="evidence-workflow-title"]')).toBeNull()
 const reason="原文只支持μ*=0.13，不支持当前0.12，请核查当前结果配对。"
 await act(async()=>finishJob({id:"job",status:"completed",records:[{...record(),status:"unsupported",pending_review:true,stale:false,reason,ai_reason:reason}]}))
 expect(await screen.findByText("核对未通过（结果已保存）")).toBeVisible()
 expect(screen.getByText(reason)).toBeVisible()
 expect(document.querySelector(`[data-evidence-key="${item}"]`)).toHaveAttribute("data-evidence-status","attention")
 expect(screen.getByLabelText("人工修改判断理由（必填）")).toHaveValue("最新人工理由")
 expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
 expect(document.querySelector('[aria-labelledby="evidence-workflow-title"]')).toBeNull()
})

it.each(['upload','revision','admin','superadmin'])('%s 相关反证的长原文直接可读，不再内嵌展开标签',async kind=>{
 const quote=('The reported mu-star is 0.13 for this result. ').repeat(16)
 sourceOverrides={status:'unsupported',reason:'原文不支持当前配对',
  source_associations:[{target_path:'payload.parameters.mu_star',stage:'superconductivity',basis_kind:'paper_quote',explanation:'当前结果的适用范围',fact_evidences:[],scope_evidences:[]}],evidences:[{file_id:'main',source_name:'正文',quote}],legacy_evidences:[{file_id:'si',quote:'Unrelated record source'}]}
 await open(kind)
 const drawer=document.querySelector('.evidence-review-drawer') as HTMLElement
 const source=within(drawer).getByText('系统找到的原文',{selector:'summary'}).parentElement!
 expect(source).toHaveTextContent(quote.trim())
 expect(source.querySelector('details')).toBeNull()
 expect(within(source).queryByText(/Unrelated record source/)).not.toBeInTheDocument()
 expect(within(drawer).getByText('原文不支持当前配对',{exact:true})).toBeVisible()
 expect(drawer.querySelector('.MuiAlert-standardInfo')).toBeNull()
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith('/jobs'))).toHaveLength(0)
})


it.each(['upload','revision','admin','superadmin'])('221 %s 重开详情通过覆盖旧摘要待核对，未保存新值仍提醒',async kind=>{
 sourceOverrides={status:'supported',pending_review:true,human_modified:true}
 detailOverrides={pending_review:false,stale:false}
 await open(kind,false)
 expect(await screen.findByText('核对通过（结果已保存）')).toBeVisible()
 fireEvent.click(screen.getByLabelText('关闭来源详情'))
 await waitFor(()=>expect(document.querySelector('.evidence-review-drawer')).toBeNull())
 fireEvent.change(screen.getByLabelText('μ*'),{target:{value:'0.12'}})
 fireEvent.click(document.querySelector(`[data-evidence-key="${item}"]`)!)
 expect(await screen.findByText('当前版本待核对')).toBeVisible()
 await waitFor(()=>expect(screen.queryByText('核对通过（结果已保存）')).not.toBeInTheDocument())
})
