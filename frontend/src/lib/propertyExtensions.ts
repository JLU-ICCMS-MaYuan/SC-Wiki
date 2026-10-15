import type { PropertyRecordDraft } from './propertyModules'

/** 开放扩展中的输入不受发布 Schema 约束，需要在保存边界拒绝非法数字。 */
export function validatePropertyExtensions(record: PropertyRecordDraft): Array<{ field: string; message: string }> {
  const issues: Array<{ field: string; message: string }> = []
  for (const group of ['parameters', 'calculation_conditions']) {
    const value = record.payload[group] as { extensions?: Array<Record<string, unknown>> } | undefined
    if (!Array.isArray(value?.extensions)) continue
    value.extensions.forEach((item, index) => {
      if (!item || typeof item !== 'object') return
      const fields = item.value_kind === 'number' ? ['value_number'] : item.value_kind === 'range' ? ['value_min', 'value_max'] : []
      const invalid = fields.some(field => item[field] != null && (typeof item[field] !== 'number' || !Number.isFinite(item[field])))
        || (item.value_kind === 'number' && typeof item.value_raw === 'string' && !!item.value_raw.trim() && item.value_number == null)
        || (item.value_kind === 'range' && typeof item.value_raw === 'string' && item.value_raw.includes('..') && (item.value_min == null || item.value_max == null))
        || (item.value_kind === 'range' && typeof item.value_min === 'number' && typeof item.value_max === 'number' && item.value_min > item.value_max)
      if (invalid) issues.push({ field: `payload.${group}.extensions.${index}.value_raw`, message: '请输入完整有效的数值或递增范围' })
    })
  }
  return issues
}
