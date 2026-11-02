import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import EvidenceFieldMarkers, { evidenceProblem } from '../../frontend/src/components/EvidenceFieldMarkers'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import defs from '../fixtures/issue176/form-definitions.json'

const auth=vi.hoisted(()=>({role:'admin'}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:auth.role,is_admin:true,is_approved:true}})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),patch:vi.fn(),put:vi.fn(),del:vi.fn()}}))
const prefix='material_states[0].property_modules[0].records[0]'
const ext=prefix+'.payload.calculation_conditions.extensions.0'
let draft:any, records:any[]
beforeEach(()=>{
 draft={paper:{id:201,title:'Ownership paper',year:2026,authors:[],paper_type:'theoretical',material_families:[],review_status:'pending',uploaded_by_user_id:8},
 material_states:[{id:1,state_key:'s',material:'CaH6',material_name:'CaH6',state_kind:'theoretical',pressure_value_gpa:150,
  structure_optimization:'classical_static',crystal_system:'cubic',element_count:2,material_dimensionality:'three_dimensional',
  structure_families:[],superconductor:{chemical_formula:'CaH6'},property_modules:[{module_key:'m',module_code:'superconductive_properties',
   definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[{record_key:'r',module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',
    definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version:1,method_code:'isotropic_eliashberg',
    name_raw:'Tc',value_kind:'number',value_number:220,value_raw:'220',unit_raw:'K',canonical_unit:'K',payload:{parameters:{lambda_ep:2.69,mu_star:.13},
     calculation_conditions:{method_scope:{stage:'epc',physical_object:'electron_phonon'},extensions:[{field_key:'phonon',key:'electron_phonon.phonon_method',name_raw:'声子方法',value_kind:'text',value_raw:'DFPT',value_text:'DFPT',unit_raw:'1'}]},
     tc_group:{version:1,group_key:'g',method_key:'method',point_key:'r'}}}]}]}],structure_candidates:[]}
 const parts=[['raw','value_raw','原始值','DFPT'],['name','name_raw','名称','声子方法'],['kind','value_kind','值类型','text'],['unit','unit_raw','单位','1']]
 records=parts.map(([part,path,label,value])=>({key:part,item_key:part,field:ext+'.'+path,fields:[ext+'.'+path],state_key:'s',module_key:'m',record_key:'r',record_group_key:'g',record_field:'payload.calculation_conditions.extensions.0.'+path,
  record_field_key:'phonon',settings_field:ext+'.value_raw',settings_part:part,label,current_value:value,required:true,human_modified:false,status:part==='raw'?'supported':'uncertain',reason:'本项理由：'+label,evidences:[]}))
 records.push({key:'scope',item_key:'scope',field:prefix+'.payload.calculation_conditions.method_scope',fields:[prefix+'.payload.calculation_conditions.method_scope.value_raw'],state_key:'s',module_key:'m',record_key:'r',record_group_key:'g',record_field:'payload.calculation_conditions.method_scope',settings_field:prefix+'.payload.calculation_conditions.method_scope',settings_part:'raw',label:'计算适用关系',current_value:{stage:'epc'},required:true,status:'unchecked',reason:'仅关系需要核验',evidences:[]})
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path==='/api/admin/papers/201')return {...draft.paper,material_states:structuredClone(draft.material_states)} as never
  if(path.includes('/classification-catalogs'))return {material_families:[],structure_families:[],material_dimensionalities:[{value:'three_dimensional',label:'三维'}]} as never
  if(path.includes('/form-definitions?'))return defs as never
  if(path.includes('/form-definitions/'))return defs.find(d=>decodeURIComponent(path).includes(d.definition_key)) as never
  if(path.includes('/draft-state'))return {version:'v1',draft:structuredClone(draft),staged:false} as never
  if(path.endsWith('/draft'))return {data:structuredClone(draft)} as never
  if(path.includes('/field-detail')){const item=new URL(path,'http://fixture').searchParams.get('item_key');return {record:records.find(r=>r.key===item),review_token:'token',can_approve:false,approval_state:'supported',source_state:'empty'} as never}
  if(path.includes('/manual-context'))return {version:'manual',record:records[0]} as never
  if(path.includes('/manual/'))return {data:{changed:false,reason:'',items:[]}} as never
  return {data:{},items:[],jobs:[],space_groups:[]} as never
 })
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('/summary')?{version:'v1',records,needs_check:false} as never:{data:structuredClone(draft),revision_id:'revision201',draft_version:1} as never)
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})

