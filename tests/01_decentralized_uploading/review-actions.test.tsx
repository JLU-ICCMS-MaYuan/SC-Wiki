import '@testing-library/jest-dom/vitest'
import React from 'react'
import {render,screen,fireEvent,waitFor,cleanup,within} from '@testing-library/react'
import {afterEach,beforeEach,it,expect,vi} from 'vitest'
import {MemoryRouter,Routes,Route} from 'react-router-dom'
import AdminPage from '../../frontend/src/pages/AdminPage'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import {LanguageProvider} from '../../frontend/src/context/LanguageContext'
import {api} from '../../frontend/src/lib/api'
const state=vi.hoisted(()=>({role:'admin',gate:vi.fn(),hasUnsavedChanges:()=>false}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:state.role,is_approved:true},logout:vi.fn()})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),patch:vi.fn(),put:vi.fn(),del:vi.fn()}}))
vi.mock('../../frontend/src/components/EvidenceWorkflow',()=>({useEvidenceWorkflow:()=>({
 dialog:null,issues:[],records:[],openIssue:vi.fn(),restore:vi.fn(),gate:state.gate,hasUnsavedChanges:state.hasUnsavedChanges,
 invalidate:vi.fn(),bind:vi.fn(),busy:false,hasPendingWrites:()=>false,hasUnsavedRefreshInput:()=>false,getRefreshRevision:()=>0,getEditRevision:()=>0,
})}))
beforeEach(()=>{
 state.gate.mockResolvedValue({expected_evidence_version:'verified'})
 vi.mocked(api.get).mockImplementation(async url=>{
  const paper={id:192,title:'当前稿',year:2026,paper_type:'review',review_status:'pending',review_comment:'通过',uploaded_by_user_id:9,
    material_families:[],material_states:[]}
  if(url.includes('/papers/all'))return{items:[paper],total:1}as never
  if(url==='/api/admin/papers/192')return paper as never
  if(url.includes('draft-state'))return{staged:false,revision:1,write_epoch:'cycle',draft:{paper,material_states:[]}}as never
  if(url.includes('classification'))return{material_families:[],structure_families:[],material_dimensionalities:[]}as never
  return{items:[]}as never
 })
 vi.mocked(api.post).mockResolvedValue({write_epoch:'cycle',paper_header:{title:'当前稿'}}as never)
})
afterEach(()=>{cleanup();vi.clearAllMocks();localStorage.clear()})
async function host(role:string,mode:string,lang:string){
 state.role=role;localStorage.setItem('sc-wiki.language',lang)
 render(<LanguageProvider><MemoryRouter initialEntries={[mode==='edit'?'/admin/papers/192/edit':'/admin']}>
 <Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage/>}/>
 <Route path="/admin" element={<AdminPage embedded mode={role as 'admin'|'superadmin'}/>}/></Routes>
 </MemoryRouter></LanguageProvider>)
 if(mode==='quick'){
  fireEvent.click(await screen.findByRole('button',{name:lang==='zh'?'审核':'Review',exact:true}))
  return within(await screen.findByRole('dialog'))
 }
 await screen.findByDisplayValue('当前稿');return within(document.body)
}
it.each(['admin','superadmin'].flatMap(role=>['quick','edit'].flatMap(mode=>['zh','en'].map(lang=>({role,mode,lang})))))
('$role $mode $lang 明确选择两种结果，旧意见不预填，原审核员可一次通过发布',async({role,mode,lang})=>{
 const ui=await host(role,mode,lang)
 const label=lang==='zh'?'审核意见':'Review Comment'
 expect(ui.getByLabelText(label)).toHaveValue('')
 const action=ui.getByRole('button',{name:mode==='edit'?(lang==='zh'?'提交审核':'Submit Review'):(lang==='zh'?'确认审核':'Confirm Review'),exact:true})
 expect(action).toBeDisabled();fireEvent.click(action)
 expect(vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))).toHaveLength(0)
 fireEvent.mouseDown(ui.getByRole('combobox',{name:lang==='zh'?'审核结果':'Review Result'}))
 expect(screen.queryByRole('option',{name:/退回待审核|Send back to pending/})).not.toBeInTheDocument()
 fireEvent.click(await screen.findByRole('option',{name:lang==='zh'?'审核通过并发布':'Approve and publish',exact:true}))
 fireEvent.click(ui.getByRole('button',{name:lang==='zh'?'审核通过并发布':'Approve and publish',exact:true}))
 await waitFor(()=>expect(vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))).toHaveLength(1))
 const payload=vi.mocked(api.post).mock.calls.find(([url])=>url.endsWith('/review-commit'))![1]as any
 expect(payload).toMatchObject({paper_id:192,status:'approved',comment:'',expected_evidence_version:'verified'})
 expect(state.gate).toHaveBeenCalledTimes(1)
})
it.each(['admin','superadmin'].flatMap(role=>['quick','edit'].map(mode=>({role,mode}))))
('$role $mode 拒绝直接退回作者；批准失败保留选择和本轮意见',async({role,mode})=>{
 const ui=await host(role,mode,'zh')
 fireEvent.mouseDown(ui.getByRole('combobox',{name:'审核结果'}))
 fireEvent.click(await screen.findByRole('option',{name:'审核通过并发布',exact:true}))
 fireEvent.change(ui.getByLabelText('审核意见'),{target:{value:'本轮已核查'}})
 vi.mocked(api.post).mockRejectedValueOnce(new Error('隔离保存失败'))
 fireEvent.click(ui.getByRole('button',{name:'审核通过并发布',exact:true}))
 await screen.findByText(/隔离保存失败/)
 expect(ui.getByLabelText('审核意见')).toHaveValue('本轮已核查')
 expect(ui.getByRole('button',{name:'审核通过并发布',exact:true})).toBeEnabled()
 fireEvent.mouseDown(ui.getByRole('combobox',{name:'审核结果'}))
 fireEvent.click(await screen.findByRole('option',{name:'拒绝并退回作者',exact:true}))
 fireEvent.click(ui.getByRole('button',{name:'拒绝并退回作者',exact:true}))
 await waitFor(()=>expect(vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))).toHaveLength(2))
 const calls=vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))
 expect(calls[1][1]).toMatchObject({status:'rejected',comment:'本轮已核查'})
 expect(state.gate).toHaveBeenCalledTimes(1)
})
