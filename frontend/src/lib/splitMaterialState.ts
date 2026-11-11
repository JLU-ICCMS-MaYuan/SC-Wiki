import type { DraftMaterialState } from './paperProcessing'
import { newStableKey } from './propertyModules'

export interface MaterialStateSplitPreview {
  stateKey: string
  snapshot: string
  state: DraftMaterialState
}

export interface MaterialStateSnapshot { state: DraftMaterialState; snapshot: string }

export function isStructureOnlyState(source: DraftMaterialState): boolean {
  return Boolean(source.state_key && source.structure?.structure_text && !(source.property_modules || []).length
    && !source.tc_results?.length && !source.properties?.length && !source.calculation_context && !source.experimental_context
    && source.material?.trim() && typeof source.pressure_value_gpa === 'number' && Number.isFinite(source.pressure_value_gpa)
    && Number.isInteger(source.reported_space_group_number) && source.reported_space_group_number! >= 1
    && source.reported_space_group_number! <= 230 && source.reported_space_group_symbol)
}

export function canMergeStructureState(source: DraftMaterialState, target: DraftMaterialState): boolean {
  return Boolean(isStructureOnlyState(source) && target.state_key && source.state_key !== target.state_key
    && target.structure == null && target.property_modules?.some(module => module.records.length)
    && source.material?.trim() && source.material.trim() === target.material?.trim()
    && typeof source.pressure_value_gpa === 'number' && Number.isFinite(source.pressure_value_gpa)
    && source.pressure_value_gpa === target.pressure_value_gpa
    && (source.state_kind || 'unknown') === (target.state_kind || 'unknown')
    && (source.structure_optimization || 'unknown') === (target.structure_optimization || 'unknown'))
}

/** 只归并无其他数据的结构卡；使用两卡最新身份，不将方法或参数广播给物性。 */
export function mergeStructureState(states: DraftMaterialState[], sourcePreview: MaterialStateSnapshot,
  targetPreview: MaterialStateSnapshot, note: string, readOnly: boolean) {
  const source = states.find(state => state.state_key === sourcePreview.state.state_key)
  const target = states.find(state => state.state_key === targetPreview.state.state_key)
  if (readOnly || !source || !target || JSON.stringify(source) !== sourcePreview.snapshot
    || JSON.stringify(target) !== targetPreview.snapshot || !canMergeStructureState(source, target)) throw new Error('stale_merge_preview')
  const extra = note.trim()
  const structure = extra ? { ...source.structure, user_note: [...new Set([
    String(source.structure!.user_note || '').trim(), extra].filter(Boolean))].join('\n\n') } : source.structure
  const merged = { ...target, structure, reported_space_group_number: source.reported_space_group_number,
    reported_space_group_symbol: source.reported_space_group_symbol, crystal_system: source.crystal_system }
  return states.filter(state => state.state_key !== source.state_key)
    .map(state => state.state_key === target.state_key ? merged : state)
}

/** 一次修改只转移规范晶胞；物性、共同参数与其他卡保持原身份和引用。 */
export function splitMaterialState(states: DraftMaterialState[], preview: MaterialStateSplitPreview,
  group: { number: number; symbol: string; crystalSystem: DraftMaterialState['crystal_system'] }, readOnly: boolean) {
  const index = states.findIndex(state => state.state_key === preview.stateKey)
  const source = states[index]
  if (readOnly || !source || JSON.stringify(source) !== preview.snapshot || !source.structure?.structure_text
    || !source.property_modules?.some(module => module.records.length)) throw new Error('stale_split_preview')
  const shared = ['material', 'material_name', 'pressure_value_gpa', 'state_kind', 'element_count',
    'element_count_locked', 'material_dimensionality', 'structure_optimization', 'crystal_system',
    'reported_space_group_symbol', 'reported_space_group_number', 'schema_version'] as const
  const structureState: DraftMaterialState = Object.fromEntries(shared.filter(key => key in source)
    .map(key => [key, source[key]]))
  Object.assign(structureState, {
    state_key: newStableKey('structure-state'), structure: source.structure,
    property_modules: [], structure_families: [], deleted_record_keys: [], deleted_module_keys: [],
    field_evidence: Object.fromEntries(Object.entries(source.field_evidence || {}).filter(([key]) =>
      (shared as readonly string[]).includes(key))),
  })
  const propertiesState: DraftMaterialState = { ...source, structure: null,
    reported_space_group_number: group.number, reported_space_group_symbol: group.symbol,
    crystal_system: group.crystalSystem }
  return [...states.map((state, i) => i === index ? propertiesState : state), structureState]
}
