import { type ReviewClassifications } from './paperReview'
import { type DraftMaterialState, type StructureCandidate } from './paperProcessing'
import { convertLegacyPropertyModules, PROPERTY_SCHEMA_VERSION } from './propertyModules'
/**
 * Go 详情行的材料状态 → 共享编辑器（MaterialStatesEditor）的 DraftMaterialState（T020）。
 * Go 侧返回的是模型序列化：化学式在 superconductor.chemical_formula，
 * structure_families 是 {id, is_primary, structure_family:{...}} 的链接行，
 * 需要转成编辑器的 {id, name, status, is_primary} 选择形态。
 * （原 AdminPage.tsx 弹窗逻辑迁移，Issue #78。）
 */
export const materialStateFromDetail = (
  state: Record<string, any>, classification: ReviewClassifications['materialStates'][number],
): DraftMaterialState => {
  const stateWithoutLegacyProperties = { ...state }
  delete stateWithoutLegacyProperties.superconductor_kind
  delete stateWithoutLegacyProperties.tc_results
  delete stateWithoutLegacyProperties.calculation_contexts
  delete stateWithoutLegacyProperties.calculation_context
  delete stateWithoutLegacyProperties.experimental_context
  delete stateWithoutLegacyProperties.properties
  delete stateWithoutLegacyProperties.key_properties
  return {
    ...stateWithoutLegacyProperties,
    ...classification,
    material_name: state.material_name || null,
    material: typeof state.material === 'string' ? state.material : state.superconductor?.chemical_formula || '',
    structure_families: classification.structure_families || [],
    property_modules: convertLegacyPropertyModules(state),
    deleted_record_keys: [],
    deleted_module_keys: [],
    schema_version: PROPERTY_SCHEMA_VERSION,
  }
}

/**
 * Go 已落库的结构模型 → 已确认候选（T020）。
 * 科学数据保存是整体替换（契约 C1）：既有结构必须并入候选列表，
 * 否则保存时会被整体删除重建流程丢掉。
 * （原 AdminPage.tsx 弹窗逻辑迁移，Issue #78。）
 */
export const candidateFromStructureModel = (model: Record<string, any>, ref: string): StructureCandidate => ({
  candidate_id: `structure_${model.id}`,
  material_state_ref: ref,
  source_kind: 'attachment',
  status: 'confirmed',
  confirmation: 'confirmed',
  original_format: model.structure_format || 'cif',
  original_text: model.structure_text || null,
  validation: {
    structure_format: model.structure_format || 'cif',
    atom_count: model.atom_count ?? undefined,
    volume: model.volume_angstrom3 ?? undefined,
    cell_parameters: model.cell_parameters || undefined,
  },
  representations: model.structure_text ? {
    // 既有 POSCAR 由服务端转换后校验，原文不能冒充 CIF。
    conventional: { [String(model.structure_format || 'cif').toLowerCase()]: { text: model.structure_text, available: true } },
  } : undefined,
  sources: [{
    file_id: `structure_${model.id}`,
    filename: model.source_locator || `structure_${model.id}.${String(model.structure_format || 'cif').toLowerCase()}`,
    role: 'attachment',
  }],
})

export interface ScientificIdentityMap {
  structure_candidate_id_map?: Record<string, string>
  structure_key_map?: Record<string, string | null>
}

/** 只同步重建产生的身份，保留保存等待期间新增的值、候选及删除操作。 */
export function remapScientificIdentities(states: DraftMaterialState[], candidates: StructureCandidate[], maps: ScientificIdentityMap) {
  const resolve = (key: string, mapping: Record<string, string | null> = {}): string | null => {
    const seen = new Set<string>()
    let current: string | null = key
    while (current && Object.hasOwn(mapping, current) && !seen.has(current)) {
      seen.add(current)
      current = mapping[current]
    }
    return current
  }
  return {
    states: states.map(state => ({ ...state, property_modules: state.property_modules?.map(module => ({
      ...module, records: module.records.map(record => ({ ...record,
        structure_key: record.structure_key ? resolve(record.structure_key, maps.structure_key_map) : record.structure_key,
      })),
    })) })),
    candidates: candidates.map(candidate => ({ ...candidate,
      candidate_id: resolve(candidate.candidate_id, maps.structure_candidate_id_map) || candidate.candidate_id,
    })),
  }
}
