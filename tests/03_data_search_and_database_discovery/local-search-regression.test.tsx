import '@testing-library/jest-dom/vitest'
import React from 'react'
import {MemoryRouter} from 'react-router-dom'
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.mock('../../frontend/src/context/AuthContext', () => ({useAuth:()=>({user:null,loading:false})}))
import SearchPage from '../../frontend/src/pages/SearchPage'
import {api} from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn().mockResolvedValue({material_families:[]}),post:vi.fn()}}))
const response={items:[{paper_id:9,title:'Mercury superconductivity',year:1911,doi:'10.1000/mercury',matched_states:1}],total:1,papers_total:1,states_total:1}
const at=(path:string)=>render(<MemoryRouter initialEntries={[path]}><SearchPage/></MemoryRouter>)
beforeEach(()=>{vi.mocked(api.post).mockReset().mockImplementation(async(url)=>url.includes('structural-records')?{items:[],total:0}:response as any)})
afterEach(cleanup)
it.each(['elements_combination_search','elements_exact_search','elements_contained_search'])('%s keeps local query semantics with paper results',async mode=>{
 at(`/search?elements=Hg&mode=${mode}`)
 expect(await screen.findByText(response.items[0].title)).toBeInTheDocument()
 expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',{elements:['Hg'],mode,view:'papers',limit:20,offset:0})
 expect(screen.queryByText(/Alexandria|HTSC-2025|全部来源/)).not.toBeInTheDocument()
 expect(screen.queryByText('结果表格')).not.toBeInTheDocument()
})
it('formula entry is a native new-tab link that keeps the original input',()=>{
 at('/search');fireEvent.change(screen.getByRole('textbox'),{target:{value:'Hg'}})
 const link=screen.getByRole('link',{name:'搜索',exact:true});expect(link).toHaveAttribute('target','_blank')
 expect(link.getAttribute('href')).toContain('formula=Hg');expect(screen.getByRole('textbox')).toHaveValue('Hg')
 expect(api.post).not.toHaveBeenCalled()
})
it('filters and server pagination keep their state and native paper destination',async()=>{
 vi.mocked(api.post).mockImplementation(async url=>url.includes('structural-records')?{items:[],total:0}:{...response,total:41} as any)
 at('/search?elements=Hg&view=papers&paper_page=2&keyword=Hg&tc_min=4')
 await screen.findByText(response.items[0].title)
 expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',expect.objectContaining({keyword:'Hg',tc_min:4,offset:20}))
 const link=screen.getByRole('link',{name:'查看来源论文'});expect(link).toHaveAttribute('target','_blank');expect(link.getAttribute('href')).toContain('return=')
 fireEvent.click(screen.getAllByRole('button',{name:'下一页'})[0])
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',expect.objectContaining({offset:40,keyword:'Hg'})))
})
it('failed result requests retry without pretending to be empty results',async()=>{
 let fail=true;vi.mocked(api.post).mockImplementation(async url=>{if(url.includes('structural-records'))return {items:[],total:0};if(fail)throw Error('暂时不可用');return response as any})
 at('/search?elements=Hg');expect(await screen.findByText('暂时不可用')).toBeInTheDocument();fail=false
 fireEvent.click(screen.getByRole('button',{name:'重试'}));expect(await screen.findByText(response.items[0].title)).toBeInTheDocument()
})
it('reset clears only result filters and retains the selected system',async()=>{
 at('/search?elements=Hg&keyword=missing');await screen.findByText(response.items[0].title)
 fireEvent.click(screen.getByRole('button',{name:'重置',exact:true}))
 expect(screen.getByPlaceholderText('如 LaH10')).toHaveValue('')
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',{elements:['Hg'],mode:'elements_combination_search',view:'papers',limit:20,offset:0}))
})

it('returning to element entry retains the original selected elements',async()=>{
 at('/search?elements=H,La,Sc&mode=elements_exact_search')
 await screen.findByText(response.items[0].title)
 fireEvent.click(screen.getByRole('link',{name:'返回元素搜索'}))
 expect(await screen.findByText('H, La, Sc')).toBeInTheDocument()
 expect(screen.getByRole('button',{name:'仅包含选择元素'})).toHaveAttribute('aria-pressed','true')
})
