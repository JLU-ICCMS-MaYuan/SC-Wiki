import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import { evidenceFieldsForStates } from '../../frontend/src/lib/evidenceFields'

vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),put:vi.fn(),del:vi.fn(),download:vi.fn()}}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,username:'reviewer',role:'admin',is_admin:true,is_approved:true}})}))
vi.mock('../../frontend/src/components/StructureCandidatePanel',()=>({default:()=>null}))
vi.mock('../../frontend/src/lib/classifications',async original=>({...await original<any>(),loadClassificationCatalogs:async()=>({material_families:[{id:9,name:'氢基超导体'}],structure_families:[],material_dimensionalities:[{value:'unknown',name:'未知'}]})}))
const extensions=Array.from({length:20},(_,i)=>({field_key:`ext-${i}`,key:`cutoff_${i}`,name_raw:`条件 ${i}`,value_kind:'number',value_number:i,value_raw:String(i),unit_raw:'Ry'}))
const definition={definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',version:1,target_kind:'property_record',module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',method_code:'isotropic_eliashberg',core_schema:{},json_schema:{type:'object'},ui_schema:{},status:'published',checksum:'test'}
const record={...definition,record_key:'r',definition_version:1,name_raw:'Tc',value_kind:'number',value_number:311,value_raw:'311',unit_raw:'K',canonical_unit:'K',payload:{parameters:{lambda_ep:3.94,omega_log:745,mu_star:.1},calculation_conditions:{extensions}}}
const state={state_key:'s',material:'LaSc2H24',material_name:'LaSc2H24',pressure_value_gpa:150,state_kind:'theoretical',material_dimensionality:'unknown',structure_optimization:'unknown',crystal_system:'unknown',structure_families:[],schema_version:2,deleted_record_keys:[],deleted_module_keys:[],property_modules:[{module_key:'m',module_code:'superconductive_properties',definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[record]}]}
const paper={id:15,title:'LaSc2H24',year:2026,authors:[],paper_type:'theoretical',theoretical_subtype:'calculation',superconductor_kind:'conventional',material_families:[{id:9,name:'氢基超导体'}],review_status:'pending',doi:'10.9999/test',journal:'test'}
const draft={paper,material_states:[state],structure_candidates:[],field_evidence:{},classification_evidence:[]}
const prefix='material_states[0].property_modules[0].records[0].payload.calculation_conditions.extensions.'
const reviews=extensions.map((extension,i)=>({key:`review-${i}`,item_key:`review-${i}`,state_key:'s',module_key:'m',record_key:'r',record_field:`payload.calculation_conditions.extensions.${i}`,record_field_key:extension.field_key,field:prefix+i,fields:[prefix+i+'.value_raw'],label:extension.name_raw,owner_label:'LaSc2H24 · 150 GPa',required:true,status:'uncertain',stale:true,current_value:extension,reason:`来源说明 ${i}：科学值或来源已变化；原方法部分对条件 ${i} 的完整原文判断应只在对应侧栏显示。`,evidences:[{file_id:'main',page_start:5,quote:`Source for condition ${i}`}]}))
let currentReviews:any[]=reviews
beforeEach(()=>{
 currentReviews=structuredClone(reviews)
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path.includes('/form-definitions'))return (path.includes('?')?[definition]:definition)as never
  if(path.endsWith('/draft'))return {ok:true,data:structuredClone(draft)}as never
  if(path.includes('/manual/'))return {ok:true,data:{changed:false,reason:'',items:[],history:[]}}as never
  if(path==='/api/admin/papers/15')return {...paper,material_states:[structuredClone(state)],key_properties:[]}as never
  if(path.includes('space-groups'))return {space_groups:[]}as never
  return {items:[],jobs:[],total:0}as never
 })
 vi.mocked(api.put).mockResolvedValue({ok:true}as never)
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/revision-draft'))return {ok:true,data:structuredClone(draft),revision_id:'revision',draft_version:1}as never
  if(path.endsWith('/preflight'))return {version:'v',needs_check:false,records:structuredClone(currentReviews)}as never
  throw new Error(`Unexpected model/write: ${path}`)
 })
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})
async function show(mode='upload'){
 await act(async()=>render(mode==='admin'?<MemoryRouter initialEntries={['/admin/papers/15/edit']}><Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes></MemoryRouter>:<UploadTaskEditor taskId="test" revisionPaperId={mode==='revision'?15:undefined} onSubmitted={()=>{}}/>))
 fireEvent.click(await screen.findByRole('heading',{name:'超导性质',exact:true}))
 await screen.findByRole('button',{name:'待处理项（20）'})
}
it.each(['upload','revision','admin'])('%s 完整宿主不展开20条来源理由，侧栏仍保留完整说明与阻断',async mode=>{
 await show(mode)
 for(const item of reviews)expect(screen.queryByText(item.reason)).not.toBeInTheDocument()
 expect(screen.getByText('20 项待处理',{exact:true})).toBeVisible()
 const field=screen.getByRole('button',{name:'设置字段：条件 6',exact:true}).closest('[data-scientific-field]')!
 await waitFor(()=>expect(field).toHaveAttribute('data-evidence-problem','true'))
 fireEvent.click(screen.getByRole('button',{name:'设置字段：条件 6',exact:true}))
 const drawer=document.querySelector('.evidence-review-drawer')as HTMLElement
 fireEvent.click(within(drawer).getByRole('tab',{name:'来源核对'}))
 const reason=await within(drawer).findByText(reviews[6].reason)
 expect(reason).toBeVisible();expect(reason.closest('[role="alert"]')).toBeNull()
 expect(within(drawer).getByText('待重新核对')).toBeVisible()
 expect(within(drawer).getByText(/Source for condition 6/)).toBeVisible()
 expect(within(drawer).queryByText(reviews[5].reason)).not.toBeInTheDocument()
 expect(within(drawer).getByRole('button',{name:'完成',exact:true})).toBeDisabled()
 expect(vi.mocked(api.put)).not.toHaveBeenCalled()
})
it('非法数值仍就地显示，来源理由不会混进校验辅助文本',async()=>{
 await show()
 fireEvent.change(screen.getByRole('textbox',{name:'电声耦合强度 λ',exact:true}),{target:{value:'-1'}})
 expect(await screen.findByText('请输入完整的非负数值')).toBeVisible()
 for(const item of reviews)expect(screen.queryByText(item.reason)).not.toBeInTheDocument()
})
it('未定位来源项保留独立入口和问题数，不生成正文警告',async()=>{
 currentReviews=[{...reviews[0],key:'not-rendered',record_key:'not-rendered',label:'未定位字段'}]
 await act(async()=>render(<UploadTaskEditor taskId="test" onSubmitted={()=>{}}/>))
 await screen.findByRole('button',{name:'待处理项（1）'})
 expect(screen.queryByText(reviews[0].reason)).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'待处理项（1）'}))
 fireEvent.click(screen.getByRole('button',{name:/未定位字段/}))
 const drawer=document.querySelector('.evidence-review-drawer')as HTMLElement
 expect(await within(drawer).findByText(reviews[0].reason)).toBeVisible()
})
it('真实保存错误继续提示，来源说明不会因此回到主表单',async()=>{
 await show()
 fireEvent.change(screen.getByRole('textbox',{name:'Tc',exact:true}),{target:{value:'312'}})
 vi.mocked(api.put).mockRejectedValueOnce(Object.assign(new Error('save failed'),{detail:{message:'本次保存失败，请重试'}}))
 fireEvent.click(screen.getByRole('button',{name:'立即保存',exact:true}))
 expect(await screen.findByText(/本次保存失败，请重试/)).toBeVisible()
 for(const item of reviews)expect(screen.queryByText(item.reason)).not.toBeInTheDocument()
})
it('只读表单仍可从key进入侧栏查看，设置不提供写入操作',async()=>{
 await act(async()=>render(<UploadTaskEditor taskId="test" draftOverride={draft as any} readOnly onSubmitted={()=>{}}/>))
 fireEvent.click(await screen.findByRole('heading',{name:'超导性质',exact:true}))
 fireEvent.click(await screen.findByRole('button',{name:'设置字段：条件 6',exact:true}))
 const drawer=document.querySelector('.evidence-review-drawer')as HTMLElement
 expect(await within(drawer).findByLabelText('字段名称（key）')).toBeDisabled()
 expect(within(drawer).queryByRole('button',{name:'应用修改'})).not.toBeInTheDocument()
 fireEvent.click(within(drawer).getByRole('tab',{name:'来源核对'}))
 expect(within(drawer).getByText('系统找到的原文',{selector:'summary'})).toBeVisible()
 expect(vi.mocked(api.put)).not.toHaveBeenCalled()
})
it('计数路径按稳定身份随状态和记录重排，不传递来源理由',()=>{
 const states=[{state_key:'other',property_modules:[]},{...state,property_modules:[{...state.property_modules[0],records:[{...record,record_key:'other'},record]}]}]
 expect(evidenceFieldsForStates([reviews[6]]as any,states)).toEqual(['material_states[1].property_modules[0].records[1].payload.calculation_conditions.extensions.6'])
})
