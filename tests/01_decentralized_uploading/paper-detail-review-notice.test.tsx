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
