import '@testing-library/jest-dom/vitest'
import React from 'react'
import {afterEach,it,expect,vi}from'vitest'
import {cleanup,render,screen}from'@testing-library/react'
import {MemoryRouter}from'react-router-dom'
import {LanguageProvider}from'../../frontend/src/context/LanguageContext'
import PaperEditView from'../../frontend/src/components/PaperEditView'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn().mockResolvedValue({items:[],collections:[]})}}))
afterEach(cleanup)
it('已批准论文详情提示实际状态，不再提示待审',()=>{
 render(<LanguageProvider><MemoryRouter><PaperEditView paper={{id:1429,title:'Verified title',review_status:'approved',material_states:[]}}onBack={()=>{}}/></MemoryRouter></LanguageProvider>)
 expect(screen.getAllByText('审核状态: 审核完成').length).toBeGreaterThan(0)
 expect(screen.queryByText('论文已提交审核。普通用户不能在这里直接修改正式记录。')).not.toBeInTheDocument()
})

it.each(['pending', 'rejected'])('旧批准版的当前返修状态为%s，顶部和基础信息一致', status => {
 const label = status === 'pending' ? '待审核' : '已拒绝'
 render(<LanguageProvider><MemoryRouter><PaperEditView paper={{id:1208,title:'CaH6',review_status:'approved',workflow_status:status,material_states:[]}} onBack={()=>{}}/></MemoryRouter></LanguageProvider>)
 expect(screen.getAllByText(`审核状态: ${label}`)).toHaveLength(2)
 expect(screen.getByText('当前展示旧批准版；修订稿通过审核后更新公开内容。')).toBeInTheDocument()
 expect(screen.queryByText('审核状态: 审核完成')).not.toBeInTheDocument()
})

it('上传者返修入口仍显示当前拒绝状态和原意见', () => {
 render(<LanguageProvider><MemoryRouter><PaperEditView paper={{id:1208,title:'CaH6',review_status:'approved',workflow_status:'rejected',can_revise:true,review_comment:'请修正来源',material_states:[]}} onBack={()=>{}}/></MemoryRouter></LanguageProvider>)
 expect(screen.getByRole('link',{name:'修改并重新提交'})).toHaveAttribute('href','/papers/1208/revise')
 expect(screen.getByText('请修正来源')).toBeInTheDocument()
 expect(screen.getAllByText('审核状态: 已拒绝')).toHaveLength(2)
 expect(screen.getByText('当前展示旧批准版；修订稿通过审核后更新公开内容。')).toBeInTheDocument()
})

it('公开访客仅看批准版，详情不再有旧化学式关键词卡片', () => {
 render(<LanguageProvider><MemoryRouter><PaperEditView paper={{id:1208,title:'CaH6',review_status:'approved',materials:['CaH8'],keywords_tags:'["Calcium hydride"]',material_states:[]}} onBack={()=>{}}/></MemoryRouter></LanguageProvider>)
 expect(screen.getAllByText('审核状态: 审核完成')).toHaveLength(2)
 expect(screen.queryByText(/当前展示旧批准版/)).not.toBeInTheDocument()
 expect(screen.queryByText('化学式')).not.toBeInTheDocument()
 expect(screen.queryByText('CaH8')).not.toBeInTheDocument()
 expect(screen.queryByText('Calcium hydride')).not.toBeInTheDocument()
})
