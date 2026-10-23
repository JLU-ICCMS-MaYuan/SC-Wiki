import { expect, it } from 'vitest'
import { spectrumGeometry, spectrumPixelPath } from '../../frontend/src/lib/spectrumGeometry'
import type { PropertySpectrumCurve } from '../../frontend/src/lib/propertySpectra'

const curve = (): PropertySpectrumCurve => ({ id:'alpha',kind:'alpha2f',unit:'dimensionless',frequency_direction:'y',roi:[62,20,88,69],
  axis_calibration:{frequency:{slope:-1,intercept:70},amplitude:{slope:.1,intercept:-6}},
  points:[{frequency_thz:50,frequency_pixel:20,observed_amplitude:1,reconstructed_amplitude:1,status:'observed'},
    {frequency_thz:40,frequency_pixel:30,observed_amplitude:null,reconstructed_amplitude:null,status:'missing'},
    {frequency_thz:30,frequency_pixel:40,observed_amplitude:2,reconstructed_amplitude:2,status:'observed'}] })

function image() {
  const width=110,height=150,pixels=new Uint8ClampedArray(width*height*4).fill(255)
  const dark=(x:number,y:number)=>{const at=(y*width+x)*4;pixels[at]=pixels[at+1]=pixels[at+2]=0}
  for (const [x0,y0,x1,y1] of [[60,10,90,70],[60,95,90,145],[20,10,48,70]]) {
    for(let x=x0;x<=x1;x++){dark(x,y0);dark(x,y1)}
    for(let y=y0;y<=y1;y++){dark(x0,y);dark(x1,y)}
  }
  return {width,height,pixels}
}
it('提取框遗漏顶部时恢复外框，裁切不含下一压力行或相邻面板',()=>{
  const {width,height,pixels}=image(),g=spectrumGeometry([curve()],width,height,pixels)!
  expect(g.method).toBe('frame')
  expect(g.plot).toEqual([60,10,90,70])
  expect(g.crop[0]).toBeGreaterThan(48)
  expect(g.crop[3]).toBeLessThan(95)
  expect((g.plot[2]-g.plot[0])/(g.plot[3]-g.plot[1])).toBe(.5)
})
it('整页模型裁切候选不覆盖确定的子图范围',()=>{
  const {width,height,pixels}=image(),c=curve();c.display_bbox=[0,0,109,149]
  const g=spectrumGeometry([c],width,height,pixels)!
  expect(g.crop[0]).toBeGreaterThan(48);expect(g.crop[3]).toBeLessThan(95)
})
it('没有可辨边框时明确退回 ROI，不把大块背景当成已确认图框',()=>{
  const {width,height}=image()
  const blank=new Uint8ClampedArray(width*height*4).fill(255)
  expect(spectrumGeometry([curve()],width,height,blank)?.method).toBe('roi')
  expect(spectrumGeometry([{...curve(),roi:undefined}],width,height,blank)).toBeNull()
})
it('同一全局像素路径用于数据与叠加，缺口不能被连接',()=>{
  const c=curve(),path=spectrumPixelPath(c)
  expect(path).toBe('M70,20 M80,40 ')
  c.frequency_direction='x'
  expect(spectrumPixelPath(c)).toBe('M20,70 M40,80 ')
})
