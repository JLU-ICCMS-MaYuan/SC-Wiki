import type { PropertyRecordDraft } from './propertyModules'

type Parameter = 'lambda_ep' | 'omega_log' | 'mu_star'
export type ParameterValue = number | string | null
export interface TcPair { tc: number | null; mu: ParameterValue }
const object = (value: unknown): Record<string, any> | undefined => (
  value != null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, any> : undefined
)
export const tcParameters = (record: PropertyRecordDraft) => object(record.payload.parameters) || {}
export const muRangeIndex = (record: PropertyRecordDraft): number => {
  const extensions = tcParameters(record).extensions
  return Array.isArray(extensions) ? extensions.findIndex(item => item?.key === 'mu_star' && item?.value_kind === 'range') : -1
}
export const readTcParameter = (record: PropertyRecordDraft, key: Parameter): ParameterValue => {
  const parameters = tcParameters(record)
  const value = key === 'omega_log' ? parameters.omega_log ?? parameters.omega_log_k : parameters[key]
  return object(value) ? value.value_number ?? null : value ?? null
}
export const readTcPairs = (record: PropertyRecordDraft): [TcPair, TcPair] => {
  const parameters = tcParameters(record), index = muRangeIndex(record)
  const range = index >= 0 ? parameters.extensions[index] : undefined
  const common = readTcParameter(record, 'mu_star')
  return [
    { tc: record.value_kind === 'range' ? record.value_min ?? null : record.value_number ?? null, mu: range ? range.value_max ?? null : common },
    { tc: record.value_max ?? null, mu: range ? range.value_min ?? null : common },
  ]
}

/** 定向合并参数，保留包装对象中的来源和 Evidence；清空不能恢复旧值。 */
export function setTcParameter(record: PropertyRecordDraft, key: Parameter, value: ParameterValue): PropertyRecordDraft['payload'] {
  const parameters = { ...tcParameters(record) }
  const previous = parameters[key] ?? (key === 'omega_log' ? parameters.omega_log_k : undefined)
  parameters[key] = object(previous) ? { ...previous, value_number: value, value_raw: value == null ? '' : String(value) } : value
  if (key === 'omega_log') delete parameters.omega_log_k
  return { ...record.payload, parameters }
}

export function setTcPairs(record: PropertyRecordDraft, pairs: [TcPair, TcPair]): Partial<PropertyRecordDraft> {
  if (record.record_type !== 'predicted_tc') return record.value_kind === 'range'
    ? { value_min: pairs[0].tc, value_max: pairs[1].tc } : { value_number: pairs[0].tc }
  const parameters = { ...tcParameters(record) }
  if (record.value_kind !== 'range') return { value_number: pairs[0].tc, payload: setTcParameter(record, 'mu_star', pairs[0].mu) }
  // 仅规范化写入数据，输入组的位置由组件保持，不在用户输入中途换位。
  const sorted = pairs[0].tc != null && pairs[1].tc != null && pairs[0].tc > pairs[1].tc ? [pairs[1], pairs[0]] : pairs
  const index = muRangeIndex(record)
  const extensions = Array.isArray(parameters.extensions) ? [...parameters.extensions] : []
  const previous = index >= 0 ? extensions[index] : object(parameters.mu_star)
  const range: Record<string, any> = { ...previous, key: 'mu_star', value_kind: 'range', unit_raw: '1',
    value_min: sorted[1].mu, value_max: sorted[0].mu,
    value_raw: `${sorted[1].mu ?? ''}–${sorted[0].mu ?? ''}` }
  delete range.value_number
  if (index >= 0) extensions[index] = range
  else extensions.push(range)
  delete parameters.mu_star
  parameters.extensions = extensions
  return { value_min: sorted[0].tc, value_max: sorted[1].tc, payload: { ...record.payload, parameters } }
}

export function tcKindParameters(record: PropertyRecordDraft, kind: string, firstMu: ParameterValue): PropertyRecordDraft['payload'] {
  if (record.record_type !== 'predicted_tc' || kind === 'range') return record.payload
  const index = muRangeIndex(record)
  if (index < 0) return record.payload
  const parameters = { ...tcParameters(record) }, range = parameters.extensions[index]
  // 范围转标量时仍保留原扩展携带的来源元数据。
  const { value_min, value_max, value_kind, ...metadata } = range
  parameters.mu_star = { ...metadata, value_number: firstMu, value_raw: firstMu == null ? '' : String(firstMu) }
  parameters.extensions = parameters.extensions.filter((_: unknown, i: number) => i !== index)
  return { ...record.payload, parameters }
}

export function validateTcParameters(record: PropertyRecordDraft): Array<{ field: string; message: string }> {
  if (record.record_type !== 'predicted_tc') return []
  const parameters = tcParameters(record), issues: Array<{ field: string; message: string }> = []
  const valid = (value: unknown) => value == null || (typeof value === 'number' && Number.isFinite(value) && value >= 0)
  for (const key of ['lambda_ep', 'omega_log', 'mu_star'] as const) {
    if (!valid(readTcParameter(record, key))) issues.push({ field: `payload.parameters.${key}`, message: '请输入完整的非负数值' })
  }
  const index = muRangeIndex(record)
  if (index >= 0) {
    const range = parameters.extensions[index], path = `payload.parameters.extensions.${index}`
    for (const field of ['value_min', 'value_max']) if (!valid(range[field])) issues.push({ field: `${path}.${field}`, message: '请输入完整的非负 μ* 数值' })
    if (range.value_min != null && range.value_max != null && range.value_min > range.value_max) issues.push({ field: `${path}.value_max`, message: '两组 Tc 与 μ* 的对应关系不一致，请检查输入' })
    if (parameters.mu_star != null || record.value_kind !== 'range' || parameters.extensions.filter((item: any) => item?.key === 'mu_star' && item?.value_kind === 'range').length > 1) issues.push({ field: `payload.parameters.mu_star`, message: 'μ* 数值与范围表示冲突，请检查输入' })
  }
  return issues
}
