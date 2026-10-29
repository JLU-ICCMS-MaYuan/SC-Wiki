import '@testing-library/jest-dom/vitest'
import React from 'react'
import {MemoryRouter} from 'react-router-dom'
import {render,screen,cleanup} from '@testing-library/react'
import {it,expect,afterEach,vi} from 'vitest'
import PaperEditView from '../../frontend/src/components/PaperEditView'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn().mockResolvedValue({items:[]})}}))
const SUMMARY = '1. Comm.120b｜1911-04-28\n2. Comm.122b｜1911-05-27'
const KEY_FINDING = '昂内斯利用新建成的液氦低温实验装置。\n1. 在 4.2 K 附近电阻陡峭突变\n2. 在 3 K 乃至 1.5 K 区间维持零电阻'

const HG_PAPER = {
  id: 9,
  title: 'Further experiments with liquid helium. V.',
  journal: 'Commun. Phys. Lab. Univ. Leiden',
  year: 1911,
  review_status: 'approved',
  summary: SUMMARY,
  key_finding: KEY_FINDING,
  methodology: '["电阻测量"]',
  key_properties: [],
  material_states: [],
}


afterEach(cleanup)
it('正式论文详情继续逐字保留总结与核心发现的换行',async()=>{
 render(<MemoryRouter><PaperEditView paper={HG_PAPER} onBack={()=>{}} /></MemoryRouter>)
 for(const text of [SUMMARY,KEY_FINDING]) {
  const body=await screen.findByText(text,{normalizer:v=>v})
  expect(body.textContent).toBe(text);expect(body).toHaveStyle({whiteSpace:'pre-wrap'})
 }
})
