import '@testing-library/jest-dom/vitest'
import React from 'react'
import {MemoryRouter,useLocation} from 'react-router-dom'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import SearchPage from '../../frontend/src/pages/SearchPage'
import {LanguageProvider} from '../../frontend/src/context/LanguageContext'
import {api} from '../../frontend/src/lib/api'
import {loadClassificationCatalogs,refreshClassificationCatalogs} from '../../frontend/src/lib/classifications'
const auth=vi.hoisted(()=>({user:null as any,loading:false}))
vi.mock('../../frontend/src/context/AuthContext',()=>({useAuth:()=>auth}))
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn()}}))
vi.mock('../../frontend/src/lib/classifications',async original=>({...await original<any>(),loadClassificationCatalogs:vi.fn(),refreshClassificationCatalogs:vi.fn()}))
const catalog={material_families:[
 {id:1,name:'氢基超导体',name_zh:'氢基超导体',name_en:'Hydrogen-based superconductor',aliases:['hydride','hydrogen_based']},
 {id:9,name:'自建家族',name_en:'Custom family',aliases:[]},
],structure_families:[],material_dimensionalities:[]}
const result={items:[{paper_id:1,title:'当前论文'}],total:1,papers_total:1,states_total:1}
function Address(){return <output data-testid="address">{useLocation().search}</output>}
const tree=(path='/search?elements=H,La')=><LanguageProvider><MemoryRouter initialEntries={[path]}><SearchPage/><Address/></MemoryRouter></LanguageProvider>
beforeEach(()=>{
 const stored=new Map<string,string>()
 vi.stubGlobal('localStorage',{getItem:(key:string)=>stored.get(key)??null,setItem:(key:string,value:string)=>stored.set(key,value),removeItem:(key:string)=>stored.delete(key),clear:()=>stored.clear()})
 auth.user=null;auth.loading=false
 vi.mocked(loadClassificationCatalogs).mockReset().mockResolvedValue(catalog)
 vi.mocked(refreshClassificationCatalogs).mockReset().mockResolvedValue(catalog)
 vi.mocked(api.post).mockReset().mockImplementation(async url=>url.includes('structural-records')?{items:[],total:0}:result as any)
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('uses canonical catalog labels, custom families and IDs, restoring old aliases',async()=>{
 render(tree('/search?elements=H,La&superconductor_type=hydride'))
 const select=screen.getByRole('combobox',{name:'超导类型'})
 await waitFor(()=>expect(select).toHaveTextContent('氢基超导体'))
 expect(screen.queryByText('高压氢化物')).not.toBeInTheDocument()
 fireEvent.mouseDown(select)
 fireEvent.click(await screen.findByRole('option',{name:'自建家族'}))
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',expect.objectContaining({material_family_id:9})))
 expect(screen.getByTestId('address')).toHaveTextContent('material_family_id=9')
 expect(screen.getByTestId('address')).not.toHaveTextContent('superconductor_type')
})
it.each([null,{id:1,role:'user',is_approved:true},{id:2,role:'admin',is_approved:false}])('hides status and discards URL status for a public viewer %j',async user=>{
 auth.user=user;render(tree('/search?elements=H&review_status=Pending'))
 await screen.findByText('当前论文')
 expect(screen.queryByRole('combobox',{name:'审核状态'})).not.toBeInTheDocument()
 for(const [,body] of vi.mocked(api.post).mock.calls)expect(body).not.toHaveProperty('review_status')
})
it.each(['admin','superadmin'])('allows approved %s to request a selected status in both APIs',async role=>{
 auth.user={id:2,role,is_approved:true};render(tree())
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'审核状态'}))
 fireEvent.click(await screen.findByRole('option',{name:'待审核 Pending'}))
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',expect.objectContaining({review_status:'pending'})))
 expect(api.post).toHaveBeenCalledWith('/api/rag/structural-records/search',expect.objectContaining({review_status:'pending'}))
})
it('clears admin results immediately and ignores late admin responses after logout',async()=>{
 auth.user={id:2,role:'admin',is_approved:true}
 let finish!:(v:any)=>void
 vi.mocked(api.post).mockImplementation(async url=>url.includes('structural-records')?{items:[],total:0}:new Promise(resolve=>{finish=resolve}) as any)
 const rendered=render(tree('/search?elements=H&review_status=Rejected'))
 await waitFor(()=>expect(finish).toBeDefined())
 const adminFinish=finish
 auth.user=null
 vi.mocked(api.post).mockImplementation(async url=>url.includes('structural-records')?{items:[],total:0}:result as any)
 rendered.rerender(tree('/search?elements=H&review_status=Rejected'))
 adminFinish({...result,items:[{paper_id:2,title:'管理员私有结果'}]})
 await screen.findByText('当前论文')
 expect(screen.queryByText('管理员私有结果')).not.toBeInTheDocument()
 expect(screen.queryByRole('combobox',{name:'审核状态'})).not.toBeInTheDocument()
})
it('names representative Tc accurately and never refetches independent structures for it',async()=>{
 render(tree());await screen.findByText('当前论文')
 const before=vi.mocked(api.post).mock.calls.filter(([url])=>url.includes('structural-records')).length
 const button=screen.getByRole('button',{name:'仅看有代表 Tc 的材料状态'})
 expect(button).toHaveAccessibleDescription('仅筛选有代表 Tc 记录的材料状态；独立结构不受影响。')
 fireEvent.click(button)
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',expect.objectContaining({chart_only:true})))
 expect(button).toHaveAttribute('aria-pressed','true')
 expect(vi.mocked(api.post).mock.calls.filter(([url])=>url.includes('structural-records'))).toHaveLength(before)
})
it('retries catalog failures without using old fixed categories',async()=>{
 vi.mocked(loadClassificationCatalogs).mockRejectedValue(Error('failed'))
 render(tree());await screen.findByText('材料分类暂不可用')
 fireEvent.click(screen.getByRole('button',{name:'重试'}))
 await waitFor(()=>expect(screen.getByRole('combobox',{name:'超导类型'})).not.toHaveAttribute('aria-disabled','true'))
 fireEvent.mouseDown(screen.getByRole('combobox',{name:'超导类型'}))
 expect(await screen.findByRole('option',{name:'氢基超导体'})).toBeInTheDocument()
})
it('shows canonical English catalog and representative Tc text',async()=>{
 localStorage.setItem('sc-wiki.language','en')
 render(tree('/search?elements=H&material_family_id=1'))
 await waitFor(()=>expect(screen.getByRole('combobox',{name:'Superconductor type'})).toHaveTextContent('Hydrogen-based superconductor'))
 expect(screen.getByRole('button',{name:'Only material states with representative Tc'})).toHaveAccessibleDescription('Filters material states with representative Tc records; independent structures are unaffected.')
})
