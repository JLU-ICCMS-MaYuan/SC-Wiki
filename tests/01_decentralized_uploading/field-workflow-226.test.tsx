import {currentEvidenceField} from '../../frontend/src/lib/evidenceFields'
import {createManualEvidenceDrafts} from '../../frontend/src/lib/manualEvidenceDrafts'
import {applySingleEvidenceValue} from '../../frontend/src/lib/evidenceProposals'
import {makeWorkdraft} from '../performance/workdraft-fixture.mjs'
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
let draft:any,manual:any,confirmed=false,failSave=false,failDecision=false,order:string[]=[],scalarMode=false
const scalarRecords=()=>['material_name','element_count'].map((name,index)=>({
 key:String(index+1).repeat(64),item_key:String(index+1).repeat(64),
 field:`material_states[0].${name}`,fields:[`material_states[0].${name}`],label:name,state_key:'s',
 current_value:draft.material_states[0][name],required:false,status:'supported',reason:'原值依据',evidences:[],
}))
const record=()=>({key,item_key:key,field,fields:[field],label:'结构家族',state_key:'s',
 current_value:confirmed?draft.material_states[0].structure_families.map((f:any)=>f.name):['Sodalite'],empty_allowed:true,
 required:true,human_modified:false,
 status:'supported',reason:confirmed?'人工确认留空：暂不分类':'原AI只说明旧分类',
 ai_reason:confirmed?'':'原AI只说明旧分类',evidences:[{file_id:'main',chunk_index:0,quote:'CaH4 has a tetragonal structure.'}],
 stale:!confirmed&&!draft.material_states[0].structure_families.length,pending_review:!confirmed&&!draft.material_states[0].structure_families.length,human_confirmed:confirmed,
 ...(confirmed?{source_kind:'human_review',field_decision:{contract:'field-review-v2',action:'approve',mode:'without_evidence'}}:{})})
beforeEach(()=>{
 order=[];confirmed=false;failSave=false;failDecision=false;scalarMode=false;manual={changed:true,reason:'',no_evidence_reason:'',items:[]}
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
  if(path.includes('/field-detail'))return {record:scalarMode?(scalarRecords().find(r=>path.includes(r.item_key)) || record()):record(),review_token:'fresh-token',can_approve_without_evidence:true,can_confirm_empty:false,
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
  if(path.endsWith('/summary'))return {version:'v',records:scalarMode?scalarRecords():[record()],needs_check:false} as never
  if(path.endsWith('/field-decision')){
   order.push('confirm')
   expect(body.action).toBe('approve_without_evidence')
   expect(manual.reason).toBe('');expect(manual.items).toHaveLength(0)
   confirmed=true;return {record:record(),review_token:'accepted',can_approve_without_evidence:true,approval_state:'human_approved',source_state:'available'} as never
  }
  if(path.endsWith('/jobs'))throw new Error('manual empty must not call model')
  return {data:structuredClone(draft),revision_id:'revision-empty',draft_version:1} as never
 })
})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})

async function renderHost(role:string){
 auth.role=role==='superadmin'?'superadmin':role==='admin'?'admin':'user'
 render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/177/edit']}>
  {['admin','superadmin'].includes(role)?<Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/></Routes>
   :<UploadTaskEditor taskId="empty-task" revisionPaperId={role==='revision'?177:undefined} onSubmitted={()=>{}}/>}
 </MemoryRouter></LanguageProvider>)
 await screen.findByDisplayValue('Original title')
}
async function open(role:string){
 await renderHost(role)
 const host=document.querySelector('[data-issue-field="'+field+'"]') as HTMLElement
 fireEvent.click(host.querySelector('.MuiChip-deleteIcon')!)
 fireEvent.click(host.querySelector('[data-evidence-key]')!)
 await screen.findByLabelText('人工修改判断理由（必填）')
 return host
}
it.each(['upload','revision','admin','superadmin'])('%s 原正常列表本地修改后显示人工区；零资料明确通过标黄且零模型',async role=>{
 const host=await open(role)
 await waitFor(()=>expect(host.querySelector('[data-evidence-status="attention"]')).toBeTruthy())
 expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('')
 fireEvent.click(screen.getByRole('button',{name:'不提交人工证据直接人工通过审核',exact:true}))
 await screen.findByText('已人工通过，未提供证据（结果已保存）')
 await waitFor(()=>expect(host.querySelector('[data-evidence-status="waived"]')).toBeTruthy())
 expect(order).toEqual(['value','confirm'])
 expect(api.put).not.toHaveBeenCalled()
 expect(vi.mocked(api.post).mock.calls.some(([p])=>p.endsWith('/jobs'))).toBe(false)
})
it.each(['upload','revision','admin','superadmin'])('%s 结构家族设置共用多选，应用更新主值且取消不改',async role=>{
 await open(role)
 fireEvent.click(screen.getByRole('tab',{name:'字段设置',exact:true}))
 let input=await screen.findByRole('combobox',{name:'当前值',exact:true})
 fireEvent.change(input,{target:{value:'取消的修改'}})
 fireEvent.keyDown(input,{key:'Enter'})
 fireEvent.click(screen.getByRole('button',{name:'取消',exact:true}))
 await waitFor(()=>expect(document.querySelector('.evidence-review-drawer')).toBeNull())
 expect(document.querySelector('[data-issue-field="'+field+'"]')?.textContent).not.toContain('取消的修改')
 fireEvent.click(document.querySelector('[data-issue-field="'+field+'"] [data-evidence-key]')!)
 fireEvent.click(screen.getByRole('tab',{name:'字段设置',exact:true}))
 input=await screen.findByRole('combobox',{name:'当前值',exact:true})
 fireEvent.change(input,{target:{value:'笼型结构'}})
 fireEvent.keyDown(input,{key:'Enter'})
 fireEvent.click(screen.getByRole('button',{name:'应用修改',exact:true}))
 await waitFor(()=>expect(document.querySelector('[data-issue-field="'+field+'"]')?.textContent).toContain('笼型结构'))
 expect(api.put).not.toHaveBeenCalled()
})

