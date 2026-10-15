import type { PropertyRecordDraft } from './propertyModules'

export const HULL_BASES = { formation_energy: '形成能 ΔE', formation_enthalpy: '形成焓 ΔH', formation_gibbs: '形成 Gibbs 自由能 ΔG', unspecified: '论文未说明' } as const
export type HullBasis = keyof typeof HULL_BASES
export const STABILITY = { stable: '稳定', unstable: '不稳定', unknown: '未判定' } as const
export const ZPE = { included: '已计入', excluded: '明确未计入', unspecified: '论文未说明' } as const
export interface HullCase {
  stability: keyof typeof STABILITY
  above_hull: number | null
  unit: 'eV/atom' | 'meV/atom'
  temperature_k: number | null
  zpe: keyof typeof ZPE
  decomposition_path: string
  source_description: string
}
export interface ThermodynamicStability {
  version: 1
  basis: HullBasis
  cases: Partial<Record<HullBasis, HullCase>>
}
export const emptyHullCase = (basis: HullBasis): HullCase => ({ stability: 'unknown', above_hull: null, unit: 'eV/atom', temperature_k: basis === 'formation_energy' || basis === 'formation_enthalpy' ? 0 : null, zpe: 'unspecified', decomposition_path: '', source_description: '' })
export function isThermodynamicStability(record: PropertyRecordDraft): boolean {
  return record.module_code === 'thermodynamical_properties' && record.record_type === 'property' && record.property_code === 'custom' && record.payload.thermodynamic_stability != null
}
export function withStability(record: PropertyRecordDraft, value: ThermodynamicStability): PropertyRecordDraft {
  const text = STABILITY[value.cases[value.basis]?.stability || 'unknown']
  return { ...record, name_raw: record.name_raw || 'thermodynamic stability', value_kind: 'text', value_raw: text, value_text: text,
    value_number: null, value_min: null, value_max: null, value_boolean: null, unit_raw: null, canonical_unit: null,
    payload: { ...record.payload, thermodynamic_stability: value } }
}
export function newStabilityRecord(record: PropertyRecordDraft): PropertyRecordDraft {
  return withStability(record, { version: 1, basis: 'unspecified', cases: { unspecified: emptyHullCase('unspecified') } })
}
export function validateStability(record: PropertyRecordDraft): Array<{ field: string; message: string }> {
  const value = record.payload.thermodynamic_stability as ThermodynamicStability | undefined
  if (value == null) return []
  const issues: Array<{ field: string; message: string }> = []
  const add = (field: string, message: string) => issues.push({ field: `payload.thermodynamic_stability${field ? `.${field}` : ''}`, message })
  if (!isThermodynamicStability(record)) add('', '稳定性记录必须使用热力学自定义性质')
  if (value.version !== 1 || !Object.hasOwn(HULL_BASES, value.basis)) add('basis', '凸包依据或版本无效')
  if (!value.cases || typeof value.cases !== 'object' || Array.isArray(value.cases) || !Object.hasOwn(value.cases, value.basis)) { add('cases', '当前判据数据缺失'); return issues }
  for (const [basis, entry] of Object.entries(value.cases)) {
    if (!Object.hasOwn(HULL_BASES, basis) || !entry || typeof entry !== 'object' || Array.isArray(entry)) { add(`cases.${basis}`, '判据数据无效'); continue }
    const c = entry as HullCase, path = `cases.${basis}`
    if (!Object.hasOwn(STABILITY, c.stability)) add(`${path}.stability`, '请选择稳定性')
    if (!Object.hasOwn(ZPE, c.zpe)) add(`${path}.zpe`, '请选择零点振动能口径')
    if (!['eV/atom', 'meV/atom'].includes(c.unit)) add(`${path}.unit`, '请选择明确的单位')
    for (const field of ['above_hull', 'temperature_k'] as const) if (c[field] != null && (typeof c[field] !== 'number' || !Number.isFinite(c[field]) || c[field]! < 0)) add(`${path}.${field}`, '请输入非负有限数值')
    if (['formation_energy', 'formation_enthalpy'].includes(basis) && c.temperature_k !== 0) add(`${path}.temperature_k`, '此判据温度应为 0 K')
    if (c.stability !== 'unstable' && c.above_hull != null) add(`${path}.above_hull`, '仅不稳定结论记录 above-hull 数值')
    for (const field of ['decomposition_path', 'source_description'] as const) if (typeof c[field] !== 'string') add(`${path}.${field}`, '必须为文本')
  }
  const current = value.cases[value.basis]
  if (current && (record.value_kind !== 'text' || record.value_raw !== STABILITY[current.stability] || record.value_text !== STABILITY[current.stability])) add('', '记录摘要与当前判据不一致')
  return issues
}
