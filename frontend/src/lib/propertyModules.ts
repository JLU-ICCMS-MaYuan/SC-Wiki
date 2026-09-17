export const PROPERTY_MODULES = [
  { code: 'superconductive_properties', label: '超导性质' },
  { code: 'dynamical_properties', label: '动力学性质' },
  { code: 'thermodynamical_properties', label: '热力学性质' },
  { code: 'electronic_properties', label: '电子性质' },
] as const

export const PROPERTY_SCHEMA_VERSION = 2

export type PropertyModuleCode = typeof PROPERTY_MODULES[number]['code']
export type PropertyValueKind = 'number' | 'range' | 'text' | 'boolean'
export type PropertyRecordType = 'predicted_tc' | 'measured_tc' | 'property'

export interface PropertyRecordDraft {
  record_key: string
  module_code: PropertyModuleCode
  record_type: PropertyRecordType
  property_code: string
  custom_property_key?: string | null
  definition_key: string
  definition_version: number
  name_raw: string
  value_kind: PropertyValueKind
  value_raw: string
  value_number?: number | null
  value_min?: number | null
  value_max?: number | null
  value_text?: string | null
  value_boolean?: boolean | null
  uncertainty?: number | null
  unit_raw?: string | null
  canonical_unit?: string | null
  method_code?: string | null
  method_raw?: string | null
  criterion_code?: string | null
  criterion_raw?: string | null
  is_representative?: boolean
  structure_key?: string | null
  payload: Record<string, unknown>
  evidence?: Record<string, unknown> | null
  evidences?: unknown[]
}

export interface PropertyModuleDraft {
  module_key: string
  module_code: PropertyModuleCode
  definition_key: string
  definition_version: number
  display_order: number
  records: PropertyRecordDraft[]
}

/** Tc 摘要使用当前规范值，不能以旧原文回填已清空的数值。 */
export function propertyRecordSummaryValue(record: PropertyRecordDraft): string {
  if (record.record_type === 'property') return record.value_raw
  if (record.value_kind === 'number') return record.value_number == null ? '待填写 Tc' : `${record.value_number} K`
  if (record.value_kind === 'range') return `${record.value_min ?? '待填写'}–${record.value_max ?? '待填写'} K`
  if (record.value_kind === 'text') return record.value_text || '待填写 Tc'
  return record.value_boolean == null ? '待填写 Tc' : record.value_boolean ? '是' : '否'
}

let fallbackKeySequence = 0

export function newStableKey(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return `${prefix}-${crypto.randomUUID()}`
  fallbackKeySequence += 1
  return `${prefix}-${Date.now()}-${fallbackKeySequence}`
}

export const emptyPropertyModule = (module_code: PropertyModuleCode, displayOrder: number): PropertyModuleDraft => ({
  module_key: newStableKey(`module-${module_code}`),
  module_code,
  definition_key: `module.${module_code}`,
  definition_version: 1,
  display_order: displayOrder,
  records: [],
})

export const emptyPropertyRecord = (module_code: PropertyModuleCode): PropertyRecordDraft => ({
  record_key: newStableKey(`record-${module_code}`),
  module_code,
  record_type: 'property',
  property_code: 'custom',
  custom_property_key: newStableKey('custom-property'),
  definition_key: `record.${module_code}.custom`,
  definition_version: 1,
  name_raw: '',
  value_kind: 'number',
  value_raw: '',
  value_number: null,
  payload: {},
  evidences: [],
})

export const clonePropertyRecord = (record: PropertyRecordDraft): PropertyRecordDraft => ({
  ...structuredClone(record),
  record_key: newStableKey('record-copy'),
  custom_property_key: record.custom_property_key ? newStableKey('custom-property') : record.custom_property_key,
})

/** Tc 的 raw 列仅为当前值的兼容表示，不能作为另一份可编辑数据。 */
export function normalizeCurrentTcValue(record: PropertyRecordDraft): PropertyRecordDraft {
  if (record.record_type !== 'measured_tc' && record.record_type !== 'predicted_tc') return record
  const numberText = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? String(value) : ''
  let raw = ''
  if (record.value_kind === 'number') raw = numberText(record.value_number)
  if (record.value_kind === 'range') {
    const min = numberText(record.value_min), max = numberText(record.value_max)
    if (min && max) raw = `${min}–${max}`
  }
  if (record.value_kind === 'text') raw = record.value_text ?? ''
  if (record.value_kind === 'boolean' && typeof record.value_boolean === 'boolean') raw = String(record.value_boolean)
  return { ...record, value_raw: raw, unit_raw: ['number', 'range'].includes(record.value_kind) ? 'K' : null }
}

