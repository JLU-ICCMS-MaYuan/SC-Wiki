import '@testing-library/jest-dom/vitest'
import React from 'react'
import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect,vi} from 'vitest'
import {MemoryRouter} from 'react-router-dom'
import {PropertySpectraProvider,PropertySpectrumControls,PropertySpectrumSection,PropertySpectrumState} from '../../frontend/src/components/PropertySpectra'
import {api} from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn()}}))
afterEach(()=>{cleanup();vi.clearAllMocks()})
it('冻结谱只使用提供的曲线和当时状态，不请求当前谱或提供写入口',async()=>{
 const frozen:any={version:'frozen',can_edit:false,can_review:false,jobs:[],items:[{
  id:'fixture',version:1,state_key:'s',stale:false,source:{source_name:'冻结谱原图',pdf_page:3},
  run:{status:'succeeded'},review:{curve:{status:'accepted'}},
  result:{curves:[{id:'curve',kind:'phonon_dos',unit:'THz',points:[{frequency_thz:1,value:9}]}]},
 }]}
 render(<MemoryRouter><PropertySpectraProvider readOnly context={{target:{target:'paper',target_id:'1'},frozenListing:frozen}}>
  <PropertySpectrumControls/><PropertySpectrumState stateKey="s" summary="材料"><PropertySpectrumSection moduleCode="dynamical_properties"/></PropertySpectrumState>
 </PropertySpectraProvider></MemoryRouter>)
 expect(screen.queryByText('刷新谱状态')).not.toBeInTheDocument()
 expect(screen.queryByRole('link')).not.toBeInTheDocument()
 fireEvent.click(await screen.findByRole('button',{name:'查看冻结谱数据'}))
 expect(await screen.findByRole('dialog')).toBeVisible()
 expect(screen.getByRole('button',{name:'下载完整冻结数据'})).toBeVisible()
 expect(api.get).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled()
})
