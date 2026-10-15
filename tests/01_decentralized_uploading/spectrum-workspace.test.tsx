import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { SpectrumProvider, SpectrumStateSection } from '../../frontend/src/components/SpectrumWorkspace'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),put:vi.fn(),download:vi.fn()}}))

const data=()=>({version:'v1',can_edit:true,can_review:true,jobs:[],items:[{
  id:'collection',version:2,state_key:'s1',stale:false,source:{size_px:[160,100],pdf_page:1,source_name:'known.pdf'},run:{status:'succeeded'},review:{},
  result:{calibration:{panel_id:'p',state_key:'s1',curves:[]},candidates:{},failures:[],
    curves:[{id:'alpha',kind:'alpha2f',projection:null,unit:'dimensionless',frequency_direction:'x',
      axis_calibration:{amplitude:{slope:-.01,intercept:1}},clipped_frequencies_thz:[],
      points:[{frequency_thz:1,frequency_pixel:20,observed_amplitude:.01,reconstructed_amplitude:.01,status:'observed'},
        {frequency_thz:2,frequency_pixel:40,observed_amplitude:null,reconstructed_amplitude:null,status:'missing'},
        {frequency_thz:3,frequency_pixel:60,observed_amplitude:.03,reconstructed_amplitude:.03,status:'observed'}]}],
    quality:{curves:{},integrals:{raw:{lambda_integral:.04,omega_log_k:90}},comparisons:{raw:{lambda:{status:'available',reference:.05,signed_difference:-.01,absolute_difference:.01,relative_difference_pct:-20},omega_log:{status:'unavailable',reason:'缺少同条件、可定位的论文报告值'}}},limitations:['积分一致是约束，不独立证明准确度']}}
}]})

beforeEach(()=>{vi.mocked(api.get).mockResolvedValue(data());vi.mocked(api.download).mockResolvedValue(new Blob(['image']));URL.createObjectURL=vi.fn(()=>'blob:image');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.clearAllMocks()})

describe('谱质量共用界面',()=>{
  it('只读态仍能叠加与缩放，缺口不连接，缺参考不显示零误差',async()=>{
    render(<SpectrumProvider target={{target:'paper',target_id:'1'}} readOnly><SpectrumStateSection stateKey="s1"/></SpectrumProvider>)
    await screen.findByText('原始重建 · λ / ωlog')
    expect(screen.getByText(/缺少同条件、可定位/)).toBeTruthy()
    expect(screen.queryByText('保存本条谱审核')).toBeNull()
    const overlay=screen.getByLabelText('原图叠加提取曲线') as HTMLInputElement
    expect(overlay.checked).toBe(true);fireEvent.click(overlay);expect(overlay.checked).toBe(false)
    const chart=screen.getByRole('img',{name:'提取谱曲线'})
    expect(chart.querySelector('path[stroke="#078284"]')?.getAttribute('d')?.match(/M/g)).toHaveLength(2)
  })

  it('单谱审核携带展示版本，服务端冲突明确显示',async()=>{
    vi.mocked(api.post).mockRejectedValue(new Error('内容或谱版本已变化，请刷新后重试'))
    render(<SpectrumProvider target={{target:'paper',target_id:'1'}}><SpectrumStateSection stateKey="s1"/></SpectrumProvider>)
    fireEvent.click(await screen.findByText('保存本条谱审核'))
    await screen.findByText(/内容或谱版本已变化/)
    expect(api.post).toHaveBeenCalledWith('/api/rag/spectra/collection/review',expect.objectContaining({expected_collection_version:2,expected_version:'v1',curve_id:'alpha'}))
  })
})
