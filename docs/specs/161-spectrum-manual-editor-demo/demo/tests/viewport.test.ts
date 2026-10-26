import { expect, it } from 'vitest'
import { fitViewport, zoomViewport, wheelFactor, wheelPixels } from '../src/viewport'
import type { Rect } from '../src/engine'

const crop: Rect = [632,8,170,460]
it('不同窗口下保留固定屏幕文字留白并完整包含原图子图', () => {
  for (const [width,height] of [[1000,700],[380,450],[230,350]]) {
    const [x,y,w,h]=fitViewport(crop,width,height), scale=width/w
    expect(width/w).toBeCloseTo(height/h)
    expect((crop[0]-x)*scale).toBeGreaterThanOrEqual(64-.00001)
    expect((crop[1]-y)*scale).toBeGreaterThanOrEqual(36-.00001)
    expect((crop[0]+crop[2]-x)*scale).toBeLessThanOrEqual(width-18+.00001)
    expect((crop[1]+crop[3]-y)*scale).toBeLessThanOrEqual(height-48+.00001)
  }
})
it('关闭轴后保留少量边距，不浪费轴文字空间', () => {
  expect(fitViewport(crop,380,450,false)[3]).toBeLessThan(fitViewport(crop,380,450,true)[3])
})
it('小步按钮可逆，缩放过程中鼠标锚点保持屏幕位置', () => {
  const fit=fitViewport(crop,600,500), anchor={x:690,y:250}
  const next=zoomViewport(fit,fit,1.05,anchor)
  expect(next[2]/fit[2]).toBeCloseTo(1.05)
  expect((anchor.x-next[0])/next[2]).toBeCloseTo((anchor.x-fit[0])/fit[2])
  expect((anchor.y-next[1])/next[3]).toBeCloseTo((anchor.y-fit[1])/fit[3])
  zoomViewport(next,fit,1/1.05,anchor).forEach((n,i)=>expect(n).toBeCloseTo(fit[i]))
})
it('微小滚动微调，大量或连续滚动更快，单位归一化一致', () => {
  expect(wheelFactor(2)-1).toBeLessThan(.001)
  expect(wheelFactor(120)-1).toBeGreaterThan(.04)
  expect(wheelFactor(40)**3).toBeCloseTo(wheelFactor(120))
  expect(wheelFactor(-120)*wheelFactor(120)).toBeCloseTo(1)
  expect(wheelPixels(1,1,500)).toBe(16);expect(wheelPixels(1,2,500)).toBe(500)
})
