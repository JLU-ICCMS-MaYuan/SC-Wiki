import { api } from './api'
import { applyEvidencePatches, type EvidencePatch } from './evidenceProposals'
import { materialStateFromDetail, candidateFromStructureModel } from './paperEditing'
import { loadPaperReviewSource, needsReviewClassificationSave, resolveReviewClassifications } from './paperReview'

/** 快速审核复用编辑器转换与原有两段保存接口，结构候选完整保留。 */
export async function saveQuickReviewProposals(paperId: number, patches: EvidencePatch[], preparationId?: string, resumeStage?: 'scientific' | 'finalize') {
  const { detail, pendingValues } = await loadPaperReviewSource(paperId)
  const classifications = resolveReviewClassifications(detail, pendingValues)
  const states: Record<string, any>[] = detail.material_states || []
  const paper: Record<string, any> = { ...detail, material_families: classifications.materialFamilies }
  const draft = applyEvidencePatches({ paper,
    material_states: states.map((state, index) => materialStateFromDetail(state, classifications.materialStates[index])) }, patches)
  const history_operation_id = crypto.randomUUID()
  const metadata: Record<string, unknown> = { ...draft.paper, history_operation_id, evidence_preparation_id: preparationId }
  if (states.length || draft.paper.material_families?.length) delete metadata.superconductor_kind
  delete metadata.key_properties
  for (const [key, value] of Object.entries(metadata)) {
    if (Array.isArray(value) && ['authors', 'keywords_tags', 'methodology', 'research_materials', 'material_relations'].includes(key)) metadata[key] = JSON.stringify(value)
  }
  if (resumeStage !== 'scientific') await api.put(`/api/admin/papers/${paperId}`, metadata)
  if (states.length || draft.paper.material_families?.length) {
    try {
      await api.put(`/api/rag/papers/${paperId}/scientific-draft`, {
        paper_type: draft.paper.paper_type, superconductor_kind: draft.paper.superconductor_kind || classifications.superconductorKind,
        material_families: draft.paper.material_families, material_states: draft.material_states,
        structure_candidates: states.flatMap((state, index) => (state.structures || []).map((model: any) => candidateFromStructureModel(model, `material_states[${index}]`))),
        history_operation_id, evidence_preparation_id: preparationId,
      })
    } catch (error) { throw new Error(`科学数据保存失败，审核未提交：${(error as Error).message}`) }
  }
  return true
}

/** 首次待审分类先走科学保存，核对和批准随后使用正式目录及状态 ID。 */
export async function saveInitialReviewClassifications(paperId: number) {
  const { detail, pendingValues } = await loadPaperReviewSource(paperId)
  if (needsReviewClassificationSave(detail, pendingValues)) {
    await saveQuickReviewProposals(paperId, [], undefined, 'scientific')
  }
}
