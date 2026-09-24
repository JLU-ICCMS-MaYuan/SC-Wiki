import { EvidenceRegion } from './EvidenceRegion'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Alert, Box, Button, LinearProgress, Dialog, DialogActions, DialogContent, DialogTitle, Drawer, IconButton, TextField, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../lib/api'
import { EvidenceValueEditor, type ProposalField } from './EvidenceProposalEditor'
import { evidenceProblem } from './EvidenceFieldMarkers'
import { createEvidenceDraftQueue } from '../lib/evidenceDraftQueue'
import { evidenceFieldAffected } from '../lib/evidenceFields'
import { useLanguage } from '../context/LanguageContext'

export interface EvidenceSource { block_id?: string; file_id: string; source_name?: string; chunk_id?: number; chunk_index: number; page_start?: number; page_end?: number; content?: string; quote?: string }
export interface ProposalDraft { values: Record<string, unknown>; accepted: boolean; reason: string; supported?: boolean }
export type EvidenceBasis = 'paper_quote' | 'paper_inference' | 'general_knowledge'
export interface EvidenceHistory {
  current_value?: unknown
  reason?: string
  adopted_basis?: EvidenceBasis
  evidences?: EvidenceSource[]
  proposal?: EvidenceRecord['proposal']
  decision?: EvidenceRecord['decision']
}
export interface EvidenceRecord { history?: EvidenceHistory[]; placeholder?: boolean; required?: boolean; adopted_basis?: EvidenceBasis; proposal_review?: {status: string; explanation: string}; human_confirmed?: boolean; source_kind?: string; proposal?: { basis_kind?: EvidenceBasis; explanation?: string; values: Record<string, unknown>; supported: boolean; evidences: EvidenceSource[] }; proposal_draft?: ProposalDraft; decision?: { actor_user_id: number; reason: string; supported?: boolean; accepted?: boolean; basis_kind?: EvidenceBasis }; editable_fields?: ProposalField[]; key: string; item_key?: string; field: string; fields?: string[]; label: string; current_value?: unknown; status: 'unchecked' | 'supported' | 'unsupported' | 'uncertain' | 'missing'; reason: string; suggestion?: string; evidences: EvidenceSource[]; stale?: boolean; resolution?: string; structure_hash?: string; state_key?: string; module_key?: string; record_key?: string; provenance?: { kind: string; submitted_by_name?: string; filename?: string; original_text?: string; method?: string; verified?: boolean; paper_supported?: boolean } }
interface Preflight { job_id?: string; version: string; needs_check: boolean; records: EvidenceRecord[] }
interface Job { timeout_seconds?: number; id: string; status: string; version?: string; progress?: string; completed_batches?: number; total_batches?: number; current_batch?: number; records?: EvidenceRecord[]; error?: { code: string; message: string } }
export interface EvidencePayload { evidence_job_id?: string; expected_evidence_version: string; evidence_resolutions: Record<string, string> }
export interface EvidenceTarget { target: 'upload' | 'paper' | 'revision'; target_id: string }
interface View { phase: 'checking' | 'countdown' | 'running' | 'error'; seconds?: number; message?: string; job?: Job }
const base = '/api/rag/evidence'
const problematic = evidenceProblem

