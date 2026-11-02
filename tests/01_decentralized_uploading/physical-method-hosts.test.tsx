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
 field:'material_states[0].structure_optimization',label:'结构优化方法',current_value:'quasi_harmonic',
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
 await screen.findByRole('combobox',{name:'结构优化方法'})
}
function save(kind:string){fireEvent.click(screen.getByRole('button',{name:['admin','superadmin'].includes(kind)?'保存修改':'立即保存',exact:true}))}
it.each(['upload','revision','admin','superadmin'])('%s 题录侧栏展示真实外部来源链接，不请求伪造PDF区域',async kind=>{
 const external={key:'external-title',item_key:'external-title',field:'paper.title',fields:['paper.title'],
  label:'标题',current_value:paper.title,status:'supported',required:true,reason:'正式题录身份已核实',
  evidences:[{file_id:'crossref:10.1073/pnas.1118168109',chunk_index:0,origin_kind:'external_bibliography',
   source_url:'https://api.crossref.org/works/10.1073%2Fpnas.1118168109',
   quote:JSON.stringify({DOI:'10.1073/pnas.1118168109',title:[paper.title],volume:'109',issue:'17',page:'6463-6466'})}]}
 const get=vi.mocked(api.get).getMockImplementation()!
 vi.mocked(api.get).mockImplementation(async(path,init)=>path.includes('/field-detail')?
  {record:external,review_token:'token',source_state:'available',approval_state:'supported'}as never:get(path,init))
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/open-workdraft'))return{revision:1,write_epoch:'current-cycle'}as never
  if(path.endsWith('/summary'))return{version:'v1',records:[external]}as never
  if(path.endsWith('/revision-draft'))return{data:structuredClone(draft),revision_id:'revision181',draft_version:1}as never
  throw new Error('Unexpected model/write: '+path)
 })
 await host(kind)
 const caption=await waitFor(()=>{
  const node=document.querySelector('[data-evidence-key="external-title"][data-evidence-caption="true"]')as HTMLElement
  expect(node).not.toBeNull();return node
 })
 fireEvent.click(caption)
 expect(await screen.findByRole('link',{name:'Crossref 正式题录（外部来源）'})).toHaveAttribute('href','https://api.crossref.org/works/10.1073%2Fpnas.1118168109')
 expect(screen.getByText(/109 卷 · 17 期 · 6463-6466/)).toBeVisible()
 expect(vi.mocked(api.post).mock.calls.filter(([p])=>p.includes('/region')||p.includes('/jobs'))).toEqual([])
})
it.each(['upload','revision','admin','superadmin'])('%s 真实疑问只标红，无状态文字后缀，键盘仍可打开来源',async kind=>{
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/open-workdraft'))return{revision:1,write_epoch:'current-cycle'}as never
  if(path.endsWith('/summary'))return{version:'v1',records:[{...review,status:'uncertain'}]}as never
  if(path.endsWith('/revision-draft'))return{data:structuredClone(draft),revision_id:'revision181',draft_version:1}as never
  throw new Error('Unexpected model/write: '+path)
 })
 await host(kind)
 const caption=await waitFor(()=>{
  const node=document.querySelector('[data-evidence-key="volume-review"][data-evidence-caption="true"]')as HTMLElement
  expect(node).not.toBeNull();return node
 })
 expect(caption).toHaveAttribute('data-evidence-caption-problem','true')
 expect(caption.textContent).toBe('结构优化方法')
 expect(document.querySelector('[data-evidence-status-text]')).toBeNull()
 fireEvent.keyDown(caption,{key:'Enter'})
 const drawer=await waitFor(()=>{
  const node=document.querySelector('.evidence-review-drawer')as HTMLElement;expect(node).not.toBeNull();return node
 })
 expect(await within(drawer).findByText(/QHA free energy was minimized/)).toBeVisible()
})
it.each(['upload','revision','admin','superadmin'])('%s 四层语义与优化约束读取一致，无变化保存零写请求',async kind=>{
 await host(kind)
 expect(screen.queryByLabelText('优化求力电子理论')).not.toBeInTheDocument()
 expect(screen.queryByLabelText('优化温度 (K)')).not.toBeInTheDocument()
 expect(screen.getByRole('combobox',{name:'结构优化方法'})).toHaveTextContent('准简谐结构优化')
 expect(screen.queryByRole('combobox',{name:'体积'})).not.toBeInTheDocument()
 expect(document.querySelector('[data-evidence-status-text]')).toBeNull()
 fireEvent.click(screen.getByRole('heading',{name:'电子性质',exact:true}))
 expect(await screen.findByLabelText('数值')).toHaveValue('0.48')
 expect(screen.getByLabelText('电子结构计算方法')).toHaveValue('HF')
 expect(screen.getByLabelText('声子计算技术')).toHaveValue('')
 expect(screen.getByLabelText('振动处理层次')).toHaveValue('')
 save(kind)
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))})
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled()
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'结构优化方法'}))
 expect(screen.getByRole('option',{name:'SSCHA量子非谐结构优化'})).toBeVisible()
 expect(screen.queryByRole('option',{name:'量子非谐自由能结构优化'})).not.toBeInTheDocument()
 fireEvent.keyDown(screen.getByRole('listbox'),{key:'Escape'})
})
it.each(['upload','revision','admin','superadmin'])('%s 只保存当前几何字段，电子带隙数值和理论不串改，来源仍可查看',async kind=>{
 await host(kind)
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'结构优化方法'}))
 fireEvent.click(screen.getByRole('option',{name:'SSCHA量子非谐结构优化'}))
 save(kind)
 await waitFor(()=>expect(api.patch).toHaveBeenCalledTimes(1))
 const body=vi.mocked(api.patch).mock.calls[0][1]as any
 expect(body.changes).toEqual([{path:['material_states',{key:'state_key',value:'s'},'structure_optimization'],
  before:'quasi_harmonic',value:'sscha'}])
 expect(screen.queryByLabelText('优化求力电子理论')).not.toBeInTheDocument()
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
 await screen.findByRole('combobox',{name:'结构优化方法'})
 expect(screen.getByRole('combobox',{name:'结构优化方法'})).toHaveTextContent('SSCHA量子非谐结构优化')
 expect(screen.getByRole('combobox',{name:'结构优化方法'})).toHaveAttribute('aria-disabled','true')
 expect(api.patch).not.toHaveBeenCalled();expect(api.put).not.toHaveBeenCalled()
})

