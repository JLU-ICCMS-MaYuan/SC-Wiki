import { api } from './api'
import type { EvidenceTarget } from '../components/EvidenceWorkflow'

type Segment = string | { key: string; value: unknown }
interface Change { path: Segment[]; before: unknown; value?: unknown; remove?: boolean }
const identityKeys = ['state_key', 'module_key', 'record_key', 'field_key', 'candidate_id']
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** 草稿数字格可以暂存未完成文本；正式数值由提交检查和持久化边界负责。 */
export function draftNumber(raw: string): number | null {
  if (raw === '') return null
  return (/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw) && Number.isFinite(Number(raw))
    ? Number(raw) : raw) as number
}

/** 展示兼容转换不能吞掉草稿里的中间输入。 */
export function preserveRawNumbers<T>(raw: any, normalized: T): T {
  const visit = (source: any, target: any) => {
    if (!source || !target || typeof source !== 'object' || typeof target !== 'object') return
    if (Array.isArray(source) && Array.isArray(target)) {
      source.forEach((item, i) => {
        const key = identityKeys.find(k => item?.[k] != null)
        visit(item, key ? target.find(t => t?.[key] === item[key]) : target[i])
      })
      return
    }
    for (const [key, value] of Object.entries(source)) {
      if (/^(value_number|value_min|value_max|pressure_.*_gpa|temperature_value_k|magnetic_field_t|element_count)$/.test(key)
        && typeof value === 'string' && value !== '' && !Number.isFinite(Number(value))) target[key] = value
      else visit(value, target[key])
    }
  }
  visit(raw, normalized)
  return normalized
}

/** 只发送变化；数组元素按稳定身份寻址，重排本身不重写各个值。 */
export function fieldChanges(before: any, after: any, path: Segment[] = []): Change[] {
  if (same(before, after)) return []
  if (Array.isArray(before) && Array.isArray(after)) {
    const key = identityKeys.find(k => before.length && before.every(v => v?.[k] != null) && after.every(v => v?.[k] != null))
    if (key && same(before.map(v => v[key]), after.map(v => v[key]))) {
      return after.flatMap(v => fieldChanges(before.find(b => b[key] === v[key]), v, [...path, { key, value: v[key] }]))
    }
  }
  if (before && after && !Array.isArray(before) && !Array.isArray(after) && typeof before === 'object' && typeof after === 'object') {
    return [...new Set([...Object.keys(before), ...Object.keys(after)])]
      .filter(k => !k.startsWith('_'))
      .flatMap(k => fieldChanges(before[k], after[k], [...path, k]))
  }
  return [{ path, before: before ?? null, ...(after === undefined ? { remove: true } : { value: after }) }]
}

export function createFieldDraftSaver(target: EvidenceTarget) {
  let serverVersion: string | undefined
  let saved: any
  let localBaseline: any
  const clone = (value: unknown) => JSON.parse(JSON.stringify(value))
  return {
    initialize(value: unknown) { localBaseline = clone(value) },
    async save(value: unknown) {
      const changes = fieldChanges(localBaseline, value).filter(c => ['paper', 'material_states', 'structure_candidates', 'structural_observations'].includes(String(c.path[0])))
      if (!changes.length) return { changed: false, draft_version: undefined as number | undefined }
      if (!serverVersion) {
        const state = await api.get<{ version: string; draft: unknown }>(`/api/rag/evidence/draft-state?target=${target.target}&target_id=${encodeURIComponent(target.target_id)}`)
        serverVersion = state.version
        saved = state.draft
      }
      const result = await api.patch<{ version: string; changed: boolean; draft_version?: number }>('/api/rag/evidence/draft', {
        ...target, expected_version: serverVersion, changes,
      })
      serverVersion = result.version
      saved = clone(value)
      localBaseline = saved
      return result
    },
  }
}
