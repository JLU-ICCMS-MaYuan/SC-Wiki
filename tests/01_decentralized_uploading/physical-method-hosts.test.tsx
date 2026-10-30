import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'

const auth=vi.hoisted(()=>({role:'admin'}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:auth.role,is_admin:true,is_approved:true}})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),patch:vi.fn(),put:vi.fn(),del:vi.fn()}}))
const details={method:'QHA volume scan',electronic_method:'HF',calculation_code:'Reported code',temperature_k:0,
  centroids:'fixed',volume:'optimized',cell_shape:'fixed'}
const definition={definition_key:'record.electronic_properties.band_gap',version:1,target_kind:'property_record',
  module_code:'electronic_properties',property_code:'band_gap',record_type:'property',core_schema:{},
  json_schema:{type:'object',properties:{},additionalProperties:true},ui_schema:{},checksum:'test',status:'published'}
const record={record_key:'gap',definition_key:definition.definition_key,definition_version:1,record_type:'property',
  property_code:'band_gap',module_code:'electronic_properties',name_raw:'Band gap',value_kind:'number',
  value_number:.48,value_raw:'0.48',unit_raw:'eV',canonical_unit:'eV',
  payload:{calculation_conditions:{electronic_method:'HF',extensions:[]}},evidences:[]}
const state={state_key:'s',material:'CaH2',material_name:'CaH2',state_kind:'theoretical',structure_optimization:'quasi_harmonic',
  structure_optimization_details:details,pressure_value_gpa:150,material_dimensionality:'unknown',
  crystal_system:'unknown',structure_families:[],schema_version:2,deleted_record_keys:[],deleted_module_keys:[],
  property_modules:[{module_key:'electronic',module_code:'electronic_properties',definition_key:'module.electronic_properties',
    definition_version:1,records:[record]}]}
const paper={id:181,title:'Electronic and vibrational methods',authors:[],year:2026,paper_type:'theoretical',
  theoretical_subtype:'calculation',material_families:[],research_materials:['CaH2'],review_status:'pending',uploaded_by_user_id:7}
const draft={paper,material_states:[state],structure_candidates:[]}
const review={key:'volume-review',item_key:'volume-review',state_key:'s',
 field:'material_states[0].structure_optimization_details.volume',label:'体积',current_value:'optimized',
 status:'supported',required:true,reason:'Original QHA volume minimization',evidences:[{file_id:'main',quote:'The QHA free energy was minimized over volume at 0 K.'}]}
let focusRevision=1, remoteTitle=paper.title
beforeEach(()=>{
 focusRevision=1;remoteTitle=paper.title
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path.includes('/form-definitions'))return(path.includes('?')?[definition]:definition)as never
  if(path.includes('/draft-revision'))return{revision:focusRevision,write_epoch:'current-cycle'}as never
  if(path.includes('/draft-state'))return{version:'current-cycle:v1',revision:focusRevision,write_epoch:'current-cycle',staged:false,draft:{...structuredClone(draft),paper:{...structuredClone(paper),title:remoteTitle}}}as never
  if(path.endsWith('/draft'))return{data:structuredClone(draft)}as never
  if(path==='/api/admin/papers/181')return{...paper,material_states:structuredClone(draft.material_states)}as never
  if(path.includes('/field-detail'))return{record:review,review_token:'token',source_state:'available',approval_state:'supported'}as never
  if(path.includes('/manual/'))return{data:{changed:false,items:[],history:[]}}as never
  return{data:{},items:[],jobs:[],space_groups:[]}as never
 })
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/open-workdraft'))return{revision:focusRevision,write_epoch:'current-cycle',version:'current-cycle:v1'}as never
  if(path.endsWith('/summary'))return{version:'v1',needs_check:false,records:[review]}as never
  if(path.endsWith('/revision-draft'))return{data:structuredClone(draft),revision_id:'revision181',draft_version:1}as never
  throw new Error('Unexpected model/write: '+path)
 })
 vi.mocked(api.patch).mockResolvedValue({changed:true,version:'v2'})
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})
async function host(kind:string){
 auth.role=kind==='superadmin'?'superadmin':'admin'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/181/edit']}>
 {['admin','superadmin'].includes(kind)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
 :<UploadTaskEditor taskId="scope181" revisionPaperId={kind==='revision'?181:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue(paper.title)
 await screen.findByDisplayValue('QHA volume scan')
}
function save(kind:string){fireEvent.click(screen.getByRole('button',{name:['admin','superadmin'].includes(kind)?'保存修改':'立即保存',exact:true}))}
it.each(['upload','revision','admin','superadmin'])('%s 四层语义与优化约束读取一致，无变化保存零写请求',async kind=>{
 await host(kind)
 expect(screen.getByLabelText('优化求力电子理论',{selector:'input'})).toHaveValue('HF')
 expect(screen.getByLabelText('优化温度 (K)',{selector:'input'})).toHaveValue('0')
 expect(screen.getByRole('combobox',{name:'结构优化目标'})).toHaveTextContent('准简谐自由能结构优化')
 expect(screen.getByRole('combobox',{name:'体积'})).toHaveTextContent('已优化')
 fireEvent.click(screen.getByRole('heading',{name:'电子性质',exact:true}))
 expect(await screen.findByLabelText('数值')).toHaveValue('0.48')
 expect(screen.getByLabelText('电子结构计算方法')).toHaveValue('HF')
 expect(screen.getByLabelText('声子计算技术')).toHaveValue('')
 expect(screen.getByLabelText('振动处理层次')).toHaveValue('')
 save(kind)
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))})
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled()
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'结构优化目标'}))
 expect(screen.getByRole('option',{name:'量子非谐自由能结构优化'})).toBeVisible()
 expect(screen.queryByRole('option',{name:'SSCHA（历史优化标签）'})).not.toBeInTheDocument()
 fireEvent.keyDown(screen.getByRole('listbox'),{key:'Escape'})
})
it.each(['upload','revision','admin','superadmin'])('%s 只保存当前几何字段，电子带隙数值和理论不串改，来源仍可查看',async kind=>{
 await host(kind)
 fireEvent.change(screen.getByLabelText('结构优化方法'),{target:{value:'用户报告的自由能优化'}})
 save(kind)
 await waitFor(()=>expect(api.patch).toHaveBeenCalledTimes(1))
 const body=vi.mocked(api.patch).mock.calls[0][1]as any
 expect(body.changes).toEqual([{path:['material_states',{key:'state_key',value:'s'},'structure_optimization_details','method'],
  before:'QHA volume scan',value:'用户报告的自由能优化'}])
 expect(screen.getByLabelText('优化求力电子理论')).toHaveValue('HF')
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>/jobs|preflight|submit-check/.test(path))).toEqual([])
 const marker=document.querySelector('[data-evidence-key="volume-review"]')as HTMLElement
 await waitFor(()=>expect(marker).not.toBeNull())
 fireEvent.click(marker)
 const drawer=document.querySelector('.evidence-review-drawer')as HTMLElement
 expect(await within(drawer).findByText(/QHA free energy was minimized/)).toBeVisible()
})
it('只读旧sscha和历史混装标签保持可查看，不自动转成新类别或发起写入',async()=>{
 const legacy=structuredClone(draft)
 legacy.material_states[0].structure_optimization='sscha'
 render(<LanguageProvider><UploadTaskEditor taskId="legacy" draftOverride={legacy as any} readOnly onSubmitted={()=>{}}/></LanguageProvider>)
 await screen.findByDisplayValue('QHA volume scan')
 expect(screen.getByRole('combobox',{name:'结构优化目标'})).toHaveTextContent('SSCHA（历史优化标签）')
 expect(screen.getByLabelText('结构优化方法')).toBeDisabled()
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled()
})

