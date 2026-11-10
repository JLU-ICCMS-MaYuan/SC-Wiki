import '@testing-library/jest-dom/vitest'
import React from 'react'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {MemoryRouter,Routes,Route} from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import {LanguageProvider} from '../../frontend/src/context/LanguageContext'
import {clearFormDefinitionCache} from '../../frontend/src/lib/formDefinitions'
import {api} from '../../frontend/src/lib/api'
const auth=vi.hoisted(()=>({role:'admin'}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:auth.role,is_admin:true,is_approved:true}})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),patch:vi.fn(),put:vi.fn(),del:vi.fn()}}))
const key='c'.repeat(64),field='material_states[0].structure_families'
let draft:any,manual:any,confirmed=false,failSave=false,failDecision=false,order:string[]=[]
const record=()=>({key,item_key:key,field,fields:[field],label:'结构家族',state_key:'s',
 current_value:draft.material_states[0].structure_families.map((f:any)=>f.name),empty_allowed:true,
 required:draft.material_states[0].structure_families.length>0,human_modified:true,
 status:confirmed?'supported':'uncertain',reason:confirmed?'人工确认留空：暂不分类':'原AI只说明旧分类',
 ai_reason:confirmed?'':'原AI只说明旧分类',evidences:[{file_id:'main',chunk_index:0,quote:'CaH4 has a tetragonal structure.'}],
 stale:!confirmed,pending_review:!confirmed,human_confirmed:confirmed,
 ...(confirmed?{source_kind:'human_review',field_decision:{contract:'field-review-v2',action:'approve',mode:'without_evidence'}}:{})})
