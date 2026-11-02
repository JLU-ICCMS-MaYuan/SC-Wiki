import type { StructureCandidate } from './paperProcessing'

const views = new WeakMap<object, Map<string, StructureCandidate>>()
/** 旧查看组件的只读内存投影；业务草稿只保存state.structure。 */
export function canonicalStructureView(structure: any, stateKey: string, index: number): StructureCandidate | null {
  if (!structure?.structure_text) return null
  const key = stateKey + ':' + index
  const cached = views.get(structure)?.get(key)
  if (cached) return cached
  const originalFormat = String(structure.structure_format || 'cif')
  const representations = structure.representations || { conventional: {
    [originalFormat]: { text: structure.structure_text, available: true, format: originalFormat } } }
  const view: StructureCandidate = {
    candidate_id: structure.review_key || structure.structure_hash || stateKey,
    material_state_ref: 'material_states[' + index + ']', source_kind: 'attachment',
    status: 'confirmed', confirmation: 'confirmed', retention: 'retained',
    original_format: originalFormat, original_text: structure.structure_text,
    representations, sources: structure.sources || [], validation: structure.validation || {},
    derivation: structure.derivation, user_note: structure.user_note,
  }
  if (!views.has(structure)) views.set(structure, new Map())
  views.get(structure)!.set(key, view)
  return view
}
function stableValidation(value: any): any {
  if (!value?.cell_parameters) return value || {}
  const cells = { ...value.cell_parameters }
  for (const key of ['alpha','beta','gamma']) {
    const angle = cells[key]
    if (typeof angle === 'number' && Math.abs(angle - Math.round(angle)) <= 1e-12) cells[key] = Math.round(angle)
  }
  return { ...value, cell_parameters: cells }
}
export function canonicalStructureFromCandidate(candidate: StructureCandidate): Record<string, any> {
  const conventional = candidate.representations?.conventional?.cif
  const text = conventional?.text || candidate.original_text
  if (!text || candidate.status === 'blocked') throw new Error('结构尚未通过完整几何校验')
  const representations = Object.fromEntries(Object.entries(candidate.representations || {}).map(([cell, formats]) => [cell,
    Object.fromEntries(Object.entries(formats || {}).map(([format, value]) => [format, { ...value, validation: stableValidation(value?.validation) }]))]))
  return {
    structure_format: conventional?.text ? 'cif' : candidate.original_format,
    structure_text: text, review_key: (candidate as any).review_key || candidate.candidate_id,
    structure_hash: conventional?.validation?.structure_hash || candidate.validation?.structure_hash,
    sources: candidate.sources || [], validation: stableValidation(conventional?.validation || candidate.validation),
    representations, derivation: candidate.derivation,
    user_note: candidate.user_note,
  }
}
