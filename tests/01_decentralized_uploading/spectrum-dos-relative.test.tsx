import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import DosRelativeMetrics, { type DosRelativeReport } from '../../frontend/src/components/spectrumEditor/DosRelativeMetrics'
import { SpectrumMetrics } from '../../frontend/src/components/SpectrumDetailView'

afterEach(cleanup)
const report = (): DosRelativeReport => ({
  method:'dos-relative-v1',
  components:[{curve_id:'La',projection:'La',status:'available',area:4,frequency_interval_thz:[0,1]},
    {curve_id:'H',projection:'H',status:'available',area:5,frequency_interval_thz:[0,1]}],
  shares:{status:'available',total_area:9,fractions:{La:4/9,H:5/9},expected_fractions:{La:1/3,H:2/3}},
  normalization:{status:'available',coefficient:1,primitive_atoms:3,target_modes:9,total_mode_integral:9,
    component_mode_integrals:{La:4,H:5},expected_modes:{La:3,H:6},deviations:{
      La:{absolute_difference:1,relative_difference_pct:100/3},H:{absolute_difference:1,relative_difference_pct:100/6}}}
})
it('同一个系数保留元素偏差，归一化总和不显示验证通过',()=>{
  render(<DosRelativeMetrics report={report()} restricted={false}/>)
  const areas=screen.getByRole('table',{name:'DOS 相对面积'})
  expect(within(areas).getByText('44.44%')).toBeVisible()
  expect(within(areas).getByText('33.33%')).toBeVisible()
  const normalized=screen.getByRole('table',{name:'DOS 归一化模式积分'})
  for(const text of ['4','5','3','6','33.33%','16.67%'])expect(within(normalized).getByText(text)).toBeVisible()
  expect(screen.getByText(/不代表提取准确性已验证/)).toBeVisible()
  expect(screen.queryByText(/验证通过|满足判断/)).toBeNull()
})
it('没有N仍展示面积与比例，部分失败不隐藏其他面积',()=>{
  const r=report();r.normalization={status:'unavailable',reason:'缺少可信原胞原子数 N'}
  const {rerender}=render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByText('4',{exact:true})).toBeVisible()
  expect(screen.getByText('缺少可信原胞原子数 N')).toBeVisible()
  r.components[0]={curve_id:'La',projection:'La',status:'unavailable',reason:'曲线存在缺口'}
  r.shares={status:'unavailable',reason:'部分曲线不能积分'}
  rerender(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByText('5',{exact:true})).toBeVisible()
  expect(screen.getByText('曲线存在缺口')).toBeVisible()
  expect(screen.queryByText('55.56%')).toBeNull()
})
it('历史/失效结果和旧方法不混入当前归一化',()=>{
  const {rerender}=render(<DosRelativeMetrics report={report()} restricted/>)
  expect(screen.queryByRole('table')).toBeNull()
  rerender(<DosRelativeMetrics restricted={false}/>)
  expect(screen.getByText(/请点击重新计算/)).toBeVisible()
})
it('正式03同时展示相对、归一化与独立绝对结果，N不被单位失败隐藏',()=>{
  const item:any={review:{},stale:false,run:{id:'r'},result:{quality:{dos_relative:report(),dos_mode_integral:{status:'unavailable',reason:'没有独立刻度'}}}}
  const curves:any=[{id:'La',kind:'phonon_dos',points:[{frequency_thz:0,observed_amplitude:0},{frequency_thz:1,observed_amplitude:0}]}]
  render(<SpectrumMetrics item={item} curves={curves} history={false}/>)
  expect(screen.getByText('3 / 9')).toBeVisible()
  expect(screen.getByText('原始绝对密度积分（独立检查）')).toBeVisible()
  expect(screen.getByRole('table',{name:'DOS 相对面积'})).toBeVisible()
  expect(screen.getByText('没有独立刻度')).toBeVisible()
})