beforeEach(()=>{
 order=[];confirmed=false;failSave=false;failDecision=false;manual={changed:true,reason:'',no_evidence_reason:'',items:[]}
 draft={paper:{id:177,title:'Original title',authors:[],year:2026,paper_type:'theoretical',material_families:[],
  review_status:'pending',uploaded_by_user_id:8},structure_candidates:[],
 material_states:[{id:1,state_key:'s',material:'CaH4',material_name:'tI10-CaH4',state_kind:'theoretical',
  pressure_value_gpa:50,structure_optimization:'classical_static',crystal_system:'tetragonal',element_count:2,
  material_dimensionality:'three_dimensional',superconductor:{chemical_formula:'CaH4'},
  structure_families:[{id:1,name:'Sodalite',status:'confirmed'}],property_modules:[]}]}
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path==='/api/admin/papers/177')return {...draft.paper,material_states:structuredClone(draft.material_states)} as never
  if(path.includes('/classification-catalogs'))return {material_families:[],structure_families:[{id:1,name:'Sodalite',name_en:'Sodalite',name_zh:'方钠石'}],material_dimensionalities:[]} as never
  if(path.includes('/draft-state'))return {version:'v',draft:structuredClone(draft),staged:false} as never
  if(path.endsWith('/draft'))return {data:structuredClone(draft)} as never
  if(path.includes('/field-detail'))return {record:record(),review_token:'fresh-token',can_approve_without_evidence:true,can_confirm_empty:false,
   approval_state:confirmed?'human_approved':'modification_required',source_state:'available'} as never
  if(path.includes('/manual-context'))return {version:'field-manual',record:record()} as never
  if(path.includes('/manual/'))return {data:manual} as never
  return {data:{},items:[],jobs:[],space_groups:[]} as never
 })
 vi.mocked(api.patch).mockImplementation(async(_path,body:any)=>{
  order.push('value')
  if(failSave)throw new Error('save failed')
  expect(body.field_scope).toBe(true)
  expect(body.changes).toHaveLength(1)
  expect(body.changes[0].path.at(-1)).toBe('structure_families')
  draft.material_states[0].structure_families=body.changes[0].value
  return {changed:true,version:'saved'} as never
 })
 vi.mocked(api.put).mockImplementation(async(_path,body:any)=>{
  order.push('materials');manual={...manual,...body,after_value:[]};return {data:manual} as never
 })
 vi.mocked(api.post).mockImplementation(async(path,body:any)=>{
  if(path.endsWith('/summary'))return {version:'v',records:[record()],needs_check:false} as never
  if(path.endsWith('/field-decision')){
   order.push('confirm')
   if(failDecision)throw new Error('confirmation failed')
   expect(body.action).toBe('approve_without_evidence');expect(body.review_token).toBe('fresh-token')
   expect(draft.material_states[0].structure_families).toEqual([])
   expect(manual.reason).toBe('');expect(manual.no_evidence_reason).toBe('')
   confirmed=true;return {record:record(),review_token:'accepted',can_confirm_empty:true,approval_state:'human_approved',source_state:'available'} as never
  }
  if(path.endsWith('/jobs'))throw new Error('manual empty must not call model')
  return {data:structuredClone(draft),revision_id:'revision-empty',draft_version:1} as never
 })
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})
async function open(role:string){
 auth.role=role==='superadmin'?'superadmin':'admin'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/177/edit']}>
  {['admin','superadmin'].includes(role)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
   :<UploadTaskEditor taskId="empty-task" revisionPaperId={role==='revision'?177:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Original title')
 const host=document.querySelector('[data-issue-field="'+field+'"]') as HTMLElement
 fireEvent.click(host.querySelector('.MuiChip-deleteIcon')!)
 await waitFor(()=>expect(host.querySelector('input')).toHaveValue(''))
 fireEvent.click(host.querySelector('[data-evidence-key]')!)
 const reason=await screen.findByLabelText('人工修改判断理由（必填）')
 fireEvent.change(reason,{target:{value:'此状态暂不分类'}})
 return host
}
it.each(['upload','revision','admin','superadmin'])('%s 人工确认留空局部保存且零模型，旧原文可读，结果和颜色一致',async role=>{
 const host=await open(role)
 fireEvent.click(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true}))
 expect(await screen.findByText('已人工通过，未提供证据（结果已保存）')).toBeVisible()
 expect(order).toEqual(['value','confirm'])
 expect(screen.getByText(/本次未调用大模型/)).toBeVisible()
 expect(screen.getByText(/CaH4 has a tetragonal structure/)).toBeVisible()
 expect(screen.queryByText('原AI只说明旧分类',{exact:true})).not.toBeInTheDocument()
 await waitFor(()=>expect(host.querySelector('[data-evidence-key]')).toHaveAttribute('data-evidence-status','waived'))
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs'))).toBe(false)
 expect(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true})).toBeDisabled()
 fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'),{target:{value:'新的留空理由'}})
 expect(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true})).toBeEnabled()
 await waitFor(()=>expect(host.querySelector('[data-evidence-key]')).toHaveAttribute('data-evidence-status','waived'))
})
it.each(['upload','revision','admin','superadmin'])('%s 保存失败保留说明，不发确认或模型',async role=>{
 await open(role);failSave=true
 fireEvent.click(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true}))
 expect((await within(document.querySelector('.evidence-review-drawer')! as HTMLElement).findAllByText(/save failed/)).at(-1)).toBeVisible()
 expect(order).toEqual(['value'])
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('此状态暂不分类')
})
it('确认写入失败不显示通过，保留理由和当前红色',async()=>{
 const host=await open('superadmin');failDecision=true
 fireEvent.click(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true}))
 expect((await within(document.querySelector('.evidence-review-drawer')! as HTMLElement).findAllByText(/confirmation failed/)).at(-1)).toBeVisible()
 expect(screen.queryByText('已人工通过，未提供证据（结果已保存）')).not.toBeInTheDocument()
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('此状态暂不分类')
 expect(host.querySelector('[data-evidence-key]')).toHaveAttribute('data-evidence-status','attention')
})
it('人工确认在途又修改理由，迟到成功不能清除新修改提醒',async()=>{
 const host=await open('upload')
 const original=vi.mocked(api.post).getMockImplementation()!
 let release!:(v:any)=>void
 vi.mocked(api.post).mockImplementation(async(path,body:any)=>{
  if(path.endsWith('/field-decision'))return new Promise(resolve=>{release=resolve})
  return original(path,body)
 })
 fireEvent.click(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'),{target:{value:'在途新理由'}})
 confirmed=true
 await act(async()=>release({record:record(),review_token:'late',approval_state:'human_approved',source_state:'available'}))
 expect(screen.queryByText('已人工通过，未提供证据（结果已保存）')).not.toBeInTheDocument()
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('在途新理由')
 expect(host.querySelector('[data-evidence-key]')).toHaveAttribute('data-evidence-status','attention')
})