async function host(kind:string){
 auth.role=kind==='superadmin'?'superadmin':'admin'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/201/edit']}>
  {['admin','superadmin'].includes(kind)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>:<UploadTaskEditor taskId="ownership201" revisionPaperId={kind==='revision'?201:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Ownership paper')
 fireEvent.click(screen.getAllByText('超导性质').find(n=>n.closest('[data-property-module-toggle]'))!)
 await screen.findByLabelText('声子方法')
}
it.each(['upload','revision','admin','superadmin'])('%s 完整宿主：类型问题归主字段并在同一侧栏独立选择',async kind=>{
 await host(kind)
 const field=document.querySelector('[data-scientific-field-key="phonon"]')!
 await waitFor(()=>expect(field).toHaveAttribute('data-evidence-problem','true'))
 expect(document.querySelector('[data-evidence-fallback]')).toBeNull()
 fireEvent.click(within(field as HTMLElement).getByRole('button',{name:'设置字段：声子方法'}))
 const group=await screen.findByRole('group',{name:'字段核对子项'})
 fireEvent.click(within(group).getByRole('button',{name:/值类型/}))
 fireEvent.click(screen.getByRole('tab',{name:'来源核对'}))
 await waitFor(()=>expect(document.querySelector('[data-evidence-review-summary]')).toHaveTextContent('本项理由：值类型'))
 expect(document.querySelector('[data-evidence-review-summary]')).not.toHaveTextContent('本项理由：单位')
 fireEvent.click(within(group).getByRole('button',{name:/单位/}))
 await waitFor(()=>expect(document.querySelector('[data-evidence-review-summary]')).toHaveTextContent('本项理由：单位'))
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled()
 expect(vi.mocked(api.post).mock.calls.filter(([p])=>/\/jobs|submit-check|preflight/.test(p))).toHaveLength(0)
})
it('生产模块：五项问题全有入口，计算关系不会归给声子方法',async()=>{
 records.push({...records[0],key:'raw2',item_key:'raw2',status:'uncertain',reason:'值问题'})
 const reviews=records.filter(evidenceProblem).map(r=>r.field.replace(/\[(\d+)\]/g,'.$1'))
 // 同一路径的多个核对记录仍只计一个子项。
 render(<LanguageProvider><div data-evidence-scope="five"><div data-state-key="s"><PropertyModuleEditor modules={draft.material_states[0].property_modules} basePath="material_states.0.property_modules" reviewFields={reviews} onChange={()=>{}}/></div>
 <EvidenceFieldMarkers records={records} scope="five" onOpen={()=>{}} onChange={()=>{}}/></div></LanguageProvider>)
 fireEvent.click(screen.getByText('超导性质'))
 await waitFor(()=>expect(document.querySelector('[data-evidence-fallback]')).toBeNull())
 await waitFor(()=>expect(document.querySelector('[data-condition-review]')).toHaveAttribute('data-evidence-problem','true'))
 expect(document.querySelector('[data-module-key] summary')).toHaveTextContent('5 项待处理')
 expect(document.querySelector('[data-condition-review]')).toHaveAttribute('data-evidence-key','scope')
})
it('未应用设置阻止切换子项，当前输入和独立通过结果保留',async()=>{
 await host('upload')
 fireEvent.click(screen.getByRole('button',{name:'设置字段：声子方法'}))
 const group=await screen.findByRole('group',{name:'字段核对子项'})
 fireEvent.change(await screen.findByLabelText('字段名称（key）'),{target:{value:'尚未应用的新名称'}})
 fireEvent.click(within(group).getByRole('button',{name:/单位/}))
 expect(screen.getByLabelText('字段名称（key）')).toHaveValue('尚未应用的新名称')
 expect(within(group).getByRole('button',{name:/值 · 已通过/})).toHaveAttribute('aria-pressed','true')
 expect(screen.getAllByText('请先应用或取消当前字段设置，并等待保存完成，再切换核对子项。').find(node=>!node.closest('[hidden]'))).toBeVisible()
 expect(api.patch).not.toHaveBeenCalled();expect(records[0].status).toBe('supported')
})
it('选择类型后主动核对只请求类型子项，切换本身不发模型或保存',async()=>{
 const original=vi.mocked(api.get).getMockImplementation()!
 vi.mocked(api.get).mockImplementation(async path=>path.includes('/field-input')?{field_token:'kind-token',version:'kind-token',records:[records.find(r=>r.key==='kind')],needs_check:true} as never:original(path))
 const post=vi.mocked(api.post).getMockImplementation()!
 vi.mocked(api.post).mockImplementation(async(path,body:any)=>{
  if(path.endsWith('/jobs'))throw new Error('隔离模型请求已捕获')
  return post(path,body)
 })
 await host('upload');fireEvent.click(screen.getByRole('button',{name:'设置字段：声子方法'}))
 const group=await screen.findByRole('group',{name:'字段核对子项'})
 fireEvent.click(within(group).getByRole('button',{name:/值类型/}))
 fireEvent.click(screen.getByRole('tab',{name:'来源核对'}))
 await waitFor(()=>expect(document.querySelector('[data-evidence-review-summary]')).toHaveTextContent('本项理由：值类型'))
 expect(api.patch).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'大模型核对',exact:true}))
 await waitFor(()=>expect(vi.mocked(api.post).mock.calls.find(([path])=>path.endsWith('/jobs'))).toBeTruthy())
 const call=vi.mocked(api.post).mock.calls.find(([path])=>path.endsWith('/jobs'))!
 expect(call[1]).toMatchObject({purpose:'field',retry_keys:['kind'],expected_field_token:'kind-token'})
 expect(records[0].status).toBe('supported')
})
it('只读完整宿主仍可切换子项查看，不出现写操作',async()=>{
 render(<LanguageProvider><MemoryRouter><UploadTaskEditor taskId="frozen201" draftOverride={draft} readOnly frozenEvidenceRecords={records} frozenManualEvidence={[]} onSubmitted={()=>{}}/></MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Ownership paper')
 fireEvent.click(screen.getAllByText('超导性质').find(n=>n.closest('[data-property-module-toggle]'))!)
 fireEvent.click(await screen.findByRole('button',{name:'设置字段：声子方法'}))
 const group=await screen.findByRole('group',{name:'字段核对子项'})
 fireEvent.click(within(group).getByRole('button',{name:/值类型/}))
 fireEvent.click(screen.getByRole('tab',{name:'来源核对'}))
 await waitFor(()=>expect(document.querySelector('[data-evidence-review-summary]')).toHaveTextContent('本项理由：值类型'))
 expect(screen.queryByRole('button',{name:'大模型核对',exact:true})).toBeNull()
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled()
})
it('扩展重排与移除后仍按稳定字段键标记，不串到另一个扩展',async()=>{
 const onOpen=vi.fn(), module=draft.material_states[0].property_modules[0]
 const own=module.records[0].payload.calculation_conditions.extensions[0]
 const other={...own,field_key:'other',key:'another',name_raw:'另一个条件',value_raw:'other',value_text:'other'}
 const form=(extensions:any[])=><LanguageProvider><div data-evidence-scope="reorder"><div data-state-key="s">
  <PropertyModuleEditor modules={[{...module,records:[{...module.records[0],payload:{...module.records[0].payload,calculation_conditions:{extensions}}}]}]} basePath="material_states.0.property_modules" onChange={()=>{}}/>
 </div><EvidenceFieldMarkers records={records.slice(0,4)} scope="reorder" onOpen={onOpen} onChange={()=>{}}/></div></LanguageProvider>
 const view=render(form([own,other]));fireEvent.click(screen.getByText('超导性质'))
 await waitFor(()=>expect(document.querySelector('[data-scientific-field-key="phonon"]')).toHaveAttribute('data-evidence-problem','true'))
 view.rerender(form([other,own]))
 await waitFor(()=>expect(document.querySelector('[data-scientific-field-key="phonon"]')).toHaveAttribute('data-evidence-problem','true'))
 expect(document.querySelector('[data-scientific-field-key="other"]')).not.toHaveAttribute('data-evidence-problem')
 view.rerender(form([own]))
 await waitFor(()=>expect(document.querySelector('[data-scientific-field-key="phonon"]')).toHaveAttribute('data-evidence-problem','true'))
 fireEvent.click(screen.getByRole('button',{name:'设置字段：声子方法'}))
 expect(new Set(onOpen.mock.calls.at(-1)?.[1])).toEqual(new Set(['raw','name','kind','unit']))
})
