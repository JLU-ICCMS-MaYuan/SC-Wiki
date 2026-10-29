import '@testing-library/jest-dom/vitest'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import SearchPage from '../../frontend/src/pages/SearchPage'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
it('defaults to papers and switches to stable states in the same result page', async () => {
  vi.mocked(api.post).mockImplementation(async (url, body: any) => url.includes('structural-records') ? {items:[],total:0} : ({
    view: body.view, total: body.view === 'states' ? 8 : 1, papers_total: 1, states_total: 8,
    items: body.view === 'states' ? Array.from({length:8}, (_,i) => ({state_id:i+1,state_key:`s${i}`,paper_id:271,material:'LaSc2H24',pressure_gpa:i===7?300:150+i*25,space_group:'P6/mmm',space_group_number:191,structure_optimization:i===7?'sscha':'classical_static',title:'来源论文',structures:[]})) : [{paper_id:271,title:'来源论文',matched_states:8}],
  }) as any)
  render(<MemoryRouter initialEntries={['/search?elements=H,La,Sc&mode=elements_exact_search']}><SearchPage /></MemoryRouter>)
  expect(await screen.findByRole('button',{name:'按论文'})).toHaveAttribute('aria-pressed','true')
  expect(await screen.findByText('来源论文')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'按材料状态'}))
  expect(await screen.findAllByTestId('search-state-card')).toHaveLength(8)
  expect(screen.queryByText('结果表格')).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'按材料状态'})).toHaveAttribute('aria-pressed','true')
  expect(screen.getAllByRole('link',{name:'查看来源论文'})[0]).toHaveAttribute('target','_blank')
})

it('late paper responses cannot overwrite the selected state view or cause structural refetches', async()=>{
  let finishPaper!: (value:any)=>void
  vi.mocked(api.post).mockImplementation(async(url,body:any)=>{
    if(url.includes('structural-records'))return {items:[],total:0} as any
    if(body.view==='papers')return new Promise(resolve=>{finishPaper=resolve}) as any
    return {items:[{paper_id:271,state_id:7,state_key:'state-7',material:'LaSc2H24',title:'当前状态',structure_optimization:'sscha'}],total:1,papers_total:1,states_total:1} as any
  })
  render(<MemoryRouter initialEntries={['/search?elements=H,La,Sc']}><SearchPage/></MemoryRouter>)
  await waitFor(()=>expect(finishPaper).toBeDefined())
  fireEvent.click(screen.getByRole('button',{name:'按材料状态'}))
  expect(await screen.findByText('当前状态')).toBeInTheDocument()
  finishPaper({items:[{paper_id:271,title:'迟到的论文'}],total:1,papers_total:1,states_total:1})
  await waitFor(()=>expect(screen.queryByText('迟到的论文')).not.toBeInTheDocument())
  expect(screen.getAllByTestId('search-state-card')).toHaveLength(1)
  expect(vi.mocked(api.post).mock.calls.filter(([url])=>url.includes('structural-records'))).toHaveLength(1)
})
