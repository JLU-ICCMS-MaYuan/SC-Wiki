import { beforeEach, expect, it, vi } from 'vitest'
import { candidateFromStructureModel, remapScientificIdentities } from '../../frontend/src/lib/paperEditing'
import { saveQuickReviewProposals } from '../../frontend/src/lib/paperProposalSave'
import { api } from '../../frontend/src/lib/api'
import { loadPaperReviewSource } from '../../frontend/src/lib/paperReview'

vi.mock('../../frontend/src/lib/api', () => ({ api: { put: vi.fn() } }))
vi.mock('../../frontend/src/lib/paperReview', () => ({
  loadPaperReviewSource: vi.fn(),
  resolveReviewClassifications: () => ({ superconductorKind: 'unknown', materialFamilies: [], materialStates: [{}] }),
}))

beforeEach(() => vi.clearAllMocks())

it.each(['cif', 'poscar'])('已有 %s 结构按实际格式回传，不冒充其他格式', (format) => {
  const candidate = candidateFromStructureModel({ id: 8, structure_format: format, structure_text: 'original' }, 'material_states[0]')
  expect(candidate.original_format).toBe(format)
  expect(candidate.representations?.conventional).toEqual({ [format]: { text: 'original', available: true } })
  expect(candidate.sources?.[0].filename).toBe(`structure_8.${format}`)
})

it('快速审核修改压强时携带既有 POSCAR 的格式、原文和身份', async () => {
  vi.mocked(loadPaperReviewSource).mockResolvedValue({ detail: {
    id: 12, paper_type: 'experimental', material_states: [{
      state_key: 'sample', material: 'Si', property_modules: [],
      structures: [{ id: 8, structure_format: 'poscar', structure_text: 'Si POSCAR' }],
    }],
  } } as any)
  await saveQuickReviewProposals(12, [{ key: 'p', item_key: 'sample', field: 'material_states[0].pressure', state_key: 'sample', values: { pressure_value_gpa: 2 } }], 'prepared')
  const payload = vi.mocked(api.put).mock.calls.find(([path]) => path.includes('scientific-draft'))?.[1] as any
  expect(payload.evidence_preparation_id).toBe('prepared')
  expect(payload.structure_candidates[0]).toMatchObject({ candidate_id: 'structure_8', original_format: 'poscar', original_text: 'Si POSCAR', representations: { conventional: { poscar: { text: 'Si POSCAR' } } } })
  expect(payload.structure_candidates[0].representations.conventional.cif).toBeUndefined()
})

it('连续映射只更新结构身份，不覆盖等待保存期间的新值或新增候选', () => {
  const record = { record_key: 'tc', structure_key: 'structure-1', value_number: 15 }
  const states = [{ pressure_value_gpa: 8, property_modules: [{ module_key: 'm', records: [record, { ...record, record_key: 'deleted-link', structure_key: 'structure-3' }] }] }] as any
  const candidates = [{ candidate_id: 'structure_1', confirmation: 'excluded' }, { candidate_id: 'added-later' }]
  const result = remapScientificIdentities(states, candidates, {
    structure_candidate_id_map: { structure_1: 'structure_2', structure_2: 'structure_4' },
    structure_key_map: { 'structure-1': 'structure-2', 'structure-2': 'structure-4', 'structure-3': null },
  })
  expect(result.states[0]).toMatchObject({ pressure_value_gpa: 8, property_modules: [{ records: [{ value_number: 15, structure_key: 'structure-4' }, { structure_key: null }] }] })
  expect(result.candidates).toEqual([{ candidate_id: 'structure_4', confirmation: 'excluded' }, { candidate_id: 'added-later' }])
  expect(record.structure_key).toBe('structure-1')
})
