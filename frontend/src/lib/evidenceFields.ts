// 比较科学编辑值；稳定身份用于数组匹配，排序与纯补证不会使核对失效。
import type { EvidenceRecord } from '../components/EvidenceWorkflow'
import { getAtPath } from './formDefinitions'

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
      const state = value
      const mi = value.property_modules?.findIndex((m: any) => m.module_key === record.module_key) ?? -1
      const ri = mi < 0 ? -1 : value.property_modules[mi].records.findIndex((r: any) => r.record_key === record.record_key)
      if (ri < 0) return undefined
      value = value.property_modules[mi].records[ri]
      field = field.replace(/\.property_modules\[\d+\]/, `.property_modules[${mi}]`).replace(/\.records\[\d+\]/, `.records[${ri}]`)
      if (record.record_field) {
        let path = record.record_field
        if (path.includes('.omega_log_k') && getAtPath(value, path) == null) {
          path = path.replace('.omega_log_k', '.omega_log')
          field = field.replace('.omega_log_k', '.omega_log')
        }
        if (path.includes('.extensions.') && (record.record_field_key || record.current_value && typeof record.current_value === 'object')) {
          const [group] = path.split('.extensions.')
          const extensions = getAtPath(value, group + '.extensions') as Array<Record<string, unknown>> | undefined
          const matches = extensions?.map((e, i) => ({ e, i })).filter(({ e }) => record.record_field_key
            ? (e.field_key || e.key) === record.record_field_key : JSON.stringify(e) === JSON.stringify(record.current_value)) || []
          const index = matches.length === 1 ? matches[0].i : -1
          if (index < 0) return undefined
          path = path.replace(/\.extensions\.\d+/, `.extensions.${index}`)
          field = field.replace(/\.extensions\.\d+/, `.extensions.${index}`)
        }
        const scalar = getAtPath(value, path) ?? null
        let annotations: unknown
        if (path.startsWith('payload.parameters.mu_star') || path.startsWith('payload.parameters.extensions.')) annotations = value.payload.field_settings?.mu_star
        else if (path.startsWith('payload.parameters.')) annotations = value.payload.parameters?.field_settings?.[path.split('.')[2].replace('omega_log_k', 'omega_log')]
        else if (path.startsWith('payload.calculation_conditions.') && !path.includes('.extensions.')) annotations = value.payload.calculation_conditions?.field_settings?.[path.split('.')[2]]
        else if (path.startsWith('value_')) annotations = value.payload.field_settings?.tc
        return { value: scalar, field, manualValue: scalar, comparisonValue: { value: scalar, field_settings: annotations } }
      }
      // 说明绑定物性值及材料条件；其他物性或排序变化不改变本条说明身份。
      const context = Object.fromEntries(Object.entries(state).filter(([key]) =>
        !['property_modules', 'structures', 'structure_candidates', 'evidence', 'evidences', 'field_evidence', 'display_order'].includes(key)))
      return {value, field, manualValue: { record: value, state: context }}
    }
  } else if (!field.startsWith('paper.')) return undefined
  if (record.structure_hash) return undefined
  return { value: value[field.split('.').at(-1)!] ?? null, field }
}

const overlaps = (left: string, right: string) => left === right || left.startsWith(right + '.') || left.startsWith(right + '[')
  || right.startsWith(left + '.') || right.startsWith(left + '[')

export function evidenceFieldAffected(record: EvidenceRecord, field: string, records: EvidenceRecord[] = []) {
  if (overlaps(record.field, field)) return true
  if (record.record_field && record.record_dependencies?.some(path => overlaps(record.field.slice(0, record.field.length - record.record_field!.length) + path, field))) return true
  const identity = field.match(/^(material_states\[\d+\])\.(material_name|material)$/)
  if (identity && record.field.startsWith(identity[1] + '.')) return true
  if (record.provenance?.kind === 'derived') {
    const source = record.dependency ? records.find(row => row.item_key === record.dependency || row.key === record.dependency) : undefined
    const name = record.field.split('.').at(-1)
    // 换算的单位也是实际输入；旧结果仅按已知规则回退。
    const inputs = name === 'element_count' ? ['material']
      : name === 'reported_space_group_number' || name === 'crystal_system' ? ['reported_space_group_symbol']
        : name === 'pressure_value_gpa' ? ['pressure_raw', 'pressure_unit_raw']
          : name === 'temperature_value_k' ? ['temperature_raw', 'temperature_unit_raw'] : []
    const state = record.field.match(/^material_states\[\d+\]/)?.[0]
    return Boolean(source && overlaps(source.field, field)) || Boolean(state && inputs.some(input => overlaps(`${state}.${input}`, field)))
  }
  const context = field.match(/^(material_states\[\d+\])\.(material|material_dimensionality|pressure_[\w]+|temperature_[\w]+|magnetic_field_t|reported_space_group_[\w]+|crystal_system|state_kind|structure_optimization|note|calculation_context|experimental_context)(?:\.|$)/)
  return Boolean(context && record.field.startsWith(context[1] + '.') && record.record_key)
}
const ignored = new Set(['evidence', 'evidences', 'display_order', 'is_representative', 'record_key', 'module_key', 'state_key', 'tc_group', 'tc_range_origin'])
const identity = (value: unknown): unknown => {
  if (!value || typeof value !== 'object') return undefined
  const row = value as Record<string, unknown>
  return row.state_key || row.module_key || row.record_key
}
export function changedScientificFields(before: unknown, after: unknown, path: string): string[] {
  if (Object.is(before, after) || (before == null && after === '') || (after == null && before === '')) return []
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
export function evidenceFieldsForStates(records: import('../components/EvidenceWorkflow').EvidenceRecord[], states: Array<{ state_key?: string; property_modules?: Array<{ module_key: string; records: Array<{ record_key: string }> }> }>) {
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
    return field
  })
}