it.each(['upload','revision','admin','superadmin'])('%s 文字和数字字段的共享设置可打开并应用到原控件',async role=>{
 scalarMode=true
 await renderHost(role)
 for(const [name,value] of [['material_name','人工材料名'],['element_count','3']]){
  const fieldPath=`material_states[0].${name}`
  const host=document.querySelector(`[data-issue-field="${fieldPath}"]`) as HTMLElement
  await waitFor(()=>expect(host.querySelector('[data-evidence-key]')).toBeTruthy())
  fireEvent.click(host.querySelector('[data-evidence-key]')!)
  fireEvent.click(await screen.findByRole('tab',{name:'字段设置',exact:true}))
  const input=await screen.findByRole('textbox',{name:'当前值',exact:true})
  fireEvent.change(input,{target:{value}})
  fireEvent.click(screen.getByRole('button',{name:'应用修改',exact:true}))
  await waitFor(()=>expect(document.querySelector('.evidence-review-drawer')).toBeNull())
  expect(within(host).getByRole('textbox')).toHaveValue(value)
 }
 expect(api.put).not.toHaveBeenCalled()
 expect(vi.mocked(api.post).mock.calls.some(([p])=>p.endsWith('/jobs'))).toBe(false)
})

it('共享设置更新只分配当前节点：论文不重建材料，记录修改不重建无关状态/方法',()=>{
 const draft=makeWorkdraft(2,20) as any
 draft.material_states[0].structure={large_geometry:'unchanged'}
 const paper=applySingleEvidenceValue(draft,{key:'year',item_key:'year',field:'paper.year'},2027)
 expect(paper.material_states).toBe(draft.material_states)
 expect(paper.paper.authors).toBe(draft.paper.authors)
 const changed=applySingleEvidenceValue(draft,{key:'lambda',item_key:'lambda',field:'material_states[0].property_modules[0].records[0].payload.parameters.lambda_ep',
  state_key:'state-0',module_key:'module-0',record_key:'record-0-0',record_group_key:'group-0',
  record_method_key:'method-isotropic_eliashberg',record_field:'payload.parameters.lambda_ep'},3.0)
 expect(changed.material_states[1]).toBe(draft.material_states[1])
 expect(changed.material_states[0].structure).toBe(draft.material_states[0].structure)
 const a=changed.material_states[0].property_modules[0].records,b=draft.material_states[0].property_modules[0].records
 expect(a[0].payload.parameters.lambda_ep).toBe(3)
 expect(a[2].payload.parameters.lambda_ep).toBe(3)
 expect(a[3]).toBe(b[3])
 expect(b[0].payload.parameters.lambda_ep).toBe(2.69)
})

it('无资料人工通过清空输入后，旧读取不能重新带回已取消的资料',()=>{
 const drafts=createManualEvidenceDrafts(),key='cancelled'
 drafts.edit(key,{reason:'旧理由',text:'旧证据'})
 const writes=drafts.read(key).writes
 drafts.discard(key)
 drafts.hydrate(key,{changed:true,reason:'迟到旧理由',no_evidence_reason:'',items:[{id:'old',kind:'text',text:'旧证据',source_description:'旧值'}]},writes)
 expect(drafts.read(key).reason).toBe('')
 expect(drafts.read(key).text).toBe('')
 expect(drafts.read(key).dirty).toBe(false)
})

it('旧草稿缺少分类列表时统一读取为空列表，不把空表示差异当科学修改',()=>{
 const result=currentEvidenceField({key:'k',field:'material_states[0].structure_families',state_key:'s'} as any,{},[{state_key:'s'}])
 expect(result?.value).toEqual([])
 expect(result?.comparisonValue).toEqual([])
})
