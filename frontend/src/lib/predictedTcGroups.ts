import { emptyPropertyRecord, newStableKey, normalizeCurrentTcValue, type PropertyRecordDraft } from './propertyModules'
import { muRangeIndex, readTcPairs, readTcParameter, setTcParameter, tcParameters, type ParameterValue } from './tcParameters'

export interface TcGroupMeta { version: 1; group_key: string; method_key: string; point_key?: string }
export interface TcPointView { key: string; record: PropertyRecordDraft; tc: number | null; mu: ParameterValue; selected: boolean }
export const isGroupedTc = (r: PropertyRecordDraft) => r.record_type === 'predicted_tc' && ['number', 'range'].includes(r.value_kind)
export const tcGroupMeta = (r: PropertyRecordDraft): TcGroupMeta | undefined => {
  const value = r.payload.tc_group as TcGroupMeta | undefined
  return value?.version === 1 && value.group_key && value.method_key ? value : undefined
}
export const tcGroupKey = (r: PropertyRecordDraft) => tcGroupMeta(r)?.group_key || r.record_key
export const tcMethodKey = (r: PropertyRecordDraft) => tcGroupMeta(r)?.method_key || r.record_key
export const tcPointKey = (r: PropertyRecordDraft) => tcGroupMeta(r)?.point_key || r.record_key
export const completeTcNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0

/** 展示旧范围不改写记录，也不从未配对 μ* 范围猜端点。 */
export function tcPointViews(record: PropertyRecordDraft): TcPointView[] {
  if (record.value_kind !== 'range') {
    const mu = readTcParameter(record, 'mu_star')
    return [{ key: tcPointKey(record), record, tc: record.value_number ?? null, mu,
      selected: Boolean(record.is_representative) && completeTcNumber(record.value_number) && completeTcNumber(mu) }]
  }
  return readTcPairs(record).map((pair, index) => ({ key: `${record.record_key}:${index}`, record, ...pair, selected: false }))
}

export function sharedTcParameters(record: PropertyRecordDraft): Record<string, any> {
  const parameters = structuredClone(tcParameters(record))
  delete parameters.mu_star
  parameters.extensions = (parameters.extensions || []).filter((item: any) => !['mu_star', 'mu_star_reported_range', 'mu_star_reported'].includes(item.key))
  if (!parameters.extensions.length) delete parameters.extensions
  return parameters
}

/** 明确编辑组合时才展开范围，每点继续作为既有科学记录保存。 */
export function expandTcPoints(records: PropertyRecordDraft[]): PropertyRecordDraft[] {
  const group = tcGroupKey(records[0])
  return records.flatMap(record => tcPointViews(record).map((point, index) => {
    const payload = setTcParameter(record, 'mu_star', point.mu)
    const parameters = payload.parameters as Record<string, any>
    if (muRangeIndex(record) >= 0) parameters.extensions = (parameters.extensions || []).filter((item: any) => item.key !== 'mu_star')
    if (record.value_kind === 'range' || record.value_min != null || record.value_max != null) {
      payload.tc_range_origin ||= { value_kind: record.value_kind, value_raw: record.value_raw,
        value_number: record.value_number, value_min: record.value_min, value_max: record.value_max,
        parameters: structuredClone(tcParameters(record)), is_representative: Boolean(record.is_representative) }
    }
    payload.tc_group = { version: 1, group_key: group, method_key: tcMethodKey(record), point_key: point.key } satisfies TcGroupMeta
    return normalizeCurrentTcValue({ ...structuredClone(record), record_key: index === 0 ? record.record_key : newStableKey('tc-point'),
      value_kind: 'number', value_number: point.tc, value_min: null, value_max: null, value_text: null, value_boolean: null,
      is_representative: point.selected, payload })
  }))
}

export function newTcPoint(template: PropertyRecordDraft, methodKey: string, definition?: {
  definition_key: string; version: number; method_code?: string | null
}): PropertyRecordDraft {
  const record = emptyPropertyRecord('superconductive_properties')
  return { ...record, record_type: 'predicted_tc', property_code: 'tc', custom_property_key: null,
    definition_key: definition?.definition_key || template.definition_key,
    definition_version: definition?.version || template.definition_version,
    method_code: definition?.method_code || template.method_code, name_raw: 'critical temperature',
    value_number: null, unit_raw: 'K', canonical_unit: 'K', is_representative: false,
    payload: { parameters: { ...sharedTcParameters(template), mu_star: null },
      calculation_conditions: structuredClone(template.payload.calculation_conditions || {}),
      ...(template.payload.approximation ? { approximation: template.payload.approximation } : {}),
      tc_group: { version: 1, group_key: tcGroupKey(template), method_key: methodKey, point_key: record.record_key } satisfies TcGroupMeta } }
}

export function updateTcPoint(records: PropertyRecordDraft[], key: string, field: 'tc' | 'mu', value: ParameterValue): PropertyRecordDraft[] {
  return expandTcPoints(records).map(record => {
    if (tcPointKey(record) !== key) return record
    const updated = field === 'tc' ? { ...record, value_number: value as number | null }
      : { ...record, payload: setTcParameter(record, 'mu_star', value) }
    if (!completeTcNumber(updated.value_number) || !completeTcNumber(readTcParameter(updated, 'mu_star'))) updated.is_representative = false
    return normalizeCurrentTcValue(updated)
  })
}

export function selectTcPoint(records: PropertyRecordDraft[], key: string, selected: boolean) {
  return expandTcPoints(records).map(record => ({ ...record, is_representative: selected && tcPointKey(record) === key
    && completeTcNumber(record.value_number) && completeTcNumber(readTcParameter(record, 'mu_star')) }))
}

/** 共同输入只传播给用户明确创建的组，保留各结果的 μ* 和来源。 */
export function updateTcCommon(records: PropertyRecordDraft[], root: PropertyRecordDraft) {
  return records.map(record => {
    const own = tcParameters(record), shared = sharedTcParameters(root)
    const ownMu = (own.extensions || []).filter((item: any) => ['mu_star', 'mu_star_reported_range', 'mu_star_reported'].includes(item.key))
    const parameters = { ...shared, ...('mu_star' in own ? { mu_star: structuredClone(own.mu_star) } : {}),
      ...((shared.extensions?.length || ownMu.length) ? { extensions: [...(shared.extensions || []), ...ownMu] } : {}) }
    return { ...record, payload: { ...record.payload, parameters,
      calculation_conditions: structuredClone(root.payload.calculation_conditions || {}) } }
  })
}

export function predictedTcGroups(records: PropertyRecordDraft[]): PropertyRecordDraft[][] {
  const groups = new Map<string, PropertyRecordDraft[]>()
  records.filter(isGroupedTc).forEach(record => {
    const key = tcGroupKey(record)
    groups.set(key, [...(groups.get(key) || []), record])
  })
  return [...groups.values()]
}
