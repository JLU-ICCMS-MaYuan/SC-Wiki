import { api, type ApiError } from './api'
import type { FamilySelection } from './classifications'
import type { DraftMaterialState } from './paperProcessing'

export const PAPER_REVIEW_OPTIONS = [
  { value: 'approved', label: 'admin.reviewApprove' },
  { value: 'pending', label: 'admin.reviewBackToPending' },
  { value: 'rejected', label: 'admin.reviewReject' },
] as const

export const initialPaperReviewStatus = (status?: string) => status === 'rejected' ? 'rejected' : 'pending'

export interface ReviewClassifications {
  superconductorKind: string
  materialFamilies: FamilySelection[]
  materialStates: Array<Pick<DraftMaterialState, 'material_dimensionality' | 'structure_families'> & { id?: number }>
}

export async function loadPaperReviewSource(paperId: number | string) {
  const detail = await api.get<Record<string, any>>(`/api/admin/papers/${paperId}`)
  let pendingValues: Record<string, any> | null = null
  if (detail.review_status === 'pending') {
    try {
      const artifact = await api.get<{ data?: { user_values?: Record<string, any> } }>(
        `/api/rag/papers/${paperId}/review-artifact`,
      )
      pendingValues = artifact?.data?.user_values || null
    } catch (error) {
      // 没有待审快照时使用正式详情；读取失败不能被误认为快照不存在。
      if ((error as ApiError).status !== 404) throw error
    }
  }
  return { detail, pendingValues }
}

export function resolveReviewClassifications(
  detail: Record<string, any>, pendingValues: Record<string, any> | null,
): ReviewClassifications {
  const pendingFamilies = pendingValues?.paper?.material_families
  const families = Array.isArray(pendingFamilies) ? pendingFamilies : (detail.material_families || [])
  return {
    superconductorKind: pendingValues?.paper?.superconductor_kind ?? detail.superconductor_kind ?? 'unknown',
    materialFamilies: families.map((family: any) => ({
      id: family.id ?? null,
      name: family.name || family.name_zh || '',
      name_zh: family.name_zh || family.name || '',
      name_en: family.name_en || '',
      status: family.status === 'pending' ? 'pending' : 'confirmed',
    })),
    materialStates: (detail.material_states || []).map((state: any, index: number) => {
      const pending = pendingValues?.material_states?.[index]
      const structureFamilies = Array.isArray(pending?.structure_families)
        ? pending.structure_families
        : (state.structure_families || []).map((link: any) => ({
          id: link.id ?? link.structure_family_id,
          name: link.structure_family?.name || link.name || '',
          name_zh: link.structure_family?.name_zh || link.structure_family?.name || link.name || '',
          name_en: link.structure_family?.name_en || link.name_en || '',
          status: 'confirmed', is_primary: Boolean(link.is_primary),
        }))
      return {
        id: state.id,
        material_dimensionality: pending?.material_dimensionality || state.material_dimensionality || 'unknown',
        structure_families: structureFamilies,
      }
    }),
  }
}

export function paperReviewPayload(status: string, comment: string, classifications?: ReviewClassifications) {
  if (status === 'approved' && !classifications) throw new Error('Approval classifications are required')
  return {
    status, comment, review_request_id: crypto.randomUUID(),
    ...(status === 'approved' && classifications ? {
      superconductor_kind: classifications.superconductorKind,
      material_families: classifications.materialFamilies.map(family => ({ id: family.id || null, name: family.name })),
      material_states: classifications.materialStates.map(state => ({
        id: state.id,
        material_dimensionality: state.material_dimensionality || 'unknown',
        structure_families: (state.structure_families || []).map(family => ({
          id: family.id || null, name: family.name || '', is_primary: Boolean(family.is_primary),
        })),
      })),
    } : {}),
  }
}
