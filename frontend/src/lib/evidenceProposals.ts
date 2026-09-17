export interface EvidencePatch { key: string; item_key: string; field: string; state_key?: string; module_key?: string; record_key?: string; values: Record<string, unknown> }
export interface PreparedProposals { preparation_id?: string; resume_stage?: 'scientific' | 'finalize'; patches: EvidencePatch[]; version: string }

/** 接受草稿按稳定身份应用，禁止将旧数组下标写到排序后的其他记录。 */
export function applyEvidencePatches<T extends { paper: Record<string, any>; material_states: Array<Record<string, any>> }>(draft: T, patches: EvidencePatch[]): T {
  const next = structuredClone(draft)
  for (const patch of patches) {
    let target: Record<string, any> = next.paper
    if (patch.state_key) {
      target = next.material_states.find(s => s.state_key === patch.state_key)!
      if (!target) throw new Error('建议对应的材料状态已变化，请刷新')
      if (patch.record_key) {
        const module = target.property_modules?.find((m: any) => m.module_key === patch.module_key)
        target = module?.records?.find((r: any) => r.record_key === patch.record_key)
        if (!target) throw new Error('建议对应的科学记录已变化，请刷新')
      }
    }
    for (const [path, value] of Object.entries(patch.values)) {
      const field = path || patch.field.split('.').at(-1)!
      if (field === 'material_families' || field === 'structure_families') {
        const original = target[field] || []
        target[field] = (value as string[]).map(name => original.find((x: any) => (x.name || x.name_zh) === name) || { name, name_zh: name, status: 'pending', ...(field === 'structure_families' ? { is_primary: false } : {}) })
      } else target[field] = value
    }
    if (patch.record_key) Object.assign(target, normalizeCurrentTcValue(target as PropertyRecordDraft))
  }
  return next
}
import { normalizeCurrentTcValue, type PropertyRecordDraft } from './propertyModules'
