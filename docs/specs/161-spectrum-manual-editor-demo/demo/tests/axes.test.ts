import { describe, expect, it } from 'vitest'
import fixtures from '../src/fixtures.json'
import { currentTicks, pointReadout, recognizedAxes, zeroReadout } from '../src/axisGeometry'
import { clone, markZero, addPoint, type Document } from '../src/engine'

const alpha = fixtures[0] as unknown as Document
describe('识别刻度与坐标读数', () => {
  it('已有识别位置原样保留，不用当前等分刻度替代', () => {
    expect(recognizedAxes(alpha)!.frequencyTicks).toEqual([[435,0],[311,20],[188,40],[65,60]])
    const current = currentTicks(alpha.calibration.frequency,17,435)
    expect(current.map(t=>t.value)).toEqual([0,15,30,45,60])
    expect(recognizedAxes({...alpha,source:{...alpha.source,sha256:'other'}})).toBeNull()
  })
  it('点读数区分换算频率和距离零线的源像素', () => {
    const p={id:'point',segment:'s',status:'人工补选',x:641,y:434.9}
    const reading=pointReadout(alpha,p)
    expect(reading.x).toBe(641);expect(reading.y).toBe(434.9)
    expect(reading.frequency).toBeCloseTo(.1*60/370);expect(reading.distanceToZeroPx).toBeCloseTo(.1)
    expect(reading.amplitude).toBe(4)
  })
  it('人工标零显示与原识别零刻度的差异，但不改识别记录', () => {
    const doc=markZero(alpha,640,434.8), reading=zeroReadout(doc)
    expect(reading.zeroPixel).toBeCloseTo(434.8);expect(reading.originalZero).toBe(435)
    expect(reading.differencePx).toBeCloseTo(-.2);expect(reading.markedValue).toBeCloseTo(0)
    expect(recognizedAxes(doc)!.frequencyTicks[0]).toEqual([435,0])
    expect(doc.curves).toEqual(alpha.curves)
  })
  it('改频率单位只改变当前标定，初始识别仍为THz', () => {
    const doc=clone(alpha);doc.calibration.frequency.values=[0,600];doc.calibration.frequency.unit='meV'
    expect(currentTicks(doc.calibration.frequency,17,435).at(-1)!.value).toBe(600)
    expect(recognizedAxes(doc)!.frequencyUnit).toBe('THz')
  })
  it('频率横轴时读数和零线使用X像素，原竖轴不冒充同轴对比', () => {
    const doc=clone(alpha);doc.calibration.direction='x';doc.calibration.frequency.pixels=[637,790]
    const p={id:'point',segment:'s',status:'人工补选',x:637,y:300}
    expect(pointReadout(doc,p).frequency).toBe(0);expect(pointReadout(doc,p).distanceToZeroPx).toBe(0)
    expect(zeroReadout(doc).originalZero).toBeNull()
  })
  it('不在图框里的零刻度不伪造在边界，刻度始终有界', () => {
    const ticks=currentTicks({pixels:[0,100],values:[10,20],unit:'THz'},0,100)
    expect(ticks.some(t=>t.value===0)).toBe(false);expect(ticks.every(t=>t.pixel>=0&&t.pixel<=100)).toBe(true)
  })
})


it('原图边框上的零频点击容忍浮点变换噪声，真实图外点击仍拒绝', () => {
  expect(markZero(alpha,640,435+1.2e-5).zero!.pixel).toBe(435)
  expect(addPoint(alpha,'alpha',641,435+1.2e-5).curves[0].points.some(p=>p.x===641&&p.y===435)).toBe(true)
  expect(()=>markZero(alpha,640,435.01)).toThrow('图框内')
  expect(()=>addPoint(alpha,'alpha',641,435.01)).toThrow('图框内')
})
