import ReviewSection from './ReviewSection'
import EvidenceReviewSummary from './EvidenceReviewSummary'
import ReviewFieldSettings from './ReviewFieldSettings'
import EvidenceHistoryTimeline, { type AuditEvent } from './EvidenceHistoryTimeline'
import type { ManualRecord } from '../lib/manualEvidenceDrafts'
import { EvidenceRegion } from './EvidenceRegion'
import EvidenceReadableValue from './EvidenceReadableValue'
import ManualEvidenceSection from './ManualEvidenceSection'
import ScientificAssociations, { type ScientificAssociation } from './ScientificAssociations'
import DosFermiConflict, { dosRecordForEvidence } from './DosFermiConflict'
import { hasDosConflict, sameDosValue } from '../lib/fermiDos'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Alert, Box, Button, LinearProgress, Dialog, DialogActions, DialogContent, DialogTitle, Drawer, IconButton, Snackbar, Tabs, Tab, TextField, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../lib/api'
import { evidenceProblem } from './EvidenceFieldMarkers'
import { createEvidenceDraftQueue } from '../lib/evidenceDraftQueue'
import { createManualEvidenceDrafts, manualDraftKey, manualFieldIdentity, manualValueIdentity, type PreparedManualEvidence } from '../lib/manualEvidenceDrafts'
import { changedScientificFields } from '../lib/evidenceFields'
import { useLanguage } from '../context/LanguageContext'

export interface EvidenceSource { paper_evidence_id?: number; block_id?: string; evidence_kind?: 'text' | 'pdf_image'; file_id: string; source_name?: string; chunk_id?: number; chunk_index: number; page_start?: number; page_end?: number; content?: string; quote?: string }
export interface ProposalField { path: string; label: string; value: unknown; schema: { type: string; enum?: string[] } }
export interface ProposalDraft { values: Record<string, unknown>; accepted: boolean; reason: string; supported?: boolean }
export type EvidenceBasis = 'paper_quote' | 'paper_inference' | 'general_knowledge'
export interface EvidenceHistory {
  audit_events?: AuditEvent[]
  legacy_scope?: string
  current_value?: unknown
  reason?: string
  ai_reason?: string
  adopted_basis?: EvidenceBasis
  evidences?: EvidenceSource[]
  proposal?: EvidenceRecord['proposal']
  decision?: EvidenceRecord['decision']
}
export interface EvidenceRecord { detail_ref?: string; field_decision?: {contract: string; action: 'approve' | 'reject'; actor_user_id: number; actor_name?: string; occurred_at: string}; settings_field?: string; settings_part?: 'name' | 'kind' | 'raw' | 'unit'; structure_field?: string; human_modified?: boolean; pending_review?: boolean; content_hash?: string; source_hash?: string; record_group_key?: string; audit_events?: AuditEvent[]; record_field?: string; record_field_key?: string; record_dependencies?: string[]; state_dependencies?: string[]; dependency_policy_version?: number; owner_label?: string; legacy_evidences?: EvidenceSource[]; dependency?: string; module_code?: string; dos_fermi_conflict?: boolean; source_associations?: ScientificAssociation[]; history?: EvidenceHistory[]; placeholder?: boolean; required?: boolean; adopted_basis?: EvidenceBasis; auto_filled?: boolean; ai_reason?: string; check_mode?: 'synthesis'; proposal_review?: {status: string; explanation: string}; human_confirmed?: boolean; source_kind?: string; proposal?: { basis_kind?: EvidenceBasis; explanation?: string; values: Record<string, unknown>; supported: boolean; evidences: EvidenceSource[] }; proposal_draft?: ProposalDraft; decision?: { actor_user_id: number; reason: string; supported?: boolean; accepted?: boolean; basis_kind?: EvidenceBasis }; editable_fields?: ProposalField[]; key: string; item_key?: string; field: string; fields?: string[]; label: string; current_value?: unknown; status: 'unchecked' | 'supported' | 'unsupported' | 'uncertain' | 'missing'; reason: string; suggestion?: string; evidences: EvidenceSource[]; stale?: boolean; resolution?: string; structure_hash?: string; state_key?: string; module_key?: string; record_key?: string; provenance?: { kind: string; submitted_by_name?: string; filename?: string; original_text?: string; method?: string; rule?: string; input?: unknown; verified?: boolean; paper_supported?: boolean } }
interface Preflight { job_id?: string; version: string; needs_check: boolean; records: EvidenceRecord[]; manual_pending_keys?: string[] }
interface FieldDetail { record?: Partial<EvidenceRecord>; history?: EvidenceHistory[]; review_token?: string; can_approve?: boolean; source_state?: string }
interface Job { timeout_seconds?: number; id: string; status: string; version?: string; progress?: string; completed_batches?: number; total_batches?: number; current_batch?: number; records?: EvidenceRecord[]; error?: { code: string; message: string } }
export interface EvidencePayload { evidence_job_id?: string; expected_evidence_version: string; evidence_resolutions: Record<string, string> }
export interface EvidenceTarget { target: 'upload' | 'paper' | 'revision'; target_id: string }
interface View { phase: 'checking' | 'countdown' | 'running' | 'error'; seconds?: number; message?: string; job?: Job }
const base = '/api/rag/evidence'
const problematic = evidenceProblem
function dosValueInput(record: EvidenceRecord) {
  const row = Array.from(document.querySelectorAll<HTMLElement>('[data-record-key]')).find(node =>
    node.dataset.recordKey === record.record_key
    && (!record.state_key || node.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey === record.state_key)
    && (!record.module_key || node.closest<HTMLElement>('[data-module-key]')?.dataset.moduleKey === record.module_key))
  return row?.querySelector<HTMLInputElement>('[data-dos-current-value] input')
}

export function aiReasonText(record: EvidenceRecord, t: (key: string) => string): string {
  if (record.provenance?.kind === 'author_keywords' || record.source_kind === 'author_keywords') {
    return record.ai_reason || record.reason || t('evidence.authorKeywordsSource')
  }
  const synthesis = (record.check_mode === 'synthesis' || record.source_kind === 'paper_synthesis')
    && record.provenance?.kind !== 'author_keywords' && record.provenance?.kind !== 'derived'
    && record.source_kind !== 'human_review'
  if (synthesis) {
    const explanation = record.ai_reason || record.proposal?.explanation || record.reason || ''
    const compact = explanation.replace(/[\s，,。.!；;：:]+/g, '')
    if (compact.length >= 12 && !['原文直接记载无需额外推断', '原文直接记载', '与原文一致',
      '原文支持', '论文原文支持', '已阅读当前论文全部有效正文窗口并提炼关键词'].includes(compact)) {
      return explanation
    }
    return t('evidence.synthesisReasonMissing')
  }
  return record.ai_reason || record.proposal?.explanation || record.reason || ''
}


