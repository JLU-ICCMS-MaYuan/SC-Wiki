// 比较科学编辑值；稳定身份用于数组匹配，排序与纯补证不会使核对失效。
import type { EvidenceRecord } from '../components/EvidenceWorkflow'

/** 当前字段按稳定身份读取；返回路径只用于聚焦，不作为数据身份。 */
export function currentEvidenceField(record: EvidenceRecord, paper: Record<string, unknown>, states: Array<Record<string, any>>) {
  let value: any = paper
  let field = record.field
  if (record.state_key) {
    const index = states.findIndex(s => s.state_key === record.state_key)
    if (index < 0) return undefined
    value = states[index]
    field = field.replace(/^material_states\[\d+\]/, `material_states[${index}]`)
    if (record.record_key) {
      const mi = value.property_modules?.findIndex((m: any) => m.module_key === record.module_key) ?? -1
      const ri = mi < 0 ? -1 : value.property_modules[mi].records.findIndex((r: any) => r.record_key === record.record_key)
      if (ri < 0) return undefined
      value = value.property_modules[mi].records[ri]
      field = field.replace(/\.property_modules\[\d+\]/, `.property_modules[${mi}]`).replace(/\.records\[\d+\]/, `.records[${ri}]`)
      return {value, field}
    }
  } else if (!field.startsWith('paper.')) return undefined
  if (record.structure_hash) return undefined
  return { value: value[field.split('.').at(-1)!] ?? null, field }
}

export function evidenceFieldAffected(record: EvidenceRecord, field: string) {
  const identity = field.match(/^(material_states\[\d+\])\.(material_name|material)$/)
  if (identity && record.field.startsWith(identity[1] + '.')) return true
  const context = field.match(/^(material_states\[\d+\])\.(material|material_dimensionality|pressure_[\w]+|temperature_[\w]+|magnetic_field_t|reported_space_group_[\w]+|crystal_system|state_kind|note|calculation_context|experimental_context)(?:\.|$)/)
  return record.field === field || record.field.startsWith(field + '.') || record.field.startsWith(field + '[') || field.startsWith(record.field + '.') || field.startsWith(record.field + '[')
    || Boolean(context && record.field.startsWith(context[1] + '.') && (record.record_key || record.provenance?.kind === 'derived'))
}
const ignored = new Set(['evidence', 'evidences', 'display_order', 'is_representative', 'record_key', 'module_key', 'state_key'])
const identity = (value: unknown): unknown => {
  if (!value || typeof value !== 'object') return undefined
  const row = value as Record<string, unknown>
  return row.state_key || row.module_key || row.record_key
}
export function changedScientificFields(before: unknown, after: unknown, path: string): string[] {
  if (Object.is(before, after)) return []
  if (Array.isArray(before) && Array.isArray(after)) {
    if (after.length > before.length && !after.every(identity)) return [path]
    return before.flatMap((value, index) => {
      const key = identity(value)
      const next = key ? after.find(item => identity(item) === key) : after[index]
      return changedScientificFields(value, next, `${path}[${index}]`)
    })
  }
  if (before && after && typeof before === 'object' && typeof after === 'object') {
    const a = before as Record<string, unknown>, b = after as Record<string, unknown>
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter(key => !ignored.has(key))
      .flatMap(key => changedScientificFields(a[key], b[key], `${path}.${key}`))
  }
  return [path]
}


/** 折叠计数与定位使用编辑器当前顺序，核对身份仍取稳定键。 */
export function evidenceIssuesForStates(records: import('../components/EvidenceWorkflow').EvidenceRecord[], states: Array<{ state_key?: string; property_modules?: Array<{ module_key: string; records: Array<{ record_key: string }> }> }>) {
  return records.map(record => {
    let field = record.field
    const si = record.state_key ? states.findIndex(state => state.state_key === record.state_key) : -1
    if (si >= 0) {
      field = field.replace(/^material_states\[\d+\]/, `material_states[${si}]`)
      const mi = states[si].property_modules?.findIndex(module => module.module_key === record.module_key) ?? -1
      if (mi >= 0) {
        field = field.replace(/\.property_modules\[\d+\]/, `.property_modules[${mi}]`)
        const ri = states[si].property_modules![mi].records.findIndex(row => row.record_key === record.record_key)
        if (ri >= 0) field = field.replace(/\.records\[\d+\]/, `.records[${ri}]`)
      }
    }
    return { field, message: record.reason }
  })
}
