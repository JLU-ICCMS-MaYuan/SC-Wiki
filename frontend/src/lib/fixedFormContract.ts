import manifest from '../../../backend/data/scientific_form_contract.v1.json'
export const FORM_CONTRACT = manifest
export const conditionLabels = manifest.labels as Record<string, string>
export const conditionSoftware = manifest.software as Record<string, string[]>
export const commonConditions = manifest.condition_fields as Record<string, string>
export const softwareLabels = manifest.software_labels as Record<string, string>
export const getCondition = (conditions: Record<string, any>, path: string): any =>
  path.split('.').reduce((value, key) => value?.[key], conditions)
export function setCondition(conditions: Record<string, any>, path: string, value: unknown): Record<string, any> {
  const [group, key] = path.split('.')
  return key ? { ...conditions, [group]: { ...conditions[group], [key]: value } } : { ...conditions, [group]: value }
}
export function conditionText(value: any): string {
  if (value == null) return ''
  if (Array.isArray(value)) return value.join(' × ')
  if (typeof value !== 'object') return String(value)
  if (value.value_raw != null) return String(value.value_raw)
  if (value.value_kind === 'range') return String(value.value_min ?? '') + '..' + String(value.value_max ?? '')
  return String(value.value_number ?? value.value_text ?? '')
}
export function conditionPatch(previous: any, raw: string, numeric: boolean, unit?: string): any {
  if (numeric || previous && typeof previous === 'object' && !Array.isArray(previous)) {
    const value = { ...(previous && typeof previous === 'object' && !Array.isArray(previous) ? previous : {}),
      value_kind: numeric ? 'number' : 'text', value_raw: raw }
    if (numeric) {
      value.value_number = raw.trim() && /^[+]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(raw.trim()) ? Number(raw) : null
      delete value.value_text
    } else { value.value_text = raw; delete value.value_number }
    if (unit !== undefined) value.unit_raw = unit
    return value
  }
  return raw
}
export function fixedConditionIssues(conditions: any): Array<{field:string; message:string}> {
  if (!conditions || typeof conditions !== 'object') return []
  const issues: Array<{field:string; message:string}> = []
  const add = (field: string, message: string) => issues.push({field:'payload.calculation_conditions.' + field,message})
  for (const key of Object.keys(conditions)) {
    if (!(key in commonConditions) && !(key in conditionSoftware) && !['extensions','field_settings'].includes(key))
      add(key, '字段未登记或已退役')
  }
  for (const [software, keys] of Object.entries(conditionSoftware)) {
    const group = conditions[software]
    if (group == null) continue
    if (typeof group !== 'object' || Array.isArray(group)) { add(software,'软件参数必须是对象'); continue }
    for (const [key, value] of Object.entries(group) as [string, any][]) {
      if (!keys.includes(key)) { add(software + '.' + key,'不是该软件已登记参数'); continue }
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        if (value.value_kind === 'number' && value.value_raw?.trim() && (value.value_number == null || !Number.isFinite(value.value_number)))
          add(software + '.' + key,'请输入完整有效的数值')
      }
    }
  }
  return issues
}
