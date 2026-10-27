import React from 'react'
import { afterEach,it,expect } from 'vitest'
import { render,screen,cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import AlphaRelativeMetrics from '../../frontend/src/components/spectrumEditor/AlphaRelativeMetrics'
import { createInfluenceKernel } from '../../frontend/src/components/spectrumEditor/dragInfluence'

afterEach(cleanup)
const raw=()=>({method:'alpha2f-relative-v2',pixel_integral:100,parameters:{omega_log:{status:'available',value:200}},
 normalization:{status:'available',lambda_reference:2,coefficient:.02,lambda_normalized:2}})
it('只比较ωlog并展示论文λ/像素积分/C，没有λ准确度表或通过门槛',()=>{
 render(<AlphaRelativeMetrics raw={raw()} comparison={{status:'available',reference:50,absolute_difference:150,relative_difference_pct:300}} restricted={false}/>)
 for(const text of ['200','50','150','300','论文 λ（归一化输入）','像素加权积分','幅值系数 C','0.02','依据论文 λ 归一化'])expect(screen.getByText(text)).toBeVisible()
 expect(screen.queryByText('λ',{exact:true})).toBeNull()
 expect(screen.queryByText(/通过|不通过/)).toBeNull()
})
it('缺λ不隐藏ωlog，缺ω参考不隐藏归一化',()=>{
 const data=raw();data.normalization={status:'unavailable',reason:'缺少论文λ'} as any
 const {rerender}=render(<AlphaRelativeMetrics raw={data} comparison={{reference:100,status:'available',absolute_difference:100,relative_difference_pct:100}} restricted={false}/>)
 expect(screen.getByText('200')).toBeVisible();expect(screen.getByText('缺少论文λ')).toBeVisible()
 rerender(<AlphaRelativeMetrics raw={raw()} comparison={{status:'unavailable',reason:'缺少论文ωlog'}} restricted={false}/>)
 expect(screen.getByText('200')).toBeVisible();expect(screen.getByText('依据论文 λ 归一化')).toBeVisible()
 expect(screen.getByText('缺少论文ωlog')).toBeVisible()
})
it('论文ω参考为零时保留计算值及绝对差，不生成无穷大',()=>{
 render(<AlphaRelativeMetrics raw={raw()} comparison={{status:'available',reference:0,absolute_difference:200,relative_difference_pct:null}} restricted={false}/>)
 expect(screen.getByText('0',{exact:true})).toBeVisible()
 expect(screen.getByText('不适用（参考为0）')).toBeVisible()
 expect(screen.queryByText(/Infinity|无穷/)).toBeNull()
})
it('核心边缘与截断相等时保留用户比例，外围全部截断',()=>{
 const weights=createInfluenceKernel({coreNeighbors:2,edgeWeight:.1,decayLength:1,minWeight:.1})
 expect(weights).toEqual([1,.55,.1])
})