it('优化方法保存失败后保留选择，重试只写当前字段',async()=>{
 await host('upload')
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'结构优化方法'}))
 fireEvent.click(screen.getByRole('option',{name:'静态结构优化'}))
 vi.mocked(api.patch).mockRejectedValueOnce(Object.assign(new Error('network save failed'),{detail:{message:'本次方法保存失败，请重试'}}))
 save('upload')
 expect(await screen.findByText(/本次方法保存失败，请重试/)).toBeVisible()
 expect(screen.getByRole('combobox',{name:'结构优化方法'})).toHaveTextContent('静态结构优化')
 save('upload')
 await waitFor(()=>expect(api.patch).toHaveBeenCalledTimes(2))
 const body=vi.mocked(api.patch).mock.calls[1][1]as any
 expect(body.changes).toHaveLength(1)
 expect(body.changes[0].path.at(-1)).toBe('structure_optimization')
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

it.each(['upload','revision','admin','superadmin'])('%s 新版固定契约：软件参数独立、声子直接字段与材料类型可见',async kind=>{
 const modern:any=structuredClone(draft)
 modern._form_contract_version=1
 modern.material_states[0].material='CaH6'
 modern.material_states[0].material_name='CaH6'
 modern.material_states[0].property_modules=[{module_key:'sc',module_code:'superconductive_properties',
  definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[{
   record_key:'tc-modern',module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',
   definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version:2,
   method_code:'isotropic_eliashberg',name_raw:'Tc',value_kind:'number',value_number:235,value_raw:'235',unit_raw:'K',canonical_unit:'K',
   payload:{parameters:{lambda_ep:2.69,mu_star:.1},calculation_conditions:{
    calculation_code:'QE + SSCHA',phonon_method:'DFPT',vibrational_treatment:'anharmonic_quantum',
    qe:{energy_cutoff:{value_kind:'number',value_raw:'90',value_number:90,unit_raw:'Ry'}},
    sscha:{energy_cutoff:{value_kind:'number',value_raw:'80',value_number:80,unit_raw:'Ry'}}}},
   evidences:[] }]}]
 const modernDefinition:any={...definition,definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',
  version:2,module_code:'superconductive_properties',property_code:'tc',record_type:'predicted_tc',method_code:'isotropic_eliashberg',
  json_schema:{type:'object',properties:{calculation_conditions:{type:'object'},parameters:{type:'object'}},additionalProperties:false}}
 const previous=vi.mocked(api.get).getMockImplementation()!
 vi.mocked(api.get).mockImplementation(async(path,init)=>{
  if(path.includes('/form-definitions?'))return[modernDefinition]as never
  if(path.includes('/form-definitions/'))return modernDefinition as never
  if(path.includes('/draft-state'))return{version:'v1',draft:structuredClone(modern),staged:false}as never
  if(path.endsWith('/draft'))return{data:structuredClone(modern)}as never
  if(path==='/api/admin/papers/181')return{...modern.paper,material_states:structuredClone(modern.material_states)}as never
  return previous(path,init)
 })
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/open-workdraft'))return{revision:1,write_epoch:'current-cycle'}as never
  if(path.endsWith('/summary'))return{version:'v1',records:[],needs_check:false}as never
  if(path.endsWith('/revision-draft'))return{data:structuredClone(modern),revision_id:'revision181',draft_version:1}as never
  throw new Error('Unexpected model/write: '+path)
 })
 await host(kind)
 expect(screen.getByRole('combobox',{name:'材料状态类型'})).toBeVisible()
 fireEvent.click(screen.getAllByText('超导性质').find(node=>node.closest('[data-property-module-toggle]'))!)
 const qe=await waitFor(()=>{const node=document.querySelector('[data-software-condition-group="qe"]')as HTMLElement;expect(node).not.toBeNull();return node})
 const sscha=document.querySelector('[data-software-condition-group="sscha"]')as HTMLElement
 const input=within(qe).getByRole('textbox',{name:'波函数／平面波截断能'})
 expect(input).toHaveValue('90')
 expect(within(sscha).getByRole('textbox',{name:'波函数／平面波截断能'})).toHaveValue('80')
 expect(screen.getByRole('textbox',{name:'声子方法'})).toHaveValue('DFPT')
 expect(document.querySelector('[data-issue-field*="method_scope"]')).toBeNull()
 expect(document.querySelector('[data-issue-field*="pressure_min_gpa"]')).toBeNull()
 fireEvent.change(input,{target:{value:'95'}})
 expect(within(qe).getByRole('textbox',{name:'波函数／平面波截断能'})).toHaveValue('95')
 expect(within(sscha).getByRole('textbox',{name:'波函数／平面波截断能'})).toHaveValue('80')
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.includes('/jobs')||path.includes('/check'))).toEqual([])
})
