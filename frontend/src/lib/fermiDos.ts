import type { PropertyModuleDraft, PropertyRecordDraft } from './propertyModules'

export const DOS_SOURCE_KEY = 'dos_fermi_sources'
const valueFields = ['value_number', 'value_min', 'value_max', 'value_text', 'value_boolean'] as const
const scienceFields = ['record_type', 'property_code', 'definition_key', 'definition_version', 'name_raw',
  'value_kind', 'value_raw', ...valueFields, 'uncertainty', 'unit_raw', 'canonical_unit',
  'method_code', 'method_raw', 'criterion_code', 'criterion_raw', 'structure_key'] as const

export const isFermiDos = (record: PropertyRecordDraft) => record.module_code === 'electronic_properties'
  && record.record_type === 'property' && record.property_code === 'dos_fermi'

const stableValue = (value: unknown): unknown => Array.isArray(value) ? value.map(stableValue)
  : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, stableValue(item)]))
    : value
const identity = (value: unknown) => JSON.stringify(stableValue(value))
const cleanScience = (value: unknown): unknown => Array.isArray(value) ? value.map(cleanScience)
  : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([, item]) => item != null).map(([key, item]) => [key, cleanScience(item)])) : value
const scientificValue = (record: PropertyRecordDraft) => identity(cleanScience({
  ...Object.fromEntries(scienceFields.map(key => [key, ['name_raw', 'value_raw', 'unit_raw', 'canonical_unit'].includes(key) && typeof record[key] === 'string'
    ? (record[key] as string).trim() : record[key]])),
  payload: Object.fromEntries(Object.entries(record.payload || {}).filter(([key]) => ![DOS_SOURCE_KEY, 'source_associations', 'table_row_ref'].includes(key))),
}))
export const sameDosValue = (left: PropertyRecordDraft, right: PropertyRecordDraft) => scientificValue(left) === scientificValue(right)

export function dosSourceRecords(record: PropertyRecordDraft): PropertyRecordDraft[] {
  const archive = record.payload?.[DOS_SOURCE_KEY] as { version?: number; records?: PropertyRecordDraft[] } | undefined
  return archive?.version === 1 && Array.isArray(archive.records) ? archive.records : [record]
}

export function dosArchiveIssue(record: PropertyRecordDraft): string | undefined {
  if (!isFermiDos(record) || !(DOS_SOURCE_KEY in record.payload)) return
  const archive = record.payload[DOS_SOURCE_KEY] as { version?: number; records?: PropertyRecordDraft[] } | null
  if (!archive || archive.version !== 1 || !Array.isArray(archive.records) || !archive.records.length
    || archive.records.some(source => !source || !isFermiDos(source) || !source.value_raw?.trim()
      || !source.payload || typeof source.payload !== 'object' || DOS_SOURCE_KEY in source.payload)) return 'DOS 来源归档格式或版本无效'
}

export function dosSourceGroups(record: PropertyRecordDraft): PropertyRecordDraft[] {
  const groups = new Map<string, PropertyRecordDraft>()
  for (const source of dosSourceRecords(record)) {
    const key = scientificValue(source)
    const known = groups.get(key)
    const evidences = [...(known?.evidences || []), ...(source.evidences || []), ...(source.evidence ? [source.evidence] : [])]
    groups.set(key, { ...(known || source), evidences: [...new Map(evidences.map(item => [identity(item), item])).values()] })
  }
  return [...groups.values()]
}

export const hasDosConflict = (record: PropertyRecordDraft) => isFermiDos(record) && !dosArchiveIssue(record) && dosSourceGroups(record).length > 1
export const pendingDosValue = (record: PropertyRecordDraft) => hasDosConflict(record) && !record.value_raw.trim()
  && valueFields.every(field => record[field] == null || record[field] === '')

export function normalizeDosRecords(records: PropertyRecordDraft[]): PropertyRecordDraft[] {
  const dos = records.filter(isFermiDos)
  if (dos.length < 2 || dos.some(dosArchiveIssue)) return records
  const current = dos.find(record => DOS_SOURCE_KEY in record.payload)
  const canonical = structuredClone(current || dos[0])
  const sources = [...new Map(dos.flatMap(dosSourceRecords).map(source => [identity(source), structuredClone(source)])).values()]
  canonical.payload = { ...canonical.payload, [DOS_SOURCE_KEY]: { version: 1, records: sources } }
  canonical.evidences = [...new Map(sources.flatMap(source => [...(source.evidences || []), ...(source.evidence ? [source.evidence] : [])]).map(item => [identity(item), item])).values()]
  if (!current && dosSourceGroups(canonical).length > 1) {
    canonical.value_raw = ''
    Object.assign(canonical, { value_number: null, value_min: null, value_max: null, value_boolean: null,
      value_text: canonical.value_kind === 'text' ? '' : null })
  }
  let inserted = false
  return records.flatMap(record => {
    if (!isFermiDos(record)) return [record]
    if (inserted) return []
    inserted = true
    return [canonical]
  })
}

export const normalizeDosModules = (modules: PropertyModuleDraft[]): PropertyModuleDraft[] => modules.map(module => {
  const records = normalizeDosRecords(module.records || [])
  return records === module.records ? module : { ...module, records }
})
