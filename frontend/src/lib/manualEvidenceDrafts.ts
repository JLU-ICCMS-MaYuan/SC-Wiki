import type { EvidenceRecord, EvidenceTarget } from '../components/EvidenceWorkflow'

export interface ManualItem {
  id: string
  kind: 'text' | 'image' | 'text_file' | 'pdf'
  text?: string
  filename?: string
  source_description: string
  ai_read_status?: string
}
export interface ManualRecord {
  id?: string
  changed: boolean
  before_value?: unknown
  after_value?: unknown
  actor_user_id?: number
  actor_name?: string
  status?: string
  reason: string
  no_evidence_reason: string
  items: ManualItem[]
  history?: ManualRecord[]
}
export interface ManualDraft {
  reason: string
  absence: string
  choice: 'provide' | 'none' | ''
  files: File[]
  revision: number
  writes: number
  dirty: boolean
  busy: boolean
  saved: ManualRecord | null
  error: string
  notice: string
}

/** 只作为浏览器草稿身份；最终语义变化和版本仍由服务端判定。 */
export function manualValueIdentity(value: unknown): string {
  if (typeof value === 'string' && /^[\[{]/.test(value.trim())) {
    try { value = JSON.parse(value) } catch { /* 普通文字保持原样。 */ }
  }
  return JSON.stringify(value, (_key, entry) => entry && typeof entry === 'object' && !Array.isArray(entry)
    ? Object.fromEntries(Object.keys(entry).sort().map(key => [key, entry[key]])) : entry) ?? 'undefined'
}
export function manualFieldIdentity(target: EvidenceTarget | undefined, record: EvidenceRecord) {
  const field = record.state_key
    ? [record.state_key, record.module_key, record.record_key, record.field.split('.').at(-1)].join(':')
    : record.field
  return `${target?.target}:${target?.target_id}:${record.item_key || field}`
}
export const manualDraftKey = (target: EvidenceTarget | undefined, record: EvidenceRecord, value: unknown) =>
  `${manualFieldIdentity(target, record)}|${manualValueIdentity(value)}`

/** 编辑工作流持有；侧栏卸载不丢草稿，整体版本变化不改变字段/值身份。 */
export function createManualEvidenceDrafts() {
  const drafts = new Map<string, ManualDraft>()
  const aliases = new Map<string, string>()
  const listeners = new Set<() => void>()
  const read = (key: string): ManualDraft => {
    key = aliases.get(key) || key
    if (!drafts.has(key)) drafts.set(key, { reason: '', absence: '', choice: '', files: [], revision: 0,
      writes: 0, dirty: false, busy: false, saved: null, error: '', notice: '' })
    return drafts.get(key)!
  }
  const patch = (key: string, changes: Partial<ManualDraft>) => {
    key = aliases.get(key) || key
    drafts.set(key, { ...read(key), ...changes })
    listeners.forEach(listener => listener())
  }
  return {
    read, patch,
    adopt(from: string, to: string) {
      if (from === to || !drafts.has(from)) return
      if (drafts.get(to)?.dirty || drafts.get(to)?.busy) return
      drafts.set(to, read(from))
      drafts.delete(from)
      aliases.set(from, to)
      listeners.forEach(listener => listener())
    },
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
    edit(key: string, changes: Partial<Pick<ManualDraft, 'reason' | 'absence' | 'choice' | 'files'>>) {
      patch(key, { ...changes, revision: read(key).revision + 1, dirty: true, error: '', notice: '' })
    },
    hydrate(key: string, saved: ManualRecord, writes: number) {
      const current = read(key)
      if (current.writes !== writes) return
      patch(key, { saved, ...(!current.dirty && !current.busy ? {
        reason: saved.reason || '', absence: saved.no_evidence_reason || '',
        choice: saved.items?.length ? 'provide' : saved.no_evidence_reason ? 'none' : '',
      } : {}) })
    },
    acknowledge(key: string, saved: ManualRecord, revision: number, file?: File) {
      const current = read(key)
      const files = file ? current.files.filter(entry => entry !== file) : current.files
      patch(key, { saved: { ...current.saved, ...saved }, files, writes: current.writes + 1,
        dirty: current.revision !== revision || files.length > 0 })
    },
    hasPending: (target?: EvidenceTarget) => [...drafts.entries()].some(([key, draft]) =>
      (!target || key.startsWith(`${target.target}:${target.target_id}:`)) && (draft.dirty || draft.files.length > 0 || draft.busy)),
    discard(key: string) { drafts.delete(aliases.get(key) || key); listeners.forEach(listener => listener()) },
    previous(field: string, key: string) {
      return [...drafts.entries()].filter(([entryKey, entry]) => entryKey.startsWith(`${field}|`) && entryKey !== key
        && (entry.dirty || entry.files.length)).map(([entryKey, entry]) => ({ key: entryKey, draft: entry }))
    },
  }
}
export type ManualEvidenceDrafts = ReturnType<typeof createManualEvidenceDrafts>

export interface PreparedManualEvidence {
  endpoint: string
  version: string
  isCurrent: () => boolean
  complete: () => void
}