it('新方法字段保留中文组合输入，保存失败后输入与相邻电子理论保持，重试只写当前字段',async()=>{
 await host('upload')
 const input=screen.getByLabelText('结构优化方法')
 fireEvent.compositionStart(input)
 fireEvent.change(input,{target:{value:'量子自由能优化'}})
 fireEvent.compositionEnd(input,{data:'量子自由能优化'})
 vi.mocked(api.patch).mockRejectedValueOnce(Object.assign(new Error('network save failed'),{detail:{message:'本次方法保存失败，请重试'}}))
 save('upload')
 expect(await screen.findByText(/本次方法保存失败，请重试/)).toBeVisible()
 expect(input).toHaveValue('量子自由能优化')
 expect(screen.getByLabelText('优化求力电子理论')).toHaveValue('HF')
 save('upload')
 await waitFor(()=>expect(api.patch).toHaveBeenCalledTimes(2))
 const body=vi.mocked(api.patch).mock.calls[1][1]as any
 expect(body.changes).toHaveLength(1)
 expect(body.changes[0].path.at(-1)).toBe('method')
})

it.each(['upload','revision','admin','superadmin'])('%s 切回只提示，确认后载入整稿且不调用模型',async kind=>{
 await host(kind)
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))})
 const fullBefore=vi.mocked(api.get).mock.calls.filter(([p])=>p.includes('/draft-state')).length
 focusRevision=2;remoteTitle='另一页已保存的标题'
 await act(async()=>{
  window.dispatchEvent(new Event('focus'))
  document.dispatchEvent(new Event('visibilitychange'))
 })
 const button=await screen.findByRole('button',{name:'载入最新稿',exact:true})
 expect(screen.getByDisplayValue(paper.title)).toBeVisible()
 expect(vi.mocked(api.get).mock.calls.filter(([p])=>p.includes('/draft-state'))).toHaveLength(fullBefore)
 fireEvent.click(button)
 await screen.findByDisplayValue(remoteTitle)
 expect(vi.mocked(api.post).mock.calls.filter(([p])=>/\/jobs|preflight|submit-check/.test(p))).toEqual([])
 expect(screen.getByRole('link',{name:'交接记录与快照'})).toHaveAttribute('target','_blank')
})

it('切回载入先保护未保存人工输入，拒绝替换不读整稿',async()=>{
 await host('upload')
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))})
 fireEvent.change(screen.getByDisplayValue(paper.title),{target:{value:'本页未保存标题'}})
 focusRevision=2
 await act(async()=>window.dispatchEvent(new Event('focus')))
 const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
 const before=vi.mocked(api.get).mock.calls.filter(([p])=>p.includes('/draft-state')).length
 fireEvent.click(await screen.findByRole('button',{name:'载入最新稿',exact:true}))
 expect(confirm).toHaveBeenCalledOnce()
 expect(screen.getByDisplayValue('本页未保存标题')).toBeVisible()
 expect(vi.mocked(api.get).mock.calls.filter(([p])=>p.includes('/draft-state'))).toHaveLength(before)
 confirm.mockRestore()
})
