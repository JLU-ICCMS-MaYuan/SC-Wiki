import { describe, expect, it } from 'vitest'
import { resolveReviewClassifications } from '../../frontend/src/lib/paperReview'

const pending = {
  paper: { material_families: [{ name: '新材料家族', status: 'pending' }], superconductor_kind: 'conventional' },
  material_states: [
    { state_key: 'b', material: 'Sn', material_dimensionality: 'three_dimensional', structure_families: [{ name: 'B', status: 'pending' }] },
    { state_key: 'a', material: 'Sn', structure_families: [{ name: 'A', status: 'pending', is_primary: true }] },
  ],
}
const detail = { review_status: 'pending', superconductor_kind: 'unconventional', material_families: [],
  material_states: [
    { id: 5, state_key: 'a', material_dimensionality: 'two_dimensional', structure_families: [] },
    { id: 6, state_key: 'b', material_dimensionality: 'unknown', structure_families: [] },
  ] }

describe('首次家族回填与正式数据边界', () => {
  it('首次回填按稳定状态 key 匹配，类型和维度始终读取当前详情', () => {
    const result = resolveReviewClassifications(detail, pending)
    expect(result.materialFamilies[0].name).toBe('新材料家族')
    expect(result.superconductorKind).toBe('unconventional')
    expect(result.materialStates.map(x => x.structure_families?.[0].name)).toEqual(['A', 'B'])
    expect(result.materialStates.map(x => x.material_dimensionality)).toEqual(['two_dimensional', 'unknown'])
  })
  it('保存后不恢复已清空的结构家族，也不覆盖已保存家族', () => {
    const result = resolveReviewClassifications({ ...detail, material_families: [{ id: 10, name: '已保存家族' }] }, pending)
    expect(result.materialFamilies.map(x => x.name)).toEqual(['已保存家族'])
    expect(result.materialStates.map(x => x.structure_families)).toEqual([[], []])
  })
  it('首次送审保留同一状态内已有结构关联和新家族候选', () => {
    const initial = { ...detail, material_states: [{ ...detail.material_states[0],
      structure_families: [{ id: 999, structure_family_id: 8, structure_family: { id: 8, name: '已有结构' }, is_primary: false }] }] }
    const snapshot = { ...pending, material_states: [{ state_key: 'a', structure_families: [
      { id: 8, name: '已有结构', status: 'confirmed' }, { name: '新结构', status: 'pending', is_primary: true },
    ] }] }
    expect(resolveReviewClassifications(initial, snapshot).materialStates[0].structure_families?.map(x => [x.id ?? null, x.name]))
      .toEqual([[8, '已有结构'], [null, '新结构']])
  })
  it('历史状态没有 key 时仅匹配唯一化学式，重复化学式不按位置猜测', () => {
    const legacy = { ...detail, material_states: [{ id: 5, superconductor: { chemical_formula: 'Sn' } }] }
    expect(resolveReviewClassifications(legacy, pending).materialStates[0].structure_families).toEqual([])
    expect(resolveReviewClassifications(legacy, { ...pending, material_states: [pending.material_states[1]] })
      .materialStates[0].structure_families?.[0].name).toBe('A')
  })
})
