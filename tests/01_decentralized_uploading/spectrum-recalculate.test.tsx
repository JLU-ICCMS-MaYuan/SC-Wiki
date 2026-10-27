import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { SpectrumMetrics } from '../../frontend/src/components/SpectrumDetailView'
import type { PropertySpectrumItem } from '../../frontend/src/lib/propertySpectra'

afterEach(cleanup)
function item():PropertySpectrumItem {
  return {id:'c',version:3,state_key:'s',stale:false,source:{},run:{id:'r',status:'succeeded'},review:{},result:{
    curves:[{id:'a',kind:'alpha2f',unit:'pixel',points:[{frequency_thz:0,observed_amplitude:0,reconstructed_amplitude:0,status:'manual_adjusted'},{frequency_thz:6,observed_amplitude:null,reconstructed_amplitude:6,status:'manual_adjusted'}]}],
    quality:{integrals:{raw:{method:'alpha2f-relative-v2',pixel_integral:10,normalization:{status:'unavailable',reason:'缺少同条件论文λ'},parameters:{lambda:{status:'unavailable',reason:'需要绝对幅值'},omega_log:{status:'available',value:106.123}},minimum_integrated_thz:0,maximum_integrated_thz:6}},
      manual_zero_checks:{a:{complete:true,boundary:'confirmed',zeroPixel:435,curves:[{id:'a',name:'α²F',status:'complete',nearest:{frequency:0,distancePx:0}}]}}}
  }}
}
it('独立展示ωlog，不展示旧零频核对，旧解释不再展示',()=>{
  const data=item(),onRecalculate=vi.fn()
  render(<SpectrumMetrics item={data} curves={data.result.curves} history={false} onRecalculate={onRecalculate}/>)
  expect(screen.getByText('106.123')).toBeVisible()
  expect(screen.getByText('缺少同条件论文λ')).toBeVisible();expect(screen.queryByText('λ',{exact:true})).toBeNull()
  expect(screen.queryByText('零频位置核对完成')).toBeNull()
  expect(screen.queryByText(/为什么零频完成/)).toBeNull()
  expect(screen.queryByText(/幅值怎么核对/)).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'重新计算'}))
  expect(onRecalculate).toHaveBeenCalledTimes(1)
})
it('计算中禁止再次提交，失效/历史版本不展示完整积分',()=>{
  const data=item(),fn=vi.fn()
  render(<SpectrumMetrics item={data} curves={data.result.curves} history onRecalculate={fn} recalculating/>)
  const button=screen.getByRole('button',{name:'计算中…'})
  expect(button).toBeDisabled();fireEvent.click(button);expect(fn).not.toHaveBeenCalled()
  expect(screen.queryByText('106.123')).toBeNull()
})
it('DOS积分可显示而3N比较缺失，旧零频报告不再展示',()=>{
  const data=item();data.result.curves[0].kind='phonon_dos'
  data.result.quality={dos_mode_integral:{status:'available',integral:12,comparison_status:'unavailable',reason:'缺少原胞依据'},
    manual_zero_checks:{a:{complete:false,boundary:'confirmed',zeroPixel:435,curves:[{id:'a',name:'H',status:'missing_point'}]}}}
  render(<SpectrumMetrics item={data} curves={data.result.curves} history={false}/>)
  expect(screen.getByText('12')).toBeVisible();expect(screen.getByText('缺少原胞依据')).toBeVisible()
  expect(screen.queryByRole('button',{name:'继续核对 H'})).toBeNull()
})


it('03移除计算时间和所有来源JSON，但不影响结果或后台数据',()=>{
  const data=item()
  data.result.quality!.recalculations={alpha2f:{calculated_at:'2026-10-27T01:00:00Z'}}
  data.result.quality!.comparisons={raw:{omega_log:{status:'unavailable',source:{quote:'秘密的内部原始JSON字段',file_id:'internal'}}}}
  render(<SpectrumMetrics item={data} curves={data.result.curves} history={false}/>)
  expect(screen.queryByText(/本版本计算时间/)).toBeNull()
  expect(screen.queryByText(/参考来源/)).toBeNull()
  expect(screen.queryByText(/秘密的内部原始JSON字段/)).toBeNull()
  expect(screen.getByText('106.123')).toBeVisible()
  expect(data.result.quality!.recalculations.alpha2f.calculated_at).toBeTruthy()
})


it('旧计算记录的末端限制不继续显示，提示按保存范围重新计算',()=>{
 const data=item()
 delete data.result.quality!.integrals.raw.method
 data.result.quality!.integrals.raw.parameters={lambda:{status:'unavailable',reason:'高频末端尚待核对，请点击下方末端坐标；图框上限不等于曲线真实截止'},omega_log:{status:'unavailable',reason:'高频末端尚待核对，请点击下方末端坐标；图框上限不等于曲线真实截止'}}
 render(<SpectrumMetrics item={data} curves={data.result.curves} history={false}/>)
 expect(screen.queryByText(/高频末端尚待核对/)).toBeNull()
 expect(screen.getByText(/请点击重新计算，独立计算ωlog/)).toBeVisible()
})
