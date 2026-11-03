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
let sourceOverrides:any = {}
const item='a'.repeat(64)
const field='material_states[0].property_modules[0].records[0].payload.parameters.mu_star'
let draft:any,manual:any,order:string[],finishJob:(value:any)=>void,poll:Promise<any>,failSave=false
const record=()=>({key:item,item_key:item,field,fields:[field],label:'μ*',state_key:'s',module_key:'m',record_key:'r',
 record_field:'payload.parameters.mu_star',current_value:draft.material_states[0].property_modules[0].records[0].payload.parameters.mu_star,
 status:'uncertain',reason:'需核对',evidences:[],human_modified:true,required:true,...sourceOverrides})
beforeEach(()=>{
 sourceOverrides={};failSave=false;order=[];manual={changed:true,reason:'',no_evidence_reason:'',items:[]}
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
 poll=new Promise(resolve=>{finishJob=resolve})
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path==='/api/admin/papers/177')return {...draft.paper,material_states:structuredClone(draft.material_states)} as never
  if(path.includes('/classification-catalogs'))return {material_families:[],structure_families:[],material_dimensionalities:[]} as never
  if(path.includes('/form-definitions?'))return defs as never
  if(path.includes('/form-definitions/'))return defs.find(d=>path.includes(d.definition_key)) as never
  if(path.includes('/draft-state'))return {version:'draft-before',draft:structuredClone(draft),staged:false} as never
  if(path.endsWith('/draft'))return {data:structuredClone(draft)} as never
  if(path.includes('/field-detail'))return {record:record(),review_token:'review',approval_state:'modification_required',source_state:'empty'} as never
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

async function open(kind:string){
 auth.role=kind==='superadmin'?'superadmin':'admin'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/177/edit']}>
  {['admin','superadmin'].includes(kind)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
   :<UploadTaskEditor taskId="task177" revisionPaperId={kind==='revision'?177:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Original title')
 fireEvent.change(screen.getByDisplayValue('Original title'),{target:{value:'Local title'}})
 fireEvent.click(screen.getAllByText('超导性质').find(n=>n.closest('[data-property-module-toggle]'))!)
 await screen.findByLabelText('μ*')
 fireEvent.change(screen.getByLabelText('μ*'),{target:{value:'0.12'}})
 await waitFor(()=>expect(document.querySelector(`[data-evidence-key="${item}"]`)).not.toBeNull())
 fireEvent.click(document.querySelector(`[data-evidence-key="${item}"]`)!)
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
 const overlay=screen.getByRole('progressbar').closest('[role="dialog"]')!
 expect(overlay).toBeVisible()
 await act(async()=>finishJob({id:'job',status:'completed',records:[{...record(),status:'supported',pending_review:false,stale:false}]}))
 await screen.findByText('核对通过，结果已保存；内容和依据不变时，提交将直接复用。')
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
