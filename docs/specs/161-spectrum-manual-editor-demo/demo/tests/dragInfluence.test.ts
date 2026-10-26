import { expect, it } from 'vitest'
import { createInfluenceKernel, DRAG_INFLUENCE } from '../src/dragInfluence'

it('默认两侧各3点，中心不变，邻点温和减小后进入指数尾部', () => {
  const weights = createInfluenceKernel(DRAG_INFLUENCE)
  expect(weights.slice(0,4)).toEqual([1,1-.4/3,1-.8/3,.6])
  expect(weights[4]).toBeCloseTo(.6*Math.exp(-.5))
  expect(weights).toHaveLength(16)
})
it('调小跟随比例会减小附近和尾部位移，调小衰减长度只加快尾部收敛', () => {
  const normal = createInfluenceKernel(DRAG_INFLUENCE)
  const weaker = createInfluenceKernel({...DRAG_INFLUENCE, edgeWeight:.3})
  const faster = createInfluenceKernel({...DRAG_INFLUENCE, decayLength:1})
  expect(weaker[0]).toBe(1); expect(weaker[1]).toBeLessThan(normal[1]); expect(weaker[4]).toBeLessThan(normal[4])
  expect(faster.slice(0,4)).toEqual(normal.slice(0,4)); expect(faster[4]).toBeCloseTo(.6*Math.exp(-1))
  expect(faster.length).toBeLessThan(normal.length)
})
it('修改邻点数或截断值有效，拒绝错误或过大的手工参数', () => {
  expect(createInfluenceKernel({...DRAG_INFLUENCE, coreNeighbors:5})[5]).toBe(.6)
  expect(createInfluenceKernel({...DRAG_INFLUENCE, minWeight:.01}).length).toBeLessThan(16)
  for (const change of [{coreNeighbors:0},{edgeWeight:2},{decayLength:0},{minWeight:0},{decayLength:Infinity},{decayLength:10000}]) {
    expect(()=>createInfluenceKernel({...DRAG_INFLUENCE,...change})).toThrow()
  }
})