export const normalizePropertyRecordIdentity = (record: PropertyRecordDraft): PropertyRecordDraft => {
  const normalized = normalizeCurrentTcValue(structuredClone(record))
  const isCustom = normalized.record_type === 'property' && normalized.property_code === 'custom'
  normalized.custom_property_key = isCustom
    ? normalized.custom_property_key || (normalized.record_key
      ? `custom-property-${normalized.record_key}`
      : newStableKey('custom-property'))
    : null
  return normalized
}

const numberParameter = (value: unknown, unit: string) => (
  typeof value === 'number' ? { value_raw: String(value), value_number: value, unit_raw: unit } : undefined
)

// 旧草稿可能同时携带单证据和空数组，不能让空数组覆盖有效来源。
const legacyEvidenceList = (source: Record<string, any>): unknown[] => {
  const candidates = [source.evidence, source.evidences].flatMap(value => Array.isArray(value) ? value : value == null ? [] : [value])
  const seen = new Set<string>()
  return structuredClone(candidates.filter(value => {
    const identity = JSON.stringify(value)
    if (seen.has(identity)) return false
    seen.add(identity)
    return true
  }))
}

export function convertLegacyPropertyModules(state: Record<string, any>): PropertyModuleDraft[] {
  if (Array.isArray(state.property_modules)) {
    return state.property_modules.map((module: PropertyModuleDraft, index: number) => ({
      ...module,
      definition_key: module.definition_key || `module.${module.module_code}`,
      definition_version: module.definition_version || 1,
      display_order: index,
      records: Array.isArray(module.records)
        ? module.records.map(record => normalizePropertyRecordIdentity(record))
        : [],
    }))
  }

  const records: PropertyRecordDraft[] = []
  for (const result of Array.isArray(state.tc_results) ? state.tc_results : []) {
    const experimental = result.result_kind === 'experimental' || result.tc_method === 'experimental'
    const methodCode = experimental ? (result.tc_method === 'experimental' ? 'resistivity' : result.tc_method) : (result.tc_method || 'unknown')
    const context = result.calculation_context || state.calculation_context || {}
    const parameters = Object.fromEntries(Object.entries({
      lambda_ep: numberParameter(context.lambda_ep, '1'),
      omega_log: numberParameter(context.omega_log_k, 'K'),
      mu_star: numberParameter(context.mu_star, '1'),
    }).filter(([, value]) => value !== undefined))
    records.push({
      record_key: newStableKey('legacy-tc'),
      module_code: 'superconductive_properties',
      record_type: experimental ? 'measured_tc' : 'predicted_tc',
      property_code: 'tc',
      definition_key: `record.superconductive_properties.${experimental ? 'measured_tc' : 'predicted_tc'}.${methodCode}`,
      definition_version: 1,
      name_raw: 'critical temperature',
      value_kind: result.tc_value_k != null ? 'number' : 'range',
      value_raw: String(result.value_raw ?? result.tc_value_k ?? ''),
      value_number: result.tc_value_k ?? null,
      value_min: result.tc_min_k ?? null,
      value_max: result.tc_max_k ?? null,
      uncertainty: result.uncertainty_k ?? null,
      unit_raw: result.unit_raw || 'K',
      canonical_unit: 'K',
      method_code: methodCode,
      method_raw: result.tc_method_custom ?? null,
      criterion_code: result.criterion_code ?? null,
      criterion_raw: result.criterion_raw ?? null,
      is_representative: Boolean(result.is_representative),
      payload: experimental
        ? { experimental_conditions: structuredClone(state.experimental_context || {}) }
        : { calculation_conditions: structuredClone(context.conditions || {}), parameters },
      evidences: legacyEvidenceList(result),
    })
  }

  for (const property of Array.isArray(state.properties) ? state.properties : []) {
    const rawValue = property.value_raw ?? property.value ?? ''
    const isNumber = typeof property.value_number === 'number' || typeof property.value === 'number'
    records.push({
      ...emptyPropertyRecord('superconductive_properties'),
      record_key: newStableKey('legacy-property'),
      name_raw: String(property.name_raw || property.name || ''),
      value_kind: isNumber ? 'number' : 'text',
      value_raw: String(rawValue),
      value_number: isNumber ? Number(property.value_number ?? property.value) : null,
      value_text: isNumber ? null : String(rawValue),
      unit_raw: property.unit || property.unit_raw || null,
      evidences: legacyEvidenceList(property),
    })
  }

  return records.length > 0
    ? [{ ...emptyPropertyModule('superconductive_properties', 0), records: records.map(normalizeCurrentTcValue) }]
    : []
}
