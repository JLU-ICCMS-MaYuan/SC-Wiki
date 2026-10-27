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
    quality:{integrals:{raw:{parameters:{lambda:{status:'unavailable',reason:'需要绝对幅值'},omega_log:{status:'available',value:106.123}},minimum_integrated_thz:0,maximum_integrated_thz:6}},
      manual_zero_checks:{a:{complete:true,boundary:'confirmed',zeroPixel:435,curves:[{id:'a',name:'α²F',status:'complete',nearest:{frequency:0,distancePx:0}}]}}}
  }}
}
it('独立展示ωlog，零频完成只出现一次，旧解释不再展示',()=>{
  const data=item(),onRecalculate=vi.fn()
  render(<SpectrumMetrics item={data} curves={data.result.curves} history={false} onRecalculate={onRecalculate}/>)
  expect(screen.getByText('106.123')).toBeVisible()
  expect(screen.getByText('λ：需要绝对幅值')).toBeVisible()
  expect(screen.getAllByText('零频位置核对完成')).toHaveLength(1)
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
it('DOS积分可显示而3N比较缺失，未完成分波有独立入口',()=>{
  const data=item();data.result.curves[0].kind='phonon_dos'
  data.result.quality={dos_mode_integral:{status:'available',integral:12,comparison_status:'unavailable',reason:'缺少原胞依据'},
    manual_zero_checks:{a:{complete:false,boundary:'confirmed',zeroPixel:435,curves:[{id:'a',name:'H',status:'missing_point'}]}}}
  const onContinue=vi.fn()
  render(<SpectrumMetrics item={data} curves={data.result.curves} history={false} onContinue={onContinue}/>)
  expect(screen.getByText('12')).toBeVisible();expect(screen.getByText('缺少原胞依据')).toBeVisible()
  fireEvent.click(screen.getByRole('button',{name:'继续核对 H'}));expect(onContinue).toHaveBeenCalledWith('a')
})