// 运行任务与持久问题列表分开；关闭抽屉不清除任何核对结果。
export function useEvidenceWorkflow(options?: {
  target?: EvidenceTarget
  getCurrentValue?: (record: EvidenceRecord) => { value: unknown; field: string } | undefined
  saveCurrent?: () => Promise<boolean>
}) {
  const { t } = useLanguage()
  const [view, setView] = useState<View | null>(null)
  const [records, setRecords] = useState<EvidenceRecord[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [fallbackRecord, setFallbackRecord] = useState<EvidenceRecord | undefined>()
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const confirmingRef = useRef(false)
  const editRevision = useRef(0)
  const dirty = useRef(false)
  const localReasons = useRef(new Map<string, string>())
  const optionsRef = useRef(options)
  optionsRef.current = options
  const recordsRef = useRef(records)
  recordsRef.current = records
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const generation = useRef(0)
  const cancelLateJob = useRef(true)
  const jobID = useRef<string | undefined>(undefined)
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
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [draftValues, setDraftValues] = useState<Record<string, Record<string, unknown>>>({})
  const valuesRef = useRef(draftValues)
  valuesRef.current = draftValues
  const drawerSession = useRef(0)
  const drawerReturn = useRef<{ trigger: HTMLElement; field: HTMLElement | null; anchor: HTMLElement; top: number; scroller: Element | null } | null>(null)
  const preserveDrawerPosition = () => {
    const origin = drawerReturn.current
    if (origin?.anchor.isConnected && origin.scroller) origin.scroller.scrollTop += origin.anchor.getBoundingClientRect().top - origin.top
  }
  // 核对记录变化时在绘制前保持阅读位置，避免关闭动画期间先下移再跳回。
  useLayoutEffect(() => { preserveDrawerPosition() }, [records])
  const openIssue = (key: string, keys?: string[], fallback?: EvidenceRecord) => {
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
  }
  const closeDrawer = useCallback(() => {
    drawerSession.current += 1
    void flushDrafts().catch(() => undefined)
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
    const current = ++generation.current
    const revision = editRevision.current
    const identity = `${target.target}:${target.target_id}`
    if (targetIdentity.current !== identity) { localReasons.current.clear(); dirty.current = false }
    const previousTarget = targetRef.current
    targetRef.current = target
    targetIdentity.current = identity
    if (previousTarget) await queueFor(previousTarget).flush().catch(() => undefined)
    if (!mounted.current || generation.current !== current || editRevision.current !== revision) return
    try {
      const result = await api.post<Preflight>(`${base}/preflight`, target)
      if (generation.current !== current || editRevision.current !== revision) return
      preflightRef.current = result
      recordsRef.current = result.records || []
      setRecords(result.records || [])
      if (!queueFor(target).hasPending()) {
        setDraftValues({})
        setReasons(Object.fromEntries((result.records || []).map(r => [r.key, localReasons.current.get(r.item_key || r.key) ?? (r.stale ? '' : r.proposal_draft?.reason ?? r.resolution ?? '')])))
      }
      return result
    } catch (error) { if (generation.current === current) setSaveError((error as Error).message); return undefined }
  }, [])
  // 普通保存与侧栏确认共用；刷新不能覆盖请求之后发生的编辑。
  const refreshAfterSave = async (revision: number) => {
    if (revision !== editRevision.current || !targetRef.current) return false
    const result = await restore(targetRef.current)
    if (!result || revision !== editRevision.current) return false
    dirty.current = false
    return true
  }
  useEffect(() => {
    if (options?.target) void restore(options.target)
  }, [options?.target?.target, options?.target?.target_id, restore])

  const payload = (preflight: Preflight, resolutions: Record<string, string> = {}): EvidencePayload => ({ evidence_job_id: jobID.current, expected_evidence_version: preflight.version, evidence_resolutions: resolutions })
  const showResults = (next: EvidenceRecord[], preflight: Preflight) => {
    setRecords(next)
    setDraftValues({})
    setReasons(Object.fromEntries(next.map(r => [r.key, r.proposal_draft?.reason ?? r.resolution ?? ''])))
    pending.current?.(payload(preflight))
    pending.current = undefined
    setView(null)
    const disputed = next.filter(problematic)
    if (disputed.length) openIssue(disputed[0].key)
  }
  // 提交门禁只读恢复；任何未核对项目都不在此处启动模型。
  const gate = async (target: EvidenceTarget): Promise<EvidencePayload | null> => {
    await flushDrafts()
    const result = await api.post<Preflight>(`${base}/preflight`, target)
    preflightRef.current = result
    targetRef.current = target
    setRecords(result.records)
    setReasons(Object.fromEntries(result.records.map(r => [r.key, r.proposal_draft?.reason ?? r.resolution ?? ''])))
    const unresolved = result.records.filter(r => r.required !== false && !(target.target === 'upload' && r.decision?.accepted && ['paper_inference', 'general_knowledge'].includes(r.adopted_basis || '')) && (r.stale || (!r.human_confirmed && (r.status === 'unchecked' || r.status === 'missing'))
      || (target.target === 'paper' && r.status !== 'supported' && !r.human_confirmed && !r.resolution?.trim())))
    if (result.needs_check || unresolved.length) {
      if (unresolved.length) openIssue(unresolved[0].key)
      setSaveError(t('evidence.checkRequired'))
      return null
    }
    return payload(result, Object.fromEntries(result.records.map(r => [r.key, r.proposal_draft?.reason ?? r.resolution ?? ''])))
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

  const execute = async (target: EvidenceTarget, retryKeys?: string[]) => {
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
    setSelected(null)
    try {
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
      const preflight = await api.post<Preflight>(`${base}/preflight`, target)
      if (!active()) return
      preflightRef.current = preflight
      if (retryItems) {
        retryKeys = preflight.records.filter(r => retryItems.has(r.item_key || r.key)).map(r => r.key)
        if (!retryKeys.length) { showResults(preflight.records, preflight); return }
      }
      if (target.target !== 'paper' && !retryKeys && !preflight.needs_check && !preflight.records.some(r => r.status === 'unchecked')) { jobID.current = preflight.job_id; completed.current = true; showResults(preflight.records, preflight); return }
      for (let seconds = 3; seconds > 0; seconds--) {
        setView({ phase: 'countdown', seconds, message: t('evidence.startHint') })
        await pause(1000)
        if (!active()) return
      }
      setView({ phase: 'running', message: t('evidence.starting') })
      const job = await api.post<Job>(`${base}/jobs`, { ...target, expected_version: preflight.version, purpose: target.target === 'paper' && !retryKeys ? 'review_all' : 'check', ...(retryKeys ? { retry_keys: retryKeys } : {}) })
      if (!active()) { if (cancelLateJob.current) void api.del(`${base}/jobs/${job.id}`).catch(() => undefined); return }
      jobID.current = job.id
      const deadline = Date.now() + ((job.timeout_seconds || 600) + 60) * 1000
      while (active()) {
        const result = await api.get<Job>(`${base}/jobs/${job.id}`)
        if (!active()) return
        if (result.status === 'completed') {
          completed.current = true
          if (result.version) preflight.version = result.version
          showResults(result.records || [], preflight)
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
        setView({ phase: 'error', message: (error as Error).message })
      }
    }
  }
  const run = (target: EvidenceTarget): Promise<EvidencePayload | null> => {
    if (pending.current) { setSelected(records.find(problematic)?.key || null); return Promise.resolve(null) }
    targetRef.current = target
    return new Promise(resolve => { pending.current = resolve; void execute(target) })
  }
  const valuesFor = (record: EvidenceRecord) => record.stale ? {} : valuesRef.current[record.key] || record.proposal_draft?.values || record.proposal?.values || {}
  const saveProposal = (record: EvidenceRecord, values: Record<string, unknown>, accepted: boolean, reason: string, immediate = false) => {
    if (!targetRef.current || !preflightRef.current) return Promise.resolve()
    const target = targetRef.current
    const identity = `${target.target}:${target.target_id}`
    targetIdentity.current = identity
    const request = { ...target, expected_version: preflightRef.current.version, key: record.key, values, accepted, reason }
    const revision = editRevision.current
    const queue = queueFor(target)
    queue.enqueue(record.key, async () => {
      const result = await api.post<{ draft: ProposalDraft }>(`${base}/proposals`, request)
      if (mounted.current && editRevision.current === revision && targetIdentity.current === identity && preflightRef.current?.version === request.expected_version) setRecords(old => old.map(r => r.key === record.key ? { ...r, stale: false, proposal_draft: result.draft } : r))
    })
    return immediate ? queue.flush() : Promise.resolve()
  }
  const updateValues = (record: EvidenceRecord, path: string, value: unknown) => {
    const next = { ...valuesFor(record), [path]: value }
    valuesRef.current = { ...valuesRef.current, [record.key]: next }
    setDraftValues(valuesRef.current)
    void saveProposal(record, next, false, reasons[record.key] ?? record.proposal_draft?.reason ?? '')
  }
  const updateReason = (record: EvidenceRecord, reason: string) => {
    localReasons.current.set(record.item_key || record.key, reason)
    setReasons(old => ({ ...old, [record.key]: reason }))
    if (!dirty.current && !record.stale) void saveProposal(record, valuesFor(record), false, reason)
  }
  const accept = async (group: EvidenceRecord[]) => {
    if (confirmingRef.current) return
    confirmingRef.current = true
    setConfirming(true)
    const revision = editRevision.current
    const session = drawerSession.current
    const target = targetRef.current
    const identity = targetIdentity.current
    const saveCurrent = optionsRef.current?.saveCurrent
    const active = () => mounted.current && identity === targetIdentity.current && (!optionsRef.current?.target || `${optionsRef.current.target.target}:${optionsRef.current.target.target_id}` === identity)
    const choices = new Map(group.map(r => [r.item_key || r.key, {values: valuesFor(r), reason: localReasons.current.get(r.item_key || r.key) ?? (r.stale ? '' : reasons[r.key] ?? r.proposal_draft?.reason ?? '')}]))
    try {
      setSaveError('')
      if (saveCurrent && target) for (const record of group) queueFor(target).discard(record.key)
      await retryDrafts()
      if (!active()) return
      if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
      if (saveCurrent && !(await saveCurrent())) throw new Error(t('evidence.saveFirstFailed'))
      if (!active()) return
      if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
      const fresh = saveCurrent || group.some(r => r.stale)
        ? target ? await restore(target) : undefined
        : preflightRef.current && {...preflightRef.current, records: recordsRef.current}
      if (!fresh) throw new Error(t('evidence.saveFirstFailed'))
      if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
      dirty.current = false
      const currentGroup = group.flatMap(old => {
        const current = fresh.records.find(r => (r.item_key || r.key) === (old.item_key || old.key))
        return current ? [{old, current}] : []
      })
      for (const {old, current} of currentGroup) {
        if (!active()) return
        if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
        const choice = choices.get(old.item_key || old.key)!
        // 手改后的值已保存，不再应用旧版本的候选。
        const values = old.stale || current.stale ? {} : choice.values
        await saveProposal(current, values, true, choice.reason, true)
      }
      if (!active()) return
      if (revision !== editRevision.current) throw new Error(t('evidence.changedDuringSave'))
      if (drawerSession.current === session) closeDrawer()
    } catch (error) { if (active() && drawerSession.current === session) setSaveError((error as Error).message) }
    finally { confirmingRef.current = false; if (mounted.current) setConfirming(false) }
  }
  const invalidate = useCallback((field: string, pathKind: 'current' | 'snapshot' = 'current') => {
    editRevision.current += 1
    dirty.current = true
    const matches = (record: EvidenceRecord) => {
      const current = pathKind === 'current' ? optionsRef.current?.getCurrentValue?.(record) : undefined
      return evidenceFieldAffected(current ? {...record, field:current.field} : record, field)
    }
    const affected = recordsRef.current.filter(matches)
    for (const r of affected) {
      if (!r.stale) localReasons.current.delete(r.item_key || r.key)
      if (targetRef.current) queueFor(targetRef.current).discard(r.key)
      delete valuesRef.current[r.key]
    }
    setReasons(old => Object.fromEntries(Object.entries(old).filter(([key]) => !affected.some(r => r.key === key && !localReasons.current.has(r.item_key || r.key)))))
    const next = recordsRef.current.map(r => matches(r)
      ? { ...r, stale: true, resolution: '', proposal_draft: undefined, proposal: undefined, human_confirmed: false, decision: undefined } : r)
    recordsRef.current = next
    setRecords(next)
  }, [])
  const issues = useMemo(() => records.filter(problematic), [records])
  const activeRecord = records.find(r => r.key === selected) || (fallbackRecord?.key === selected ? fallbackRecord : undefined)
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
  const activeGroup = activeRecord?.placeholder ? [activeRecord] : records.filter(r => selectedKeys.includes(r.key) || r.key === selected)
  const accepted = activeGroup.length > 0 && activeGroup.every(r => r.proposal_draft?.accepted)
  const draftSaveFailed = Boolean(targetRef.current && queueFor(targetRef.current).error())
  const editCurrent = (record: EvidenceRecord) => {
    const field = optionsRef.current?.getCurrentValue?.(record)?.field || record.field
    closeDrawer()
    setTimeout(() => {
      const node = Array.from(document.querySelectorAll<HTMLElement>('[data-issue-field]')).find(n => n.dataset.issueField === field)
      for (let parent = node?.parentElement; parent; parent = parent.parentElement) if (parent instanceof HTMLDetailsElement) parent.open = true
      const input = node?.matches('input,textarea,select') ? node : node?.querySelector<HTMLElement>('input,textarea,select,[role="combobox"]')
      input?.scrollIntoView?.({block: 'center'}); input?.focus()
    }, 320)
  }
  const dialog = <>

    <Dialog open={view !== null} onClose={() => finish(null)} fullWidth maxWidth="md" aria-labelledby="evidence-workflow-title">
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
        {view?.phase === 'error' && <Button onClick={() => void execute(targetRef.current!, issues.map(r => r.key))}>{t('evidence.retry')}</Button>}
      </DialogActions>
    </Dialog>
    <Drawer anchor="right" variant="temporary" open={Boolean(activeRecord)} onClose={closeDrawer} ModalProps={{ disableRestoreFocus: true }} slotProps={{ transition: { onExited: restoreDrawerFocus }, paper: { role: 'dialog', className: 'evidence-review-drawer', 'aria-label': t('evidence.title'), sx: { width: { xs: '100vw', sm: 480 }, maxWidth: '100vw', p: 3 } } }}>
      {activeRecord && <>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><Typography variant="h6">{activeRecord.label}</Typography><IconButton aria-label={t('evidence.closeDrawer')} onClick={closeDrawer}><CloseIcon /></IconButton></Box>
        <Typography fontWeight={600} sx={{ mt: 2 }}>{t(options?.getCurrentValue ? 'evidence.currentValue' : 'evidence.currentContent')}</Typography>
        {[...new Map(activeGroup.map(r => [r.field, r])).values()].map(r => {
          const value = options?.getCurrentValue?.(r)?.value ?? (options?.getCurrentValue?.(r) ? null : r.current_value)
          return <Typography key={r.key} sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', my: 1 }}>{value == null || value === '' ? t('evidence.emptyValue') : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}</Typography>
        })}
        {options?.getCurrentValue && !activeRecord.placeholder && <Button onClick={() => editCurrent(activeRecord)}>{t('evidence.editCurrent')}</Button>}
        {dirty.current && options?.saveCurrent && <Alert severity="info">{t('evidence.saveBeforeConfirm')}</Alert>}
        {activeGroup.every(r => !r.evidences.length && !r.proposal && !r.decision && !r.proposal_draft && (r.placeholder || r.status === 'unchecked')) && <Alert severity="info" sx={{ mt: 2 }}>{t('evidence.emptySources')}</Alert>}
        {!activeRecord.placeholder && <><Typography fontWeight={600} sx={{ mt: 2 }}>{t('evidence.problemsDirections')}</Typography>
        {activeGroup.map(r => <Box key={r.key} sx={{ my: 1 }}>
          {r.stale && <Alert severity="warning">{t('evidence.staleResult')}</Alert>}
          <Alert severity={r.human_confirmed ? 'success' : r.status === 'unchecked' ? 'info' : r.status === 'supported' ? 'success' : 'error'}>{r.human_confirmed ? t('evidence.humanConfirmed') : r.status === 'unchecked' ? t('evidence.uncheckedHint') : r.reason}</Alert>
          <Typography sx={{ my: 1 }}>{r.suggestion || t('evidence.defaultSuggestion')}</Typography>
        </Box>)}
        <Typography fontWeight={600} sx={{ my: 2 }}>{t('evidence.suggestionLabel')}</Typography>
        {activeGroup.map(r => <Box key={r.key} sx={{ display: 'grid', gap: 1.5, mb: 2 }}>
          {(r.adopted_basis || r.proposal?.basis_kind) && <Alert severity="info">{t(`evidence.basis.${r.adopted_basis || r.proposal?.basis_kind}`)}</Alert>}
          {r.proposal?.explanation && <Typography sx={{ whiteSpace: 'pre-wrap' }}>{r.proposal.explanation}</Typography>}
          {r.proposal_review && <Typography>{t('evidence.proposalReview')}：{r.proposal_review.explanation}</Typography>}
          {r.decision?.reason && <Typography>{t('evidence.savedHumanReason')}：{r.decision.reason}</Typography>}
          {!r.proposal && <Alert severity="info">{t('evidence.noReplacement')}</Alert>}
          {(r.editable_fields || []).map(field => <EvidenceValueEditor key={field.path} label={r.stale ? `${field.label} · ${t('evidence.beforeEditValue')}` : field.label} schema={field.schema}
            value={Object.hasOwn(valuesFor(r), field.path) ? valuesFor(r)[field.path] : field.value} disabled={r.stale || Boolean(r.proposal_draft?.accepted)}
            onChange={value => updateValues(r, field.path, value)} />)}
          {targetRef.current?.target === 'paper' && <TextField multiline minRows={2} label={t('evidence.humanReason')} value={reasons[r.key] ?? r.proposal_draft?.reason ?? ''}
            disabled={confirming || (!r.stale && Boolean(r.proposal_draft?.accepted))} onChange={event => updateReason(r, event.target.value)} helperText={t('evidence.reasonConditional')} />}
        </Box>)}
        {accepted && <Alert severity="success">{t('evidence.acceptedPending')}</Alert>}</>}

        {activeGroup.some(r => r.history?.length) && <Box component="details" sx={{ my: 2 }}><Typography component="summary">{t('evidence.historyLabel')}</Typography>{activeGroup.flatMap(r => r.history || []).map((entry, index) => <Box key={index} sx={{ my: 2, overflowWrap: 'anywhere' }}>
          <Alert severity="info">{t('evidence.historyReadonly')}</Alert>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{typeof entry.current_value === 'object' ? JSON.stringify(entry.current_value, null, 2) : String(entry.current_value ?? '')}</Typography>
          <Typography>{entry.reason}</Typography>
          {(entry.adopted_basis || entry.proposal?.basis_kind) && <Typography>{t(`evidence.basis.${entry.adopted_basis || entry.proposal?.basis_kind}`)}</Typography>}
          {entry.proposal && <><Typography>{JSON.stringify(entry.proposal.values)}</Typography><Typography>{entry.proposal.explanation}</Typography></>}
          {entry.decision?.reason && <Typography>{t('evidence.savedHumanReason')}：{entry.decision.reason}</Typography>}
          {[...(entry.evidences || []), ...(entry.proposal?.evidences || [])].map((source, i) => <Typography key={i}>{source.source_name || source.file_id} · {source.page_start} — {source.quote}</Typography>)}
        </Box>)}</Box>}
        {activeRecord.provenance?.kind === 'contributor_structure' && <Alert severity="info" sx={{ mb: 2 }}>
          {activeRecord.evidences.length === 0 && <Typography>{t('evidence.noPaperSupport')}</Typography>}
          <Typography>{t('evidence.providerLabel')}：{activeRecord.provenance.submitted_by_name || t('evidence.unknownProvider')}</Typography>
          <Typography>{activeRecord.provenance.filename} · {activeRecord.provenance.method}</Typography>
          {activeRecord.provenance.original_text && <Box component="details"><Box component="summary">原始结构文件</Box><Typography component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{activeRecord.provenance.original_text}</Typography></Box>}
        </Alert>}
        {activeGroup.some(r => r.evidences.length > 0 || r.proposal?.evidences.length) && <Box component="details" sx={{ my: 2 }}><Box component="summary" sx={{ cursor: 'pointer' }}>{t('evidence.foundSources')}</Box>
          {activeGroup.flatMap(r => [...r.evidences, ...(r.proposal?.evidences || [])]).filter((e, i, all) => all.findIndex(x => x.file_id === e.file_id && x.quote === e.quote) === i).map((e, i) => <EvidenceRegion key={`${e.file_id}:${e.page_start}:${i}`} target={targetRef.current} source={e} />)}
        </Box>}
        {saveError && <Alert severity="error" sx={{ mt: 1 }} action={draftSaveFailed ? <Button disabled={saving} onClick={() => void retryDrafts().catch(() => undefined)}>{t('evidence.retrySave')}</Button> : undefined}>{saveError} {draftSaveFailed && t('evidence.saveFailureRetained')}</Alert>}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', my: 2 }}>
          <Button onClick={closeDrawer}>{t('evidence.back')}</Button>
          {!activeRecord.placeholder && <><Button disabled={confirming || (activeRecord.stale && dirty.current && !options?.saveCurrent)} onClick={() => { setDraftValues({}); void execute(targetRef.current!, activeGroup.map(r => r.key)) }}>{t('evidence.retry')}</Button>
          <Button variant="contained" disabled={saving || confirming || activeGroup.some(r => targetRef.current?.target === 'paper'
            ? ((dirty.current && !options?.saveCurrent) || ((r.stale || (r.status !== 'supported' && !r.proposal?.supported)) && !(reasons[r.key] ?? r.proposal_draft?.reason ?? '').trim()))
            : (r.stale || ((!r.proposal || r.proposal.basis_kind === 'paper_quote' || !r.proposal.basis_kind) && (r.status === 'unchecked' || (!r.evidences.length && !r.proposal?.evidences.length && !r.provenance?.verified))))) || accepted} onClick={() => void accept(activeGroup)}>{t('evidence.complete')}</Button>
          {accepted && <Button disabled={saving} onClick={() => { for (const r of activeGroup) void saveProposal(r, valuesFor(r), false, reasons[r.key] || r.proposal_draft?.reason || '', true).catch(() => undefined) }}>{t('evidence.revise')}</Button>}</>}
        </Box>
        {issues.length > 1 && <Box>{issues.map(r => <Button key={r.key} color="error" onClick={() => openIssue(r.key)}>{r.label}</Button>)}</Box>}
      </>}
    </Drawer>
  </>
  return { refreshAfterSave, getEditRevision: () => editRevision.current, hasUnsavedChanges: () => dirty.current, hasAccepted: records.some(r => !r.stale && r.proposal_draft?.accepted), run, gate, applyAccepted, dialog, busy: view !== null, issues, records, restore, invalidate, openIssue, clearIssues: () => finish(null), saveError }
}
