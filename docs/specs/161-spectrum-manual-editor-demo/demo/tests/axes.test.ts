import { describe, expect, it } from 'vitest'
import fixtures from '../src/fixtures.json'
import { currentTicks, pointReadout, recognizedAxes } from '../src/axisGeometry'
import { clone, addPoint, type Document } from '../src/engine'

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
    expect(reading.frequency).toBeCloseTo(.1*60/370)
    expect(reading.amplitude).toBe(4)
  })

  it('改频率单位只改变当前标定，初始识别仍为THz', () => {
    const doc=clone(alpha);doc.calibration.frequency.values=[0,600];doc.calibration.frequency.unit='meV'
    expect(currentTicks(doc.calibration.frequency,17,435).at(-1)!.value).toBe(600)
    expect(recognizedAxes(doc)!.frequencyUnit).toBe('THz')
  })

  it('不在图框里的零刻度不伪造在边界，刻度始终有界', () => {
    const ticks=currentTicks({pixels:[0,100],values:[10,20],unit:'THz'},0,100)
    expect(ticks.some(t=>t.value===0)).toBe(false);expect(ticks.every(t=>t.pixel>=0&&t.pixel<=100)).toBe(true)
  })
})
