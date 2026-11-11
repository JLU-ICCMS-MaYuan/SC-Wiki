import type { DraftMaterialState } from './paperProcessing'
import { newStableKey } from './propertyModules'

export interface MaterialStateSplitPreview {
  stateKey: string
  snapshot: string
  state: DraftMaterialState
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
