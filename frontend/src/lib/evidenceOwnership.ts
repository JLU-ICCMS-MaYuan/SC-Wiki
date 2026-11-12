import type { EvidenceRecord } from '../components/EvidenceWorkflow'

export const normalizedEvidencePath = (field: string) => field.replace(/\[(\d+)\]/g, '.$1').replace('.omega_log_k', '.omega_log')

/** DOM容器索引转为服务端字段路径；参数内部路径及稳定身份保持原样。 */
export const canonicalEvidencePath = (field: string) => field.replace(
  /(^|\.)(material_states|property_modules|records)\.(\d+)(?=\.|$)/g, '$1$2[$3]')

/** 所属关系仅用于入口和展示；不能授予另一个子项科学通过资格。 */
export function evidenceOwnerKey(record: EvidenceRecord): string {
  if (!record.settings_field) return record.key
  let field = normalizedEvidencePath(record.settings_field)
    .replace(/^material_states\.\d+\.property_modules\.\d+\.records\.\d+\./, '')
  if (record.record_field_key) field = field.replace(/\.extensions\.\d+(?=\.|$)/, () => '.extensions.' + record.record_field_key)
  return JSON.stringify([record.state_key, record.module_key, record.record_group_key || record.record_key, field])
}

export function evidenceSiblings(record: EvidenceRecord, records: EvidenceRecord[]): EvidenceRecord[] {
  const owner = evidenceOwnerKey(record)
  const order = ['name', 'raw', 'kind', 'unit']
  return records.filter(item => evidenceOwnerKey(item) === owner).sort((left, right) =>
    order.indexOf(left.settings_part || 'raw') - order.indexOf(right.settings_part || 'raw'))
}

export const evidencePartName = (record: EvidenceRecord) => ({ name: '名称', raw: '值', kind: '值类型', unit: '单位' }[record.settings_part || 'raw'])
