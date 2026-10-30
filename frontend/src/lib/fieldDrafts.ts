import { api } from './api'
import { rememberWorkdraft, workdraftEpoch } from './workdraftSession'
import type { EvidenceTarget } from '../components/EvidenceWorkflow'

type Segment = string | { key: string; value: unknown }
interface Change { path: Segment[]; before?: unknown; value?: unknown; remove?: boolean; op?: string; key?: string; identity?: { key: string; value: unknown }; order?: unknown[]; after?: unknown }
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
    const rows = [...before, ...after]
    const key = identityKeys.find(k => rows.length && rows.every(v => typeof v?.[k] === 'string' && v[k]) &&
      [before, after].every(values => new Set(values.map(v => v[k])).size === values.length))
    if (key) {
      const previous = new Map(before.map(v => [v[key], v]))
      const current = new Set(after.map(v => v[key]))
      const changes: Change[] = before.filter(v => !current.has(v[key]))
        .map(v => ({op: 'remove_item', path, identity: {key, value: v[key]}}))
      after.forEach((v, index) => {
        if (!previous.has(v[key])) changes.push({op: 'insert', path, key, after: index ? after[index-1][key] : null, value: v})
        else changes.push(...fieldChanges(previous.get(v[key]), v, [...path, {key, value: v[key]}]))
      })
      const retained = before.filter(v => current.has(v[key])).map(v => v[key])
      const order = after.filter(v => previous.has(v[key])).map(v => v[key])
      if (!same(retained, order)) changes.push({op: 'reorder', path, key, order: after.map(v => v[key])})
      return changes
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
  let localBaseline: any
  const clone = (value: unknown) => JSON.parse(JSON.stringify(value))
  let running: Promise<unknown> = Promise.resolve()
  const save = (value: unknown, field?: string) => {
    const requested = clone(value)
    const operation = running.catch(() => undefined).then(async () => {
      const selected = field ? fieldDraft(localBaseline, requested, field) : requested
      const changes = fieldChanges(localBaseline, selected).filter(c => ['paper', 'material_states', 'structure_candidates', 'structural_observations'].includes(String(c.path[0])))
      if (!changes.length) return { changed: false, draft_version: undefined as number | undefined }
      if (!serverVersion && workdraftEpoch(target)) serverVersion = workdraftEpoch(target) + ':local'
      if (!serverVersion) {
        const params = new URLSearchParams({target:target.target,target_id:target.target_id})
        const state = await api.get<{version:string}>('/api/rag/evidence/draft-state?' + params)
        serverVersion = state.version
        rememberWorkdraft(target,state.version.includes(':') ? state.version.split(':')[0] : undefined)
      }
      const result = await api.patch<{ version: string; changed: boolean; draft_version?: number; revision?: number }>('/api/rag/evidence/draft', {
        ...target, expected_version: serverVersion, changes, ...(field ? { field_scope: true } : {}),
      })
      serverVersion = result.version
      if (result.revision !== undefined) window.dispatchEvent(new CustomEvent('workdraft-saved', {
        detail: {target, revision:result.revision, write_epoch:result.version.split(':')[0]} }))
      localBaseline = selected
      return result
    })
    running = operation
    return operation
  }
  return {
    initialize(value: unknown) { localBaseline = clone(value); serverVersion = undefined },
    hasChanges: (value: unknown) => fieldChanges(localBaseline, value).length > 0,
    save: (value: unknown) => save(value),
    saveField: (value: unknown, field: string) => save(value, field),
  }
}

/** 在原基线上只投影一个字段；数组索引先转换为当前宿主的稳定身份。 */
export function fieldDraft(baseline: any, current: any, field: string): any {
  const projected = JSON.parse(JSON.stringify(baseline))
  const parts = field.replace(/\[(\d+)\]/g, '.$1').split('.')
  let from = current, to = projected
  let record: { from: any; to: any; fromRows: any[]; toRows: any[]; path: string[] } | undefined
  for (const [depth, part] of parts.slice(0, -1).entries()) {
    if (Array.isArray(from)) {
      const item = from[Number(part)]
      const identity = identityKeys.find(key => item?.[key] != null)
      const found = identity && Array.isArray(to) ? to.find((value: any) => value?.[identity] === item[identity]) : undefined
      if (!found) throw new Error('当前字段所属记录尚未保存或身份已变化，输入已保留。')
      if (identity === 'record_key') record = { from: item, to: found, fromRows: from, toRows: to, path: parts.slice(depth + 1) }
      from = item; to = found
    } else {
      if (!from || typeof from !== 'object') throw new Error('当前字段已不存在，输入已保留。')
      from = from[part]
      to[part] ??= {}
      to = to[part]
    }
  }
  const leaf = parts.at(-1)!
  if (from?.[leaf] === undefined) delete to[leaf]
  else to[leaf] = JSON.parse(JSON.stringify(from[leaf]))
  if (record) {
    const valueField = /\.value_(number|min|max|text|boolean|kind|raw)$/.test(field)
    if (valueField || record.from.value_kind !== record.to.value_kind) {
      for (const key of ['value_kind', 'value_number', 'value_min', 'value_max', 'value_text', 'value_boolean', 'value_raw', 'unit_raw', 'canonical_unit']) {
        if (key in record.from) record.to[key] = record.from[key]
      }
      record.to.is_representative = record.from.is_representative
    }
    for (const key of ['tc_group', 'tc_range_origin']) {
      if (record.from.payload?.[key]) { record.to.payload ??= {}; record.to.payload[key] = structuredClone(record.from.payload[key]) }
    }
    const relative = record.path.join('.')
    const shared = relative.startsWith('payload.calculation_conditions.') ||
      relative.startsWith('payload.parameters.') && !relative.startsWith('payload.parameters.mu_star')
    const method = ['method_code', 'method_raw'].includes(relative)
    const group = record.from.payload?.tc_group
    if (group && (shared || method)) {
      for (const row of record.toRows) {
        const live = record.fromRows.find(item => item.record_key === row.record_key)
        if (!live || live.payload?.tc_group?.group_key !== group.group_key ||
            method && live.payload.tc_group.method_key !== group.method_key) continue
        let a = live, b = row
        for (const key of record.path.slice(0, -1)) { a = a?.[key]; b[key] ??= {}; b = b[key] }
        if (a?.[leaf] === undefined) delete b[leaf]
        else b[leaf] = structuredClone(a[leaf])
        if (relative === 'method_code') {
          row.definition_key = live.definition_key; row.definition_version = live.definition_version
          row.method_raw = live.method_raw
        }
      }
    }
  }
  return projected
}
