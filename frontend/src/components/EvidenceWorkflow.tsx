import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, LinearProgress, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'

export interface EvidenceSource { file_id: string; chunk_id?: number; chunk_index: number; page_start?: number; page_end?: number; content?: string; quote?: string }
export interface EvidenceRecord { key: string; field: string; label: string; status: 'unchecked' | 'supported' | 'unsupported' | 'uncertain' | 'missing'; reason: string; evidences: EvidenceSource[] }
interface Preflight { job_id?: string; version: string; needs_check: boolean; records: EvidenceRecord[] }
interface Job { id: string; status: string; progress?: string; completed_batches?: number; total_batches?: number; current_batch?: number; records?: EvidenceRecord[]; error?: { code: string; message: string } }
export interface EvidencePayload { evidence_job_id?: string; expected_evidence_version: string; evidence_resolutions: Record<string, string> }
export interface EvidenceTarget { target: 'upload' | 'paper'; target_id: string }
interface View { phase: 'checking' | 'countdown' | 'running' | 'issues' | 'error'; seconds?: number; message?: string; records?: EvidenceRecord[]; job?: Job }
const base = '/api/rag/evidence'

// 一次 run 对应一次用户动作；取消、卸载和迟到响应由 generation 隔离。
export function useEvidenceWorkflow() {
  const { t } = useLanguage()
  const [view, setView] = useState<View | null>(null)
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const completedJob = useRef(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const waiting = view?.phase === 'checking' || view?.phase === 'running'
  useEffect(() => {
    setElapsedSeconds(0)
    if (!waiting) return
    const started = Date.now()
    const interval = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [waiting])
  const generation = useRef(0)
  const jobID = useRef<string | undefined>(undefined)
  const pending = useRef<((value: EvidencePayload | null) => void) | undefined>(undefined)
  const targetRef = useRef<EvidenceTarget | undefined>(undefined)
  const preflightRef = useRef<Preflight | undefined>(undefined)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const timerDone = useRef<(() => void) | undefined>(undefined)
  const pause = (ms: number) => new Promise<void>(resolve => { timerDone.current = resolve; timer.current = setTimeout(resolve, ms) })

  const finish = useCallback((value: EvidencePayload | null) => {
    generation.current += 1
    clearTimeout(timer.current)
    timerDone.current?.()
    timerDone.current = undefined
    const id = jobID.current
    jobID.current = undefined
    if (value === null && id && !completedJob.current) void api.del(`${base}/jobs/${id}`).catch(() => undefined)
    pending.current?.(value)
    pending.current = undefined
    setView(null)
  }, [])

  useEffect(() => () => { finish(null) }, [finish])

  const showResults = (records: EvidenceRecord[], preflight: Preflight) => {
    const missing = records.some(r => r.status === 'missing')
    const disputed = records.some(r => r.status !== 'supported')
    if (!missing && (!disputed || targetRef.current?.target === 'upload')) {
      finish({ evidence_job_id: jobID.current, expected_evidence_version: preflight.version, evidence_resolutions: {} })
    } else {
      setView({ phase: 'issues', records })
    }
  }

  const execute = async (target: EvidenceTarget, retry = false) => {
    const current = ++generation.current
    jobID.current = undefined
    const active = () => generation.current === current
    try {
      setView({ phase: 'checking', message: t('evidence.checking') })
      const preflight = await api.post<Preflight>(`${base}/preflight`, target)
      if (!active()) return
      preflightRef.current = preflight
      if (!retry && !preflight.needs_check) { jobID.current = preflight.job_id; showResults(preflight.records, preflight); return }
      for (let seconds = 3; seconds > 0; seconds--) {
        setView({ phase: 'countdown', seconds, message: t('evidence.startHint') })
        await pause(1000)
        if (!active()) return
      }
      setView({ phase: 'running', message: t('evidence.starting') })
      const job = await api.post<Job>(`${base}/jobs`, { ...target, expected_version: preflight.version })
      if (!active()) { void api.del(`${base}/jobs/${job.id}`).catch(() => undefined); return }
      jobID.current = job.id
      const deadline = Date.now() + 660_000
      while (active()) {
        const result = await api.get<Job>(`${base}/jobs/${job.id}`)
        if (!active()) return
        if (result.status === 'completed') {
          completedJob.current = true
          if (target.target === 'upload') await api.post(`${base}/jobs/${job.id}/save-draft`)
          showResults(result.records || [], preflight); return
        }
        if (result.status === 'failed') throw new Error(result.error?.message || t('evidence.failed'))
        if (result.status === 'cancelled') { finish(null); return }
        if (Date.now() > deadline) throw new Error(t('evidence.timeout'))
        setView({ phase: 'running', job: result, message: result.status === 'queued' ? t('evidence.queued') : result.progress || t('evidence.running') })
        await pause(1000)
      }
    } catch (error) {
      if (active()) {
        if (jobID.current) void api.del(`${base}/jobs/${jobID.current}`).catch(() => undefined)
        setView({ phase: 'error', message: (error as Error).message })
      }
    }
  }

  const run = (target: EvidenceTarget): Promise<EvidencePayload | null> => {
    if (pending.current) return Promise.resolve(null)
    targetRef.current = target
    completedJob.current = false
    setReasons({})
    return new Promise(resolve => { pending.current = resolve; void execute(target) })
  }

  const disputed = view?.records?.filter(r => r.status !== 'supported') || []
  const total = view?.job?.total_batches || 0
  const completed = Math.min(total, Math.max(0, view?.job?.completed_batches || 0))
  const percent = total > 0 ? Math.floor(completed / total * 100) : undefined
  const currentBatch = view?.job?.current_batch || 0
  const progressMessage = total > 0 && currentBatch > completed
    ? t('evidence.currentBatch', { current: currentBatch, total }) : view?.message
  const canResolve = targetRef.current?.target === 'paper' && disputed.length > 0 && disputed.every(r => r.status !== 'missing' && reasons[r.key]?.trim())
  const dialog = <Dialog open={view !== null} onClose={() => finish(null)} fullWidth maxWidth="md" aria-labelledby="evidence-workflow-title">
    <DialogTitle id="evidence-workflow-title">{t('evidence.title')}</DialogTitle>
    <DialogContent>
      {view?.phase === 'countdown' && <Alert severity="info">{t('evidence.countdown', { seconds: view.seconds || 0 })}{view.message}</Alert>}
      {waiting && <Box sx={{ py: 1 }}>
        <Typography role="status" sx={{ mb: 2 }}>{progressMessage}</Typography>
        <LinearProgress aria-label={t('evidence.progressLabel')} variant={percent === undefined ? 'indeterminate' : 'determinate'} value={percent} sx={{ height: 8, borderRadius: 4 }} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mt: 1 }}>
          <Typography variant="body2" color="text.secondary">{percent === undefined ? t('evidence.waitingHint') : t('evidence.batchProgress', { completed, total, percent })}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>{t('evidence.elapsed', { minutes: Math.floor(elapsedSeconds / 60), seconds: elapsedSeconds % 60 })}</Typography>
        </Box>
      </Box>}
      {view?.phase === 'error' && <Alert severity="error">{view.message}</Alert>}
      {view?.phase === 'issues' && <>
        <Alert severity="warning" sx={{ mb: 2 }}>{t('evidence.issues')}</Alert>
        {disputed.map(record => <Box key={record.key} sx={{ mb: 3, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Typography fontWeight={700}>{record.label}</Typography>
          <Typography color="error" sx={{ my: 1 }}>{record.reason}</Typography>
          {record.evidences.length > 0 && <Box component="details" sx={{ my: 2 }}>
            <Box component="summary" sx={{ cursor: 'pointer', color: 'primary.main' }}>{t('evidence.foundSources')}</Box>
            {record.evidences.map((e, i) => <Box key={i} component="blockquote" sx={{ ml: 0, pl: 2, borderLeft: 3, borderColor: 'divider', whiteSpace: 'pre-wrap' }}>
              <Typography variant="caption">{e.page_start ? (e.page_end && e.page_end !== e.page_start ? t('evidence.pages', { start: e.page_start, end: e.page_end }) : t('evidence.page', { page: e.page_start })) : t('evidence.pageUnknown')}</Typography>
              <Typography>{e.quote}</Typography>
            </Box>)}
          </Box>}
          {record.status !== 'missing' && targetRef.current?.target === 'paper' && <TextField fullWidth multiline label={t('evidence.reason')} value={reasons[record.key] || ''} inputProps={{ maxLength: 4000 }} onChange={e => setReasons(old => ({ ...old, [record.key]: e.target.value }))} helperText={t('evidence.reasonHint')} sx={{ mb: 2 }} />}
        </Box>)}
      </>}
    </DialogContent>
    <DialogActions>
      <Button onClick={() => finish(null)}>{view?.phase === 'issues' ? t('evidence.back') : t('common.cancel')}</Button>
      {(view?.phase === 'issues' || view?.phase === 'error') && <Button onClick={() => { setReasons({}); void execute(targetRef.current!, true) }}>{t('evidence.retry')}</Button>}
      {canResolve && <Button variant="contained" onClick={() => finish({ evidence_job_id: jobID.current, expected_evidence_version: preflightRef.current!.version, evidence_resolutions: reasons })}>{t('evidence.approve')}</Button>}
    </DialogActions>
  </Dialog>
  return { run, dialog, busy: view !== null }
}