// 运行任务与持久问题列表分开；关闭抽屉不清除任何核对结果。
export function useEvidenceWorkflow(options?: {
  target?: EvidenceTarget
  readOnly?: boolean
  getCurrentValue?: (record: EvidenceRecord) => { value: unknown; field: string; record_key?: string; manualValue?: unknown; comparisonValue?: unknown } | undefined
  saveCurrent?: () => Promise<boolean>
}) {
  const { t } = useLanguage()
  const [view, setView] = useState<View | null>(null)
  const [automatic, setAutomatic] = useState(false)
  const [records, setRecords] = useState<EvidenceRecord[]>([])
  const [drawerTab, setDrawerTab] = useState('source')
  const [settingsPending, setSettingsPending] = useState(false)
  const settingsPendingRef = useRef(false)
  const [discardSettingsOpen, setDiscardSettingsOpen] = useState(false)
  const reportSettingsPending = useCallback((pending: boolean) => {
    settingsPendingRef.current = pending; setSettingsPending(pending)
  }, [])
  const [issueListOpen, setIssueListOpen] = useState(false)
  const [manualHistory, setManualHistory] = useState<Record<string, ManualRecord[]>>({})
  const receiveManualHistory = useCallback((key: string, entries: ManualRecord[]) => setManualHistory(old => JSON.stringify(old[key]) === JSON.stringify(entries) ? old : { ...old, [key]: entries }), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [fallbackRecord, setFallbackRecord] = useState<EvidenceRecord | undefined>()
  const [sourceDetail, setSourceDetail] = useState<{key: string; ref?: string; data?: FieldDetail; error?: string}>()
  const [detailReload, setDetailReload] = useState(0)
  const [manualOpenKey, setManualOpenKey] = useState<string>()
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [saveError, setSaveError] = useState('')
  const [manualNotice, setManualNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const confirmingRef = useRef(false)
  const decisionEpoch = useRef(0)
  const fieldDecisionEpoch = useRef(new Map<string, number>())
  const saveManualBeforeReview = useRef<(() => Promise<boolean>) | null>(null)
  const editRevision = useRef(0)
  const dirty = useRef(false)
  const localReasons = useRef(new Map<string, string>())
  const optionsRef = useRef(options)
  optionsRef.current = options
  const observedValues = useRef(new Map<string, unknown>())
  const invalidationTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const pendingEdits = useRef<Array<{ field: string; pathKind: 'current' | 'snapshot' }>>([])
  const copyValue = (value: unknown) => value === undefined ? undefined : JSON.parse(JSON.stringify(value))
  // 只初始化新身份；后续值在处理编辑通知时推进，避免原生事件迟到后漏掉变化。
  useLayoutEffect(() => {
    for (const record of records) {
      const key = record.item_key || record.key
      const current = optionsRef.current?.getCurrentValue?.(record)
      if (current && !observedValues.current.has(key)) observedValues.current.set(key, copyValue(current.comparisonValue ?? current.value))
      else if (current && manualValueIdentity(observedValues.current.get(key)) !== manualValueIdentity(current.comparisonValue ?? current.value)) invalidate(current.field)
      else if (!current && optionsRef.current?.getCurrentValue && !record.structure_hash && !record.placeholder) invalidate(record.field, 'snapshot')
    }
  })
  useEffect(() => () => { clearTimeout(invalidationTimer.current) }, [])
  const manualCurrentValue = (record: EvidenceRecord) => {
    const current = optionsRef.current?.getCurrentValue?.(record)
    return current ? ('manualValue' in current ? current.manualValue : current.value) : record.current_value
  }
  const hasLocalManualEdit = (record: EvidenceRecord) => {
    if (record.record_field) {
      const current = optionsRef.current?.getCurrentValue?.(record)
      return Boolean(current && manualValueIdentity(current.value) !== manualValueIdentity(record.current_value))
    }
    if (record.stale) return true
    const current = optionsRef.current?.getCurrentValue?.(record)
    const dos = dosRecordForEvidence(record)
    if (dos && current?.value && typeof current.value === 'object') {
      return !sameDosValue(dos, current.value as import('../lib/propertyModules').PropertyRecordDraft)
    }
    // 科学记录的服务器值含材料条件，不能直接与编辑器的原始记录对象比较。
    return Boolean(current && typeof current.value !== 'object' && typeof record.current_value !== 'object'
      && manualValueIdentity(current.value) !== manualValueIdentity(record.current_value))
  }
  const [manualDrafts] = useState(createManualEvidenceDrafts)
  useEffect(() => {
    const protect = (event: BeforeUnloadEvent) => {
      if (manualDrafts.hasPending()) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [manualDrafts])
  const recordsRef = useRef(records)
  recordsRef.current = records
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const generation = useRef(0)
  const cancelLateJob = useRef(true)
  const jobID = useRef<string | undefined>(undefined)
  const lastRetryKeys = useRef<string[] | undefined>(undefined)
  const completed = useRef(false)
  const pending = useRef<((value: EvidencePayload | null) => void) | undefined>(undefined)
  const targetRef = useRef<EvidenceTarget | undefined>(options?.target)
  const preflightRef = useRef<Preflight | undefined>(undefined)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const timerDone = useRef<(() => void) | undefined>(undefined)
  const mounted = useRef(true)
  const targetIdentity = useRef('')
  const queues = useRef(new Map<string, ReturnType<typeof createEvidenceDraftQueue>>())
  const queueFor = (target: EvidenceTarget) => {
    const identity = `${target.target}:${target.target_id}`
    let queue = queues.current.get(identity)
    if (!queue) {
      queue = createEvidenceDraftQueue(state => {
        if (!mounted.current || targetIdentity.current !== identity) return
        setSaving(state.saving)
        if (state.error) setSaveError(state.error.message)
        else if (state.saving) setSaveError('')
      })
      queues.current.set(identity, queue)
    }
    return queue
  }
  const flushDrafts = () => targetRef.current ? queueFor(targetRef.current).flush() : Promise.resolve()
  const retryDrafts = () => targetRef.current ? queueFor(targetRef.current).retry() : Promise.resolve()
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      for (const queue of queues.current.values()) void queue.flush().catch(() => undefined)
    }
  }, [])
  const [, setSelectedKeys] = useState<string[]>([])
  const drawerSession = useRef(0)
  const drawerReturn = useRef<{ trigger: HTMLElement; field: HTMLElement | null; anchor: HTMLElement; top: number; scroller: Element | null } | null>(null)
  const preserveDrawerPosition = () => {
    const origin = drawerReturn.current
    if (origin?.anchor.isConnected && origin.scroller) origin.scroller.scrollTop += origin.anchor.getBoundingClientRect().top - origin.top
  }
  // 核对记录变化时在绘制前保持阅读位置，避免关闭动画期间先下移再跳回。
  useLayoutEffect(() => { preserveDrawerPosition() }, [records])
  const openIssue = (key: string, keys?: string[], fallback?: EvidenceRecord, tab: 'source' | 'settings' = 'source') => {
    setDrawerTab(tab); setIssueListOpen(false)
    setFallbackRecord(fallback)
    drawerSession.current += 1
    const trigger = document.activeElement
    if (trigger instanceof HTMLElement && !trigger.closest('.evidence-review-drawer')) {
      const field = trigger.closest<HTMLElement>('[data-issue-field],.MuiFormControl-root')
      const anchor = field || trigger
      let scroller = anchor.parentElement
      while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) scroller = scroller.parentElement
      drawerReturn.current = { trigger, field, anchor, top: anchor.getBoundingClientRect().top, scroller: scroller || document.scrollingElement }
    }
    setSelected(key); setSelectedKeys(keys || [key]); setSaveError(targetRef.current ? queueFor(targetRef.current).error()?.message || '' : '')
    if (fallback?.placeholder && targetRef.current && optionsRef.current?.saveCurrent && !optionsRef.current.readOnly
        && (fallback.field.startsWith('paper.') || fallback.field.startsWith('material_states[') || fallback.structure_field)) {
      const session = drawerSession.current
      void (async () => {
        try {
          // 查看只定位已保存的字段；未保存的值继续由父草稿持有，不能在打开时顺带保存。
          const {record} = await api.post<{record: EvidenceRecord}>(`${base}/identify-field`, { ...targetRef.current,
            field: fallback.field, state_key: fallback.state_key, module_key: fallback.module_key,
            record_key: fallback.record_key, record_field_key: fallback.record_field_key,
            structure_field: fallback.structure_field, structure_hash: fallback.structure_hash })
          if (drawerSession.current !== session) return
          setRecords(old => [...old.filter(r => r.key !== record.key), record])
          setSelected(record.key); setSelectedKeys([record.key]); setFallbackRecord(undefined)
        } catch (error) { if (drawerSession.current === session) setSaveError((error as Error).message) }
      })()
    }

  }
  useEffect(() => {
    if (!selected || !targetRef.current) return
    let active = true
    const record = recordsRef.current.find(r => r.key === selected)
    if (!record || record.placeholder) return
    const target = targetRef.current
    const epoch = fieldDecisionEpoch.current.get(selected) || 0
    const params = new URLSearchParams({ ...target, item_key: record.item_key || record.key, history: String(drawerTab === 'history') })
    const history = drawerTab === 'history'
    if (!history) setSourceDetail({key: selected, ref: record.detail_ref})
    void api.get<FieldDetail>(`${base}/field-detail?${params}`).then(result => {
      if (!active || epoch !== (fieldDecisionEpoch.current.get(selected) || 0)) return
      if (!history && (!result.record || !result.review_token || !['available', 'empty', 'historical'].includes(result.source_state || ''))) {
        throw new Error(t('evidence.sourceResponseInvalid'))
      }
      if (history) setRecords(old => old.map(r => r.key === selected ? {...r, history: result.history || []} : r))
      else setSourceDetail({key: selected, ref: record.detail_ref, data: result})
    }).catch(error => { if (active && epoch === (fieldDecisionEpoch.current.get(selected) || 0)) {
      if (history) setSaveError((error as Error).message)
      else setSourceDetail({key: selected, ref: record.detail_ref, error: (error as Error).message})
    } })
    return () => { active = false }
  }, [selected, drawerTab, detailReload, records.find(r => r.key === selected)?.detail_ref])
  const closeDrawer = useCallback(() => {
    if (settingsPendingRef.current) { setDiscardSettingsOpen(true); return }
    setDiscardSettingsOpen(false)
    drawerSession.current += 1
    void flushDrafts().catch(() => undefined)
    setManualOpenKey(undefined)
    setSelected(null)
  }, [])
  useEffect(() => {
    if (!selected) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); closeDrawer() } }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [selected, closeDrawer])
  const waiting = view?.phase === 'checking' || view?.phase === 'running'
  useEffect(() => {
    setElapsedSeconds(0)
    if (!waiting) return
    const started = Date.now()
    const interval = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [waiting])
  const pause = (ms: number) => new Promise<void>(resolve => { timerDone.current = resolve; timer.current = setTimeout(resolve, ms) })
  const finish = useCallback((value: EvidencePayload | null, cancelJob = true) => {
    cancelLateJob.current = cancelJob
    generation.current += 1
    clearTimeout(timer.current)
    timerDone.current?.()
    timerDone.current = undefined
    if (cancelJob && value === null && jobID.current && !completed.current) void api.del(`${base}/jobs/${jobID.current}`).catch(() => undefined)
    pending.current?.(value)
    pending.current = undefined
    setView(null)
    setSelected(null)
  }, [])
  useEffect(() => () => { finish(null, false) }, [finish])

  const restore = useCallback(async (target: EvidenceTarget) => {
    const epoch = decisionEpoch.current
    const current = ++generation.current
    const revision = editRevision.current
    const identity = `${target.target}:${target.target_id}`
    if (targetIdentity.current !== identity) {
      localReasons.current.clear(); dirty.current = false
      setSourceDetail(undefined); setSelected(null); setManualOpenKey(undefined)
      clearTimeout(invalidationTimer.current); pendingEdits.current = []
    }
    const previousTarget = targetRef.current
    targetRef.current = target
    targetIdentity.current = identity
    if (previousTarget) await queueFor(previousTarget).flush().catch(() => undefined)
    if (!mounted.current || generation.current !== current || editRevision.current !== revision) return
    try {
      const result = await api.post<Preflight>(`${base}/summary`, target)
      if (generation.current !== current || editRevision.current !== revision || epoch !== decisionEpoch.current) return
      preflightRef.current = result
      observedValues.current.clear()
      recordsRef.current = result.records || []
      setRecords(result.records || [])
      if (!queueFor(target).hasPending()) {
        setReasons(Object.fromEntries((result.records || []).map(r => [r.key, localReasons.current.get(r.item_key || r.key) ?? (r.stale ? '' : r.proposal_draft?.reason ?? r.resolution ?? '')])))
      }
      return result
    } catch (error) { if (generation.current === current) setSaveError((error as Error).message); return undefined }
  }, [])
  // 普通保存与侧栏确认共用；刷新不能覆盖请求之后发生的编辑。
  const refreshAfterSave = async (revision: number) => {
    if (revision !== editRevision.current) return false
    dirty.current = false
    return true
  }

  useEffect(() => {
    if (options?.target) void restore(options.target)
  }, [options?.target?.target, options?.target?.target_id, restore])

  const prepareManual = async (record: EvidenceRecord): Promise<PreparedManualEvidence> => {
    const target = targetRef.current
    if (!target) throw new Error(t('evidence.manualContextMissing'))
    const identity = `${target.target}:${target.target_id}`
    const session = drawerSession.current
    const hadCurrent = Boolean(optionsRef.current?.getCurrentValue?.(record))
    const value = () => manualCurrentValue(record)
    const expectedValue = manualValueIdentity(value())
    const isCurrent = () => mounted.current && identity === targetIdentity.current
      && (!optionsRef.current?.target || `${optionsRef.current.target.target}:${optionsRef.current.target.target_id}` === identity)
      && (!hadCurrent || Boolean(optionsRef.current?.getCurrentValue?.(record)))
      && manualValueIdentity(value()) === expectedValue
    const saveCurrent = optionsRef.current?.saveCurrent
    if (saveCurrent && !(await saveCurrent())) throw new Error(t('evidence.saveFirstFailed'))
    if (!isCurrent()) throw new Error(t('evidence.changedDuringSave'))
    const params = new URLSearchParams({...target, item_key: record.item_key || record.key})
    const fresh = await api.get<{version: string; record: EvidenceRecord}>(`${base}/manual-context?${params}`)
    if (!fresh || !isCurrent()) throw new Error(t('evidence.changedDuringSave'))
    const current = fresh.record
    if (!current?.item_key || !/^[0-9a-f]{64}$/.test(current.item_key)) throw new Error(t('evidence.manualContextMissing'))
    manualDrafts.adopt(manualDraftKey(target, record, value()), manualDraftKey(target, current, value()))
    return {
      endpoint: `${base}/${target.target}/${target.target_id}/manual/${current.item_key}`,
      version: fresh.version, isCurrent,
      complete: () => { if (isCurrent() && drawerSession.current === session) {
        setManualNotice(t('common.saved'))
        setRecords(old => old.map(r => r.key === record.key ? {...r, pending_review: true, human_modified: true} : r))
        setDetailReload(value => value + 1)
      } },
    }
  }

  const payload = (preflight: Preflight, resolutions: Record<string, string> = {}): EvidencePayload => ({ evidence_job_id: jobID.current, expected_evidence_version: preflight.version, evidence_resolutions: resolutions })
  const showResults = (next: EvidenceRecord[], preflight: Preflight, silent = false) => {
    setRecords(next)
    setReasons(Object.fromEntries(next.map(r => [r.key, r.proposal_draft?.reason ?? r.resolution ?? ''])))
    pending.current?.(payload(preflight))
    pending.current = undefined
    setView(null)
    const disputed = next.filter(problematic)
    if (disputed.length && !silent) openIssue(disputed[0].key)
  }
  // 提交复用已通过项；后端只为尚未核对的实际修改排队。
  const gate = async (target: EvidenceTarget): Promise<EvidencePayload | null> => {
    const current = ++generation.current
    setSaveError('')
    completed.current = false
    await flushDrafts()
    targetRef.current = target
    setAutomatic(false)
    setView({ phase: 'checking', message: '正在检查本次提交的必要字段' })
    try {
      if (manualDrafts.hasPending(target)) throw new Error(t('evidence.saveManualBeforeSubmit'))
      let result = await api.post<Job & Preflight & { program_issues?: Array<{field: string; message: string}> }>(`${base}/submit-check`, target)
      if (current !== generation.current) return null
      if (result.program_issues?.length) { setRecords(result.records || []); throw new Error(result.program_issues.map(i => '程序检查：' + i.message).join('；')) }
      const id = result.id
      const deadline = Date.now() + ((result.timeout_seconds || 1800) + 60) * 1000
      while (result.status === 'queued' || result.status === 'running') {
        if (Date.now() > deadline) throw new Error(t('evidence.timeout'))
        jobID.current = id
        setView({ phase: 'running', job: result, message: result.progress || '等待必要字段核对' })
        await pause(1000)
        if (current !== generation.current) return null
        result = await api.get<Job & Preflight>(`${base}/jobs/${id}`)
        if (current !== generation.current) return null
      }
      if (result.status !== 'completed') throw new Error(result.error?.message || '核对未完成，未提交')
      completed.current = true
      const next = (result.records || []).map(r => ({ ...r, pending_review: false }))
      recordsRef.current = next
      setRecords(next)
      const blocked = next.filter(r => r.field_decision?.action === 'reject' || (r.required !== false || r.human_modified) && (r.stale || r.status !== 'supported'))
      if (blocked.length) { openIssue(blocked[0].key); setSaveError('这些字段尚未通过审核，未提交'); return null }
      return { evidence_job_id: id, expected_evidence_version: result.version, evidence_resolutions: {} }
    } catch (error) {
      const failure = error as import('../lib/api').ApiError
      setSaveError(failure.issues?.map(issue => {
        const label = recordsRef.current.find(r => r.field === issue.field)?.label
        return (label ? label + '：' : '') + issue.message
      }).join('；') || failure.message)
      return null
    }
    finally { setView(null) }
  }
  const applyAccepted = async (target: EvidenceTarget, save: (patches: import('../lib/evidenceProposals').EvidencePatch[], preparationId: string, resumeStage?: 'scientific' | 'finalize') => Promise<boolean>) => {
    await flushDrafts()
    const current = await api.post<Preflight>(`${base}/preflight`, target)
    const prepared = await api.post<import('../lib/evidenceProposals').PreparedProposals>(`${base}/proposals/prepare`, { ...target, expected_version: current.version })
    if (!prepared.preparation_id) return true
    if (prepared.resume_stage !== 'finalize' && !(await save(prepared.patches, prepared.preparation_id, prepared.resume_stage))) return false
    await api.post(`${base}/proposals/finalize`, { ...target, preparation_id: prepared.preparation_id })
    await restore(target)
    return true
  }

  const execute = async (target: EvidenceTarget, retryKeys?: string[], silent = false, attempt = 0) => {
    lastRetryKeys.current = retryKeys
    const retryItems = retryKeys && new Set(retryKeys.map(key => {
      const record = recordsRef.current.find(r => r.key === key)
      return record?.item_key || key
    }))
    targetIdentity.current = `${target.target}:${target.target_id}`
    cancelLateJob.current = true
    const current = ++generation.current
    const saveCurrent = optionsRef.current?.saveCurrent
    const revision = editRevision.current
    const active = () => mounted.current && generation.current === current && (!optionsRef.current?.target || (optionsRef.current.target.target === target.target && optionsRef.current.target.target_id === target.target_id))
    completed.current = false
    jobID.current = undefined
    setSaveError('')
    try {
      // 先保存当前侧栏的人工依据，再卸载侧栏；不能静默核对旧说明。
      if (retryKeys && saveManualBeforeReview.current && !(await saveManualBeforeReview.current())) return
      if (!active()) return
      setSelected(null)
      await flushDrafts()
      if (!active()) return
      if (retryKeys && saveCurrent) {
        if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
        if (!(await saveCurrent())) throw new Error(t('evidence.saveFirstFailed'))
        if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
        dirty.current = false
      }
      if (!active()) return
      setView({ phase: 'checking', message: t('evidence.checking') })
      const preflight = await api.post<Preflight>(`${base}/summary`, target)
      if (!active()) return
      if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
      preflightRef.current = preflight
      if (retryItems) {
        retryKeys = preflight.records.filter(r => retryItems.has(r.item_key || r.key)).map(r => r.key)
        if (!retryKeys.length) { showResults(preflight.records, preflight, silent); return }
      }
      if (target.target !== 'paper' && !retryKeys && !preflight.needs_check && !preflight.records.some(r => r.status === 'unchecked')) { jobID.current = preflight.job_id; completed.current = true; showResults(preflight.records, preflight, silent); return }
      for (let seconds = silent || retryKeys ? 0 : 3; seconds > 0; seconds--) {
        setView({ phase: 'countdown', seconds, message: t('evidence.startHint') })
        await pause(1000)
        if (!active()) return
      }
      setView({ phase: 'running', message: t('evidence.starting') })
      const job = preflight.job_id && !retryKeys
        ? { id: preflight.job_id, timeout_seconds: 1800 }
        : await api.post<Job>(`${base}/jobs`, { ...target, expected_draft_version: preflight.version, purpose: retryKeys ? 'field' : 'submit', ...(retryKeys ? { retry_keys: retryKeys } : {}) })
      if (!active()) { if (cancelLateJob.current) void api.del(`${base}/jobs/${job.id}`).catch(() => undefined); return }
      jobID.current = job.id
      const deadline = Date.now() + ((job.timeout_seconds || 600) + 60) * 1000
      while (active()) {
        const result = await api.get<Job>(`${base}/jobs/${job.id}`)
        if (!active()) return
        if (result.status === 'completed') {
          if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
          completed.current = true
          if (result.version) preflight.version = result.version
          if (retryItems) {
            const selectedResults = (result.records || []).filter(r => retryItems.has(r.item_key || r.key))
            setRecords(old => old.map(r => selectedResults.find(fresh => (fresh.item_key || fresh.key) === (r.item_key || r.key)) || r))
            setView(null)
            const reviewed = selectedResults[0]
            if (reviewed?.status === 'supported' && !reviewed.stale && !reviewed.pending_review) setManualNotice(t('evidence.fieldReviewSaved'))
            else if (reviewed) openIssue(reviewed.key)
          } else showResults(result.records || [], preflight, silent)
          return
        }
        if (result.status === 'failed') throw new Error(result.error?.message || t('evidence.failed'))
        if (result.status === 'cancelled') { finish(null); return }
        if (Date.now() > deadline) throw new Error(t('evidence.timeout'))
        setView({ phase: 'running', job: result, message: result.status === 'queued' ? t('evidence.queued') : result.progress || t('evidence.running') })
        await pause(1000)
      }
    } catch (error) {
      if (active()) {
        if (jobID.current && !completed.current) void api.del(`${base}/jobs/${jobID.current}`).catch(() => undefined)
        if (silent && attempt === 0) void execute(target, retryKeys, true, 1)
        else setView({ phase: 'error', message: (error as Error).message })
      }
    }
  }
  const run = (target: EvidenceTarget): Promise<EvidencePayload | null> => {
    if (pending.current) { setSelected(records.find(problematic)?.key || null); return Promise.resolve(null) }
    targetRef.current = target
    setAutomatic(false)
    return new Promise(resolve => { pending.current = resolve; void execute(target) })
  }
  const runAutomatic = (target: EvidenceTarget) => {
    if (view && view.phase !== 'error') return
    targetRef.current = target
    setAutomatic(true)
    void execute(target, undefined, true)
  }
  const invalidate = useCallback((field: string, pathKind: 'current' | 'snapshot' = 'current') => {
    editRevision.current += 1
    pendingEdits.current.push({ field, pathKind })
    const flush = () => {
      invalidationTimer.current = undefined
      const edits = pendingEdits.current.splice(0)
      const getCurrent = optionsRef.current?.getCurrentValue
      const currentRecords = recordsRef.current.map(record => {
        const current = getCurrent?.(record)
        return current ? { ...record, field: current.field, record_key: current.record_key || record.record_key,
          fields: record.fields?.map(field => field.startsWith(record.field) ? current.field + field.slice(record.field.length) : field) } : record
      })
      const changes = new Set<string>()
      const removed = new Set<string>()
      const removedPaths: string[] = []
      if (getCurrent) {
        for (const record of recordsRef.current) {
          const key = record.item_key || record.key
          const current = getCurrent(record)
          if (observedValues.current.has(key)) {
            if (current) changedScientificFields(observedValues.current.get(key), current.comparisonValue ?? current.value, current.field).forEach(path => changes.add(path))
            else if (!record.structure_hash) { removed.add(record.key); removedPaths.push(record.field) }
          }
          if (current) observedValues.current.set(key, copyValue(current.comparisonValue ?? current.value))
        }
      }
      // 结构等只读摘要沿用显式编辑通知；可读字段必须以实际值差异为准。
      for (const edit of edits) {
        if (removedPaths.some(path => path === edit.field || path.startsWith(edit.field + '.') || path.startsWith(edit.field + '['))) continue
        const owner = recordsRef.current.find(record => record.field === edit.field || edit.field.startsWith(record.field + '.') || edit.field.startsWith(record.field + '[')
          || record.field.startsWith(edit.field + '.') || record.field.startsWith(edit.field + '['))
        if (!getCurrent || !owner || owner.structure_hash) {
          const current = owner && getCurrent?.(owner)
          changes.add(edit.pathKind === 'snapshot' && owner && current ? edit.field.replace(owner.field, current.field) : edit.field)
        }
      }
      const relocated = currentRecords.some((record, index) => record.field !== recordsRef.current[index].field
        || record.record_key !== recordsRef.current[index].record_key)
      if (!changes.size && !removed.size) {
        if (relocated) { recordsRef.current = currentRecords; setRecords(currentRecords) }
        return
      }
      dirty.current = true
      // 编辑只移除当前键旧问题；读取上下文不意味着修改上下文字段的结果。
      const affected = new Set(currentRecords.filter(record => removed.has(record.key)
        || [...changes].some(path => path === record.field || path.startsWith(record.field + '.')
          || path.startsWith(record.field + '['))).map(record => record.key))
      const next = currentRecords.filter(r => !removed.has(r.key)).map(r => {
        if (!affected.has(r.key)) return r
        const current = getCurrent?.(r)
        return { ...r, pending_review: r.status !== 'supported' || manualValueIdentity(current?.value) !== manualValueIdentity(r.current_value) }
      })
      recordsRef.current = next
      setRecords(next)
    }
    if (!optionsRef.current?.getCurrentValue) flush()
    else if (invalidationTimer.current === undefined) invalidationTimer.current = setTimeout(flush, 0)
  }, [])
  const issues = useMemo(() => records.filter(problematic), [records])
  const summaryRecord = records.find(r => r.key === selected) || (fallbackRecord?.key === selected ? fallbackRecord : undefined)
  const currentDetail = sourceDetail?.key === selected && sourceDetail?.ref === summaryRecord?.detail_ref ? sourceDetail : undefined
  const activeRecord = summaryRecord && currentDetail?.data?.record ? {...summaryRecord, ...currentDetail.data.record,
    key: summaryRecord.key, field: summaryRecord.field, fields: summaryRecord.fields,
    pending_review: summaryRecord.pending_review || currentDetail.data.record.pending_review} : summaryRecord
  const manualVisible = Boolean(activeRecord && (manualOpenKey === activeRecord.key || activeRecord.field_decision?.action === 'reject'
    || activeRecord.human_modified || hasLocalManualEdit(activeRecord)))
  const canApprove = Boolean(summaryRecord && activeRecord && problematic(summaryRecord) && problematic(activeRecord)
    && currentDetail?.data?.can_approve && !hasLocalManualEdit(activeRecord) && !settingsPending)
  const decideField = async (action: 'approve' | 'reject') => {
    if (!activeRecord || !currentDetail?.data?.review_token || confirmingRef.current) return
    if (action === 'approve' && !canApprove) return
    confirmingRef.current = true; setConfirming(true); setSaveError('')
    const record = activeRecord, session = drawerSession.current, target = targetRef.current
    const currentValue = () => {
      const current = optionsRef.current?.getCurrentValue?.(record)
      return manualValueIdentity(current ? current.comparisonValue ?? current.value : record.current_value)
    }
    const value = currentValue()
    try {
      const result = await api.post<FieldDetail>(`${base}/field-decision`, {...targetRef.current,
        item_key: record.item_key || record.key, action, review_token: currentDetail.data.review_token})
      if (!result.record || result.record.field_decision?.action !== action || (action === 'approve' && result.record.status !== 'supported')) {
        throw new Error(t('evidence.decisionResponseInvalid'))
      }
      if (target?.target !== targetRef.current?.target || target?.target_id !== targetRef.current?.target_id || currentValue() !== value) return
      decisionEpoch.current += 1
      fieldDecisionEpoch.current.set(record.key, (fieldDecisionEpoch.current.get(record.key) || 0) + 1)
      const update = (old: EvidenceRecord[]) => old.map(r => r.key === record.key ? {...r, ...result.record, pending_review: false} : r)
      recordsRef.current = update(recordsRef.current)
      setRecords(update)
      if (drawerSession.current !== session) return
      setSourceDetail({key: record.key, ref: summaryRecord?.detail_ref, data: result})
      if (action === 'approve') { setManualNotice(t('evidence.humanApprovalSaved')); closeDrawer() }
      else setManualOpenKey(record.key)
    } catch (error) { setSaveError((error as Error).message) }
    finally { confirmingRef.current = false; if (mounted.current) setConfirming(false) }
  }
  const restoreDrawerFocus = () => {
    if (!mounted.current || activeRecord || view) return
    const origin = drawerReturn.current
    // 顶部接受列表可能增高；保持原字段在视口的位置，同时兼容嵌套滚动容器。
    preserveDrawerPosition()
    drawerReturn.current = null
    // 接受后原标签恢复普通语义，就回到同一字段的输入框；不查顶部同名入口。
    const trigger = origin?.trigger
    const focusable = 'input:not(:disabled),textarea:not(:disabled),select:not(:disabled),button:not(:disabled),[tabindex]:not([tabindex="-1"])'
    const node = trigger?.isConnected && trigger.tabIndex >= 0 && !trigger.matches(':disabled')
      ? trigger : origin?.field?.isConnected ? origin.field.querySelector<HTMLElement>(focusable) : null
    node?.focus({ preventScroll: true })
  }
  const total = view?.job?.total_batches || 0
  const done = Math.min(total, Math.max(0, view?.job?.completed_batches || 0))
  const percent = total > 0 ? Math.floor(done / total * 100) : undefined
  const batch = view?.job?.current_batch || 0
  const activeGroup = activeRecord ? [activeRecord] : []
  const activeDos = activeRecord ? dosRecordForEvidence(activeRecord) : undefined
  const activeDosConflict = Boolean(activeDos && hasDosConflict(activeDos))
  const activeCurrent = activeRecord ? options?.getCurrentValue?.(activeRecord) : undefined
  const completionBlockers = (saving || confirming) ? [t('evidence.completeBusy')] : []
  const draftSaveFailed = Boolean(targetRef.current && queueFor(targetRef.current).error())
  const editCurrent = (record: EvidenceRecord) => {
    const field = optionsRef.current?.getCurrentValue?.(record)?.field || record.field
    if (record.settings_field && record.settings_part !== 'raw') { setDrawerTab('settings'); return }
    closeDrawer()
    setTimeout(() => {
      if (dosRecordForEvidence(record)) {
        const input = dosValueInput(record)
        if (!input || input.disabled) return
        for (let parent = input.parentElement; parent; parent = parent.parentElement) if (parent instanceof HTMLDetailsElement) parent.open = true
        input.focus({ preventScroll: true })
        const area = input.closest<HTMLElement>('[data-property-core-row]')
        if (area) {
          const fieldBounds = input.getBoundingClientRect(), areaBounds = area.getBoundingClientRect()
          if (fieldBounds.right > areaBounds.right) area.scrollLeft += fieldBounds.right - areaBounds.right + 2
          else if (fieldBounds.left < areaBounds.left) area.scrollLeft += fieldBounds.left - areaBounds.left - 2
        }
        return
      }
      const node = Array.from(document.querySelectorAll<HTMLElement>('[data-issue-field]')).find(n => n.dataset.issueField === field)
      for (let parent = node?.parentElement; parent; parent = parent.parentElement) if (parent instanceof HTMLDetailsElement) parent.open = true
      const input = node?.matches('input,textarea,select') ? node : node?.querySelector<HTMLElement>('input,textarea,select,[role="combobox"]')
      input?.scrollIntoView?.({block: 'center'}); input?.focus()
    }, 320)
  }
  const dialog = <>
    {saveError && !activeRecord && !view && <Alert severity="error" sx={{my: 1}}>{saveError}</Alert>}
    {records.length > 0 && <Button data-evidence-pending-navigation onClick={() => setIssueListOpen(true)}>{t('evidence.pendingItems')}（{issues.length}）</Button>}
    <Dialog open={issueListOpen} onClose={() => setIssueListOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>{t('evidence.pendingItems')}</DialogTitle><DialogContent>
        {!issues.length && <Typography>{t('evidence.noPendingItems')}</Typography>}
        {issues.map(record => <Button key={record.key} fullWidth sx={{ justifyContent: 'start', textAlign: 'left', display: 'block', my: 1 }} onClick={() => openIssue(record.key)}>
          <Typography variant="caption" color="text.secondary">{record.owner_label}</Typography><Typography>{record.label}</Typography>
        </Button>)}
      </DialogContent><DialogActions><Button onClick={() => setIssueListOpen(false)}>{t('common.close')}</Button></DialogActions>
    </Dialog>
    <Snackbar open={Boolean(manualNotice)} autoHideDuration={4000} onClose={() => setManualNotice('')} message={manualNotice} />
    <Dialog open={discardSettingsOpen} onClose={() => setDiscardSettingsOpen(false)} aria-labelledby="discard-field-settings-title">
      <DialogTitle id="discard-field-settings-title">{t('evidence.settingsDiscardTitle')}</DialogTitle>
      <DialogContent>{t('evidence.settingsDiscardQuestion')}</DialogContent>
      <DialogActions>
        <Button onClick={() => setDiscardSettingsOpen(false)}>{t('evidence.settingsContinue')}</Button>
        <Button onClick={() => { reportSettingsPending(false); closeDrawer() }}>{t('evidence.settingsDiscard')}</Button>
      </DialogActions>
    </Dialog>

    <Dialog open={view !== null && !automatic} onClose={() => finish(null)} fullWidth maxWidth="md" aria-labelledby="evidence-workflow-title">
      <DialogTitle id="evidence-workflow-title">{t('evidence.title')}</DialogTitle>
      <DialogContent>
        {view?.phase === 'countdown' && <Alert severity="info">{t('evidence.countdown', { seconds: view.seconds || 0 })}{view.message}</Alert>}
        {waiting && <Box sx={{ py: 1 }}>
          <Typography role="status" sx={{ mb: 2 }}>{total > 0 && batch > done ? t('evidence.currentBatch', { current: batch, total }) : view?.message}</Typography>
          <LinearProgress aria-label={t('evidence.progressLabel')} variant={percent === undefined ? 'indeterminate' : 'determinate'} value={percent} sx={{ height: 8, borderRadius: 4 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mt: 1 }}>
            <Typography variant="body2">{percent === undefined ? t('evidence.waitingHint') : t('evidence.batchProgress', { completed: done, total, percent })}</Typography>
            <Typography variant="body2">{t('evidence.elapsed', { minutes: Math.floor(elapsedSeconds / 60), seconds: elapsedSeconds % 60 })}</Typography>
          </Box>
        </Box>}
        {view?.phase === 'error' && <Alert severity="error">{view.message}</Alert>}
      </DialogContent>
      <DialogActions><Button onClick={() => finish(null)}>{t('common.cancel')}</Button>
        {view?.phase === 'error' && <Button onClick={() => void execute(targetRef.current!, lastRetryKeys.current)}>{t('evidence.retry')}</Button>}
      </DialogActions>
    </Dialog>
    <Drawer anchor="right" variant="temporary" open={Boolean(activeRecord)} onClose={closeDrawer} ModalProps={{ disableRestoreFocus: true }} slotProps={{ transition: { onExited: restoreDrawerFocus }, paper: { role: 'dialog', className: 'evidence-review-drawer', 'aria-label': t('evidence.title'), sx: { width: { xs: '100vw', sm: 480 }, maxWidth: '100vw', p: 3 } } }}>
      {activeRecord && <>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><Typography variant="h6">{activeRecord.label}</Typography><IconButton aria-label={t('evidence.closeDrawer')} onClick={closeDrawer}><CloseIcon /></IconButton></Box>
        <Typography variant="caption" color="text.secondary">{activeRecord.owner_label}</Typography>
        <Tabs value={drawerTab} onChange={(_, value) => setDrawerTab(value)} variant="fullWidth">
          <Tab value="settings" label={t('evidence.settingsTab')} /><Tab value="source" label={t('evidence.sourceTab')} /><Tab value="history" label={t('evidence.historyLabel')} />
        </Tabs>
        <Box hidden={drawerTab !== 'settings'} key={'settings:' + activeRecord.key} sx={{ pt: 2 }}>
          <ReviewFieldSettings identity={activeRecord.item_key || activeRecord.key} field={options?.getCurrentValue?.(activeRecord)?.field || activeRecord.field}
            settingsField={activeRecord.settings_field} sourceField={activeRecord.field}
            enabled={drawerTab === 'settings'} onDone={closeDrawer} onPendingChange={reportSettingsPending}
            label={activeRecord.label} value={activeCurrent ? activeCurrent.value : activeRecord.current_value} />
        </Box>
        <Box hidden={drawerTab !== 'source'} key={'source:' + activeRecord.key}>
        <ReviewSection title={t('evidence.foundSources')} initialOpen>
          <DosFermiConflict record={activeRecord} target={targetRef.current}
            onEdit={dosValueInput(activeRecord) && !dosValueInput(activeRecord)?.disabled ? () => editCurrent(activeRecord) : undefined} />
          {activeRecord.field === 'paper.theoretical_subtype' && <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.subtypeSynthesisHint')}</Alert>}
          {activeRecord.field === 'paper.summary' && !activeRecord.stale && <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.summarySynthesisHint')}</Alert>}
          {activeRecord.field === 'paper.keywords_tags' && activeRecord.provenance?.kind === 'author_keywords' &&
            <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.authorKeywordsSource')}</Alert>}
          {activeRecord.field === 'paper.keywords_tags' && activeRecord.provenance?.kind === 'paper_synthesis' &&
            <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.fulltextKeywordsSource')}</Alert>}
          {currentDetail?.error ? <Alert severity="error" action={<Button onClick={() => setDetailReload(n => n + 1)}>{t('evidence.retrySource')}</Button>}>{t('evidence.sourceLoadFailed')} {currentDetail.error}</Alert>
            : !currentDetail?.data && !activeRecord.placeholder ? <Typography role="status">{t('evidence.sourceLoading')}</Typography>
            : activeDosConflict ? null : activeGroup.some(r => r.evidences.length)
            ? activeGroup.flatMap(r => r.evidences)
              .filter((source, index, all) => all.findIndex(item => item.file_id === source.file_id && item.quote === source.quote) === index)
              .map((source, index) => <EvidenceRegion key={`${source.file_id}:${source.page_start}:${index}`} target={targetRef.current} source={source} />)
            : activeRecord.provenance?.kind === 'derived'
              ? <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.derivedSource')}
                  <Typography>{t('evidence.derivedRule')}：{activeRecord.provenance.rule}</Typography>
                  <EvidenceReadableValue value={activeRecord.provenance.input} />
                </Alert>
              : <Alert severity="info" sx={{ mt: 1 }}>{t('evidence.noPaperSource')}</Alert>}
          {activeRecord.provenance?.kind === 'contributor_structure' && <Alert severity="info" sx={{ mt: 1 }}>
            <Typography>{t('evidence.providerLabel')}：{activeRecord.provenance.submitted_by_name || t('evidence.unknownProvider')}</Typography>
            <Typography>{activeRecord.provenance.filename} · {activeRecord.provenance.method}</Typography>
            {activeRecord.provenance.original_text && <Box component="details"><Box component="summary">{t('evidence.originalStructure')}</Box><Typography component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{activeRecord.provenance.original_text}</Typography></Box>}
          </Alert>}
          {currentDetail?.data?.source_state === 'historical' && <Alert severity="info">{t('evidence.historicalSource')}</Alert>}
          {!activeRecord.placeholder && activeGroup.map(r => <EvidenceReviewSummary key={r.key} record={r} />)}
          {Boolean(activeRecord.legacy_evidences?.length) && !activeRecord.evidences.length && <ReviewSection title={t('evidence.legacySources')}>
            {activeRecord.legacy_evidences!.map((source, index) => <EvidenceRegion key={index} target={targetRef.current} source={source} />)}
          </ReviewSection>}
        </ReviewSection>
        <ReviewSection title={t('evidence.aiReasonLabel')} initialOpen>
        {activeGroup.map(r => <Box key={r.key} sx={{ display: 'grid', gap: 1.5, mb: 2 }}>
          {(r.adopted_basis || r.proposal?.basis_kind) && <Alert severity="info">{t(`evidence.basis.${r.adopted_basis || r.proposal?.basis_kind}`)}</Alert>}
            {(r.pending_review || r.stale) && <Alert severity="info">当前内容待提交核对；下方仅显示已有核对结论。</Alert>}
            <Typography sx={{ whiteSpace: 'pre-wrap' }}>{aiReasonText(r, t) || t('evidence.noAiReason')}</Typography>
            <ScientificAssociations associations={r.source_associations} target={targetRef.current} />
            {r.proposal_review && <Typography>{t('evidence.proposalReview')}：{r.proposal_review.explanation}</Typography>}
            {Boolean(r.proposal?.evidences?.length) && <Box component="details"><Typography component="summary">{t('evidence.aiReasonSources')}</Typography>
              {r.proposal!.evidences.map((source, index) => <EvidenceRegion key={`${source.file_id}:${index}`} target={targetRef.current} source={source} />)}
            </Box>}
        </Box>)}
        </ReviewSection>
        {settingsPending && <Typography color="text.secondary">{t('evidence.settingsPending')}</Typography>}
        {!options?.readOnly && !activeRecord.placeholder && <Box data-field-review-actions sx={{display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: .75, my: 2, '& .MuiButton-root': {minWidth: 0, px: .5, overflowWrap: 'anywhere'}}}>
          <Button disabled={settingsPending || confirming || !currentDetail?.data?.review_token || hasLocalManualEdit(activeRecord)}
            onClick={() => void decideField('reject')}>{t('evidence.humanReject')}</Button>
          <Button variant="contained" disabled={confirming || !canApprove}
            onClick={() => void decideField('approve')}>{t('evidence.humanApprove')}</Button>
          <Button variant="outlined" disabled={settingsPending || confirming || (activeRecord.stale && dirty.current && !options?.saveCurrent)}
            onClick={() => void execute(targetRef.current!, activeGroup.map(r => r.key))}>{t('evidence.reviewCurrentField')}</Button>
        </Box>}
        {manualVisible && <ReviewSection title={t('evidence.manualEditRecords')} initialOpen expand={manualOpenKey === activeRecord.key}>
        <ManualEvidenceSection readOnly={options?.readOnly} showHistory={false} onRecords={receiveManualHistory} target={targetRef.current} record={activeRecord} version={preflightRef.current?.version}
          saveBeforeReview={saveManualBeforeReview}
          drafts={manualDrafts} value={manualCurrentValue(activeRecord)}
          localChanged={hasLocalManualEdit(activeRecord)}
          prepare={() => prepareManual(activeRecord)} />
        {dirty.current && options?.saveCurrent && <Alert severity="info">{t('evidence.saveBeforeConfirm')}</Alert>}
        </ReviewSection>}
        {saveError && <Alert severity="error" sx={{ mt: 1 }} action={draftSaveFailed ? <Button disabled={saving} onClick={() => void retryDrafts().catch(() => undefined)}>{t('evidence.retrySave')}</Button> : undefined}>{saveError} {draftSaveFailed && t('evidence.saveFailureRetained')}</Alert>}
        {!activeRecord.placeholder && completionBlockers.length > 0 && <Alert severity="info" sx={{ mt: 1 }}>{completionBlockers.map(message => <Typography key={message} variant="body2">{message}</Typography>)}</Alert>}
        </Box>
        <Box hidden={drawerTab !== 'history'} key={'history:' + activeRecord.key}>
          <ReviewSection title={t('evidence.historyLabel')}>
            <EvidenceHistoryTimeline record={activeRecord} manual={manualHistory[activeRecord.item_key || activeRecord.key] || []} />
          </ReviewSection>
        </Box>
      </>}
    </Drawer>
  </>
  return { showResults: () => setIssueListOpen(true), hasManualDrafts: manualDrafts.hasPending, refreshAfterSave, getEditRevision: () => editRevision.current, hasUnsavedChanges: () => dirty.current, hasAccepted: records.some(r => !r.stale && r.proposal_draft?.accepted), run, runAutomatic, automaticView: automatic ? view : null, gate, applyAccepted, dialog, busy: view !== null, issues, records, restore, invalidate, openIssue, clearIssues: () => finish(null), saveError }
}
