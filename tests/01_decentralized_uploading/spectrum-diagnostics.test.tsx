import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import TraceDiagnostics, {type TraceReport} from '../../frontend/src/components/spectrumEditor/TraceDiagnostics'

afterEach(cleanup)
function report(count=1):TraceReport {
  return {curves:[{curve_id:'Sc',name:'Sc',amplitude_unit:'pixel',component_count:count,point_count:count,
    issues:Array.from({length:count},(_,i)=>({kind:'isolated',message:'未连接点',points:[{point_id:'p'+i,frequency_thz:i,amplitude:5,x:42+i,y:20}]}))}]}
}
it('坐标携带正确曲线与稳定点ID，不按近邻猜测',()=>{
  const locate=vi.fn();render(<TraceDiagnostics report={report()} onLocate={locate}/>)
  fireEvent.click(screen.getByRole('button',{name:'原图 (x=42, y=20) px'}))
  expect(locate).toHaveBeenCalledTimes(1);expect(locate).toHaveBeenCalledWith('Sc','p0')
  expect(screen.getByText('频率 0 THz · 幅值 5 相对像素')).toBeVisible()
})
it('分页最多12项，所有问题可访问',()=>{
  render(<TraceDiagnostics report={report(25)} onLocate={()=>{}}/>)
  expect(document.querySelectorAll('[data-diagnostic-point]')).toHaveLength(12)
  fireEvent.click(screen.getByRole('button',{name:'下一页'}))
  expect(document.querySelector('[data-diagnostic-point="p12"]')).not.toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'下一页'}))
  expect(document.querySelectorAll('[data-diagnostic-point]')).toHaveLength(1)
  expect(screen.getByText('3 / 3')).toBeVisible()
})
it('只读、忙碌或缺坐标时不能定位',()=>{
  const data=report(2);data.curves[0].issues[1].points[0].x=null
  const locate=vi.fn();const {rerender}=render(<TraceDiagnostics report={data} onLocate={locate}/>)
  expect(screen.getByRole('button',{name:'原图 (x=未知, y=20) px'})).toBeDisabled()
  rerender(<TraceDiagnostics report={data} onLocate={locate} disabled/>)
  fireEvent.click(screen.getByRole('button',{name:'原图 (x=42, y=20) px'}))
  expect(locate).not.toHaveBeenCalled()
})


it('历史保存的高频末端和分波截止诊断不再显示',()=>{
 const data=report()
 data.curves[0].issues=[{kind:'high_endpoint',message:'旧高端限制',points:[]},{kind:'projection_range',message:'旧分波截止限制',points:[]}]
 render(<TraceDiagnostics report={data} onLocate={()=>{}}/>)
 expect(screen.queryByTestId('trace-diagnostics')).toBeNull()
})
