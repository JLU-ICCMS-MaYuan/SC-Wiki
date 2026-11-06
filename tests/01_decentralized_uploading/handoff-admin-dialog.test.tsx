import '@testing-library/jest-dom/vitest'
import React from 'react'
import {render,screen,fireEvent,waitFor,cleanup,within} from '@testing-library/react'
import {afterEach,beforeEach,it,expect,vi} from 'vitest'
import {MemoryRouter} from 'react-router-dom'
import AdminPage from '../../frontend/src/pages/AdminPage'
import {LanguageProvider} from '../../frontend/src/context/LanguageContext'
import {api} from '../../frontend/src/lib/api'
const state=vi.hoisted(()=>({role:'admin',restore:vi.fn(),gate:vi.fn()}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>({user:{id:7,role:state.role,is_approved:true},logout:vi.fn()})}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),put:vi.fn(),del:vi.fn()}}))
vi.mock('../../frontend/src/components/EvidenceWorkflow',()=>({useEvidenceWorkflow:()=>({
 dialog:null,records:[],openIssue:vi.fn(),restore:state.restore,gate:state.gate,
})}))
beforeEach(()=>{
 state.gate.mockResolvedValue({expected_evidence_version:'verified'})
 vi.mocked(api.get).mockImplementation(async url=>{
  if(url.includes('/papers/all'))return{items:[{id:192,title:'正式收到的标题',year:2026,review_status:'pending',uploaded_by_user_id:9}],total:1}as never
  return[]as never
 })
 vi.mocked(api.post).mockResolvedValue({write_epoch:'dialog-cycle',paper_header:{title:'当前工作稿标题'}}as never)
})
afterEach(()=>{cleanup();vi.clearAllMocks()})
function host(role:string){
 state.role=role
 render(<LanguageProvider><MemoryRouter><AdminPage embedded mode={role as 'admin'|'superadmin'}/></MemoryRouter></LanguageProvider>)
}
it.each(['admin','superadmin'])('%s 快速审核先领取并展示当前稿，响应失败重试保持交接身份',async role=>{
 host(role)
 fireEvent.click(await screen.findByRole('button',{name:'审核',exact:true}))
 const dialog=await screen.findByRole('dialog')
 fireEvent.mouseDown(within(dialog).getByRole('combobox'))
 fireEvent.click(await screen.findByRole('option',{name:'拒绝并退回作者',exact:true}))
 expect(within(dialog).getByText('当前工作稿标题')).toBeVisible()
 expect(within(dialog).getByRole('link',{name:'交接记录与快照'})).toHaveAttribute('target','_blank')
 expect(vi.mocked(api.post).mock.calls[0]).toEqual(['/api/rag/evidence/open-workdraft',{target:'paper',target_id:'192'}])
 vi.mocked(api.post).mockRejectedValueOnce(new Error('响应中断')).mockResolvedValueOnce({ok:true})
 fireEvent.click(within(dialog).getByRole('button',{name:'拒绝并退回作者',exact:true}))
 await screen.findByText(/响应中断/)
 await waitFor(()=>expect(within(dialog).getByRole('button',{name:'拒绝并退回作者',exact:true})).toBeEnabled())
 fireEvent.click(within(dialog).getByRole('button',{name:'拒绝并退回作者',exact:true}))
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
 const commits=vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))
 expect(commits).toHaveLength(2)
 expect((commits[0][1]as any).review_request_id).toBe((commits[1][1]as any).review_request_id)
})
it('其他审核员已接手时不打开私稿或启动审核',async()=>{
 host('admin')
 vi.mocked(api.post).mockRejectedValueOnce(new Error('工作稿已由其他审核员接手'))
 fireEvent.click(await screen.findByRole('button',{name:'审核',exact:true}))
 await screen.findByText('工作稿已由其他审核员接手')
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
 expect(state.restore).not.toHaveBeenCalled()
})
it.each(['admin','superadmin'])('%s 代理超时后按原操作身份恢复结果，不重复核对或创建交接',async role=>{
 host(role)
 fireEvent.click(await screen.findByRole('button',{name:'审核',exact:true}))
 const dialog=await screen.findByRole('dialog')
 fireEvent.mouseDown(within(dialog).getByRole('combobox'))
 fireEvent.click(await screen.findByRole('option',{name:'审核通过并发布'}))
 vi.mocked(api.post).mockRejectedValueOnce(Object.assign(new Error('HTTP 502'),{status:502})).mockResolvedValueOnce({ok:true})
 fireEvent.click(within(dialog).getByRole('button',{name:'审核通过并发布',exact:true}))
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
 const commits=vi.mocked(api.post).mock.calls.filter(([url])=>url.endsWith('/review-commit'))
 expect(commits).toHaveLength(2)
 expect(commits[0][1]).toEqual(commits[1][1])
 expect(state.gate).toHaveBeenCalledTimes(1)
})
