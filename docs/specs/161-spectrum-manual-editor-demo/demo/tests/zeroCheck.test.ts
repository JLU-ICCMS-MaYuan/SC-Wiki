import { expect, it } from 'vitest'
import fixtures from '../src/fixtures.json'
import { addPoint, clone, markZero, move, removePoints, type Document } from '../src/engine'
import { checkZeroFrequency, confirmCurrentZeroBoundary, confirmExistingZeroPoint } from '../src/zeroCheck'

const initial = fixtures[0] as unknown as Document
const confirmed = () => addPoint(confirmCurrentZeroBoundary(clone(initial)), 'alpha', 641, 435, true)

it('仅有识别标定不会自动成为人工核对，候选点仍保留', () => {
  const doc = addPoint(clone(initial),'alpha',641,435)
  const check = checkZeroFrequency(doc)
  expect(check.boundary).toBe('missing');expect(check.complete).toBe(false)
  expect(check.curves[0].pointId).toBeTruthy()
  expect(()=>confirmExistingZeroPoint(doc,'alpha',check.curves[0].pointId!)).toThrow('请先')
})
it('确认当前蓝线不改标定和点，只标线仍不完成', () => {
  const doc=confirmCurrentZeroBoundary(initial), check=checkZeroFrequency(doc)
  expect(doc.curves).toBe(initial.curves);expect(doc.calibration).toBe(initial.calibration)
  expect(check.boundary).toBe('confirmed');expect(check.curves[0].status).toBe('missing_point')
})
it('普通零频点需要明确确认，可复用已有点且坐标不变', () => {
  const doc=addPoint(confirmCurrentZeroBoundary(initial),'alpha',641,435)
  const check=checkZeroFrequency(doc);expect(check.curves[0].status).toBe('needs_confirmation')
  const next=confirmExistingZeroPoint(doc,'alpha',check.curves[0].pointId!)
  expect(next.curves).toBe(doc.curves);expect(checkZeroFrequency(next).complete).toBe(true)
  expect(checkZeroFrequency(JSON.parse(JSON.stringify(next)))).toEqual(checkZeroFrequency(next))
})
it('旧的图上标线和零频补点可直接完成，不要求重复确认', () => {
  const doc=addPoint(markZero(initial,640,435),'alpha',641,435,true)
  expect(checkZeroFrequency(doc).complete).toBe(true)
})
it('近零不伪造为零；确认失败不改坐标', () => {
  const doc=addPoint(confirmCurrentZeroBoundary(initial),'alpha',641,434.9)
  const check=checkZeroFrequency(doc), before=JSON.stringify(doc)
  expect(check.curves[0].status).toBe('missing_point');expect(check.curves[0].nearest!.distancePx).toBeCloseTo(.1)
  expect(()=>confirmExistingZeroPoint(doc,'alpha',check.curves[0].nearest!.id)).toThrow('不会自动移动')
  expect(JSON.stringify(doc)).toBe(before)
})
it('删除或移走已确认零点会使新快照检查失效，旧快照不变', () => {
  const doc=confirmed(), id=doc.zero!.pointIds[0]
  expect(checkZeroFrequency(removePoints(doc,'alpha',[id])).complete).toBe(false)
  expect(checkZeroFrequency(move(doc,'alpha',id,0,-1,false,'free')).complete).toBe(false)
  expect(checkZeroFrequency(doc).complete).toBe(true)
})
it('修改标定清除边界记录后重新待核对，不沿用旧完成结果', () => {
  const doc=confirmed();expect(checkZeroFrequency({...doc,zero:null}).boundary).toBe('missing')
  const wrong=clone(doc);wrong.calibration.frequency.values=[1,61]
  expect(checkZeroFrequency(wrong).boundary).toBe('invalid')
})
it('PhDOS每个分波独立，只有全部完成才整体完成', () => {
  let doc=confirmCurrentZeroBoundary(clone(fixtures[1] as unknown as Document))
  doc=addPoint(doc,'H',480,435,true)
  let check=checkZeroFrequency(doc);expect(check.completedCount).toBe(1);expect(check.complete).toBe(false)
  expect(check.curves.find(c=>c.id==='La')!.status).toBe('missing_point')
  doc=addPoint(doc,'La',475,435,true);doc=addPoint(doc,'Sc',478,435,true)
  check=checkZeroFrequency(doc);expect(check.complete).toBe(true);expect(check.completedCount).toBe(3)
})
it('空曲线、零线在图框外均不能报告完成', () => {
  expect(checkZeroFrequency({...initial,curves:[]}).complete).toBe(false)
  const doc=clone(initial);doc.calibration.frequency.values=[10,70]
  expect(()=>confirmCurrentZeroBoundary(doc)).toThrow('不在图框')
  expect(checkZeroFrequency(doc).boundary).toBe('invalid')
})
