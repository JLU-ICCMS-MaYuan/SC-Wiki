import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { unwrapData, type UploadTaskState } from '../lib/paperProcessing'

interface Question {
  question_id: string; prompt_revision: number; target_token: string; title: string
  checked_context: string; state: string
  target_refs: Array<{ item_key?: string; field?: string; state_key?: string }>
  source_refs: Array<{ file_id: string; source_name?: string; pdf_page?: number; page_start?: number; quote?: string; content?: string }>
  options: Array<{ choice_id: string; label: string; description: string }>
  last_answer?: { direction?: string; reason?: string }
  answer_draft?: { manual_text?: string; reason?: string }
}
interface Queue { queue_revision: number; pending_count: number; can_answer_existing: boolean; questions: Question[] }
interface Draft { manual_text: string; reason: string; answer_id?: string; signature?: string }

const QuestionCard = React.memo(function QuestionCard({ question: q, queueRevision, taskId, storageKey, writable, refresh }: {
  question: Question; queueRevision: number; taskId: string; storageKey: string; writable: boolean; refresh: () => void
}) {
  const { t } = useLanguage()
  const [draft, setDraft] = useState<Draft>(() => {
    try { return JSON.parse(sessionStorage.getItem(storageKey) || 'null') ||
      { manual_text: q.answer_draft?.manual_text || '', reason: q.answer_draft?.reason || '' } }
    catch { return { manual_text: '', reason: '' } }
  })
  const [manual, setManual] = useState(false)
  const [pending, setPending] = useState(false)
  const pendingRef = useRef(false)
  const mounted = useRef(true)
  const [error, setError] = useState('')
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const update = (next: Draft) => {
    setDraft(next)
    try { sessionStorage.setItem(storageKey, JSON.stringify(next)) } catch { /* 当前输入仍保留在内存。 */ }
  }
  const answer = async (choice: string) => {
    if (pendingRef.current) return
    pendingRef.current = true; setPending(true); setError('')
    const signature = JSON.stringify([choice, draft.manual_text, draft.reason, q.target_token, q.prompt_revision])
    const answerId = signature === draft.signature && draft.answer_id ? draft.answer_id : crypto.randomUUID()
    update({ ...draft, signature, answer_id: answerId })
    try {
      const response = await api.post<{ ok: boolean; data: { accepted: boolean; resume_error?: unknown } }>(
        `/api/upload-tasks/${encodeURIComponent(taskId)}/human-questions/${q.question_id}/answers`, {
          answer_id: answerId, expected_queue_revision: queueRevision, prompt_revision: q.prompt_revision,
          target_token: q.target_token, choice_id: choice,
          ...(choice === 'manual' ? { manual_text: draft.manual_text, reason: draft.reason } : {}),
        })
      const result = unwrapData(response)
      if (!mounted.current) return
      if (!result.accepted) setError(t('upload.humanQuestionStale'))
      else {
        try { sessionStorage.removeItem(storageKey) } catch { /* 不影响已持久接受的答案。 */ }
        if (result.resume_error) setError(t('upload.humanQuestionResumeError'))
      }
      refresh()
    } catch (reason: any) {
      if (mounted.current) {
        setError(reason.message || t('upload.operationFailed'))
        if (reason.status === 409) refresh()
      }
    } finally {
      pendingRef.current = false
      if (mounted.current) setPending(false)
    }
  }
  const canAnswer = writable && ['waiting', 'investigating'].includes(q.state)
  return <Box data-testid={`human-question-${q.question_id}`} sx={{ p: 2, mt: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
    <Typography fontWeight={600}>{q.title}</Typography>
    <Chip size="small" label={t(`upload.humanQuestionState.${q.state}`)} sx={{ my: 1 }} />
    {q.target_refs.map((target, i) => <Typography key={target.item_key || i} variant="caption" display="block">
      {[target.state_key, target.field].filter(Boolean).join(' · ')}</Typography>)}
    <Typography variant="body2" sx={{ my: 1 }}>{q.checked_context}</Typography>
    {q.source_refs.map((source, i) => <Box component="blockquote" key={`${source.file_id}-${i}`} sx={{ m: 1, borderLeft: 2, pl: 1 }}>
      <Typography variant="caption">{source.source_name || source.file_id}
        {(source.pdf_page || source.page_start) ? ` · p.${source.pdf_page || source.page_start}` : ''}</Typography>
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 160, overflow: 'auto' }}>{source.quote || source.content}</Typography>
    </Box>)}
    {q.last_answer && <Alert severity="info">{t('upload.humanQuestionAccepted')} {q.last_answer.direction}</Alert>}
    {!canAnswer && draft.manual_text && <TextField fullWidth multiline sx={{ mt: 1 }}
      label={t('upload.humanQuestionRetained')} value={[draft.manual_text, draft.reason].filter(Boolean).join('\n')}
      InputProps={{ readOnly: true }} />}
    {canAnswer && <>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
        {q.options.filter(o => o.choice_id !== 'manual').map(option => <Button key={option.choice_id}
          variant={option.choice_id === 'recommended' ? 'contained' : 'outlined'} disabled={pending}
          onClick={() => void answer(option.choice_id)}>{option.label}</Button>)}
        <Button disabled={pending} onClick={() => setManual(true)}>{t('upload.humanQuestionManual')}</Button>
        <Button disabled={pending} onClick={() => setManual(false)}>{t('upload.humanQuestionLater')}</Button>
      </Box>
      {q.options.filter(o => o.choice_id === 'recommended').map(option =>
        <Typography key={option.choice_id} variant="body2" sx={{ mt: 1 }}>{option.description}</Typography>)}
      {manual && <Box sx={{ mt: 1 }}>
        <TextField fullWidth multiline label={t('upload.humanQuestionDirection')} value={draft.manual_text}
          onChange={e => update({ ...draft, manual_text: e.target.value })} inputProps={{ maxLength: 4000 }} />
        <TextField fullWidth multiline sx={{ mt: 1 }} label={t('upload.humanQuestionReason')} value={draft.reason}
          onChange={e => update({ ...draft, reason: e.target.value })} inputProps={{ maxLength: 4000 }} />
        <Button disabled={pending || !draft.manual_text.trim() || !draft.reason.trim()} onClick={() => void answer('manual')}>
          {t('upload.humanQuestionSend')}</Button>
      </Box>}
    </>}
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
  </Box>
})

export default function UploadHumanQuestions({ task, onAnswered }: { task: UploadTaskState; onAnswered?: () => void }) {
  const { user } = useAuth()
  const { t } = useLanguage()
  const [queue, setQueue] = useState<Queue | null>(null)
  const [loadedFor, setLoadedFor] = useState('')
  const [error, setError] = useState('')
  const [refreshRevision, setRefreshRevision] = useState(0)
  const answered = useRef(onAnswered)
  answered.current = onAnswered
  const refresh = useCallback(() => { setRefreshRevision(value => value + 1); answered.current?.() }, [])
  const revision = task.human_questions_summary?.queue_revision
  const identity = `${task.task_id}:${user?.id}`
  useEffect(() => {
    let stopped = false
    if (!revision || !user?.id) { setQueue(null); return }
    void api.get<{ ok: boolean; data: Queue }>(`/api/upload-tasks/${task.task_id}/human-questions`).then(response => {
      if (!stopped) { setQueue(unwrapData(response)); setLoadedFor(identity); setError('') }
    }).catch((reason: any) => { if (!stopped) setError(reason.message || t('upload.operationFailed')) })
    return () => { stopped = true }
  }, [task.task_id, revision, refreshRevision, user?.id, t])
  const visibleQueue = loadedFor === identity ? queue : null
  if (!visibleQueue?.questions.length && !error) return null
  return <Box data-testid="upload-human-questions" sx={{ mt: 2 }}>
    <Typography fontWeight={700}>{t('upload.humanQuestionTitle')} · {visibleQueue?.pending_count || 0}</Typography>
    <Typography variant="body2">{t('upload.humanQuestionHelp')}</Typography>
    {error && <Alert severity="error">{error}<Button onClick={refresh}>{t('upload.humanQuestionRefresh')}</Button></Alert>}
    {visibleQueue?.questions.map(question => <QuestionCard key={`${task.task_id}:${user?.id}:${question.question_id}:${question.prompt_revision}`}
      question={question} queueRevision={visibleQueue.queue_revision} taskId={task.task_id} writable={visibleQueue.can_answer_existing}
      storageKey={`humanq:${task.task_id}:${user?.id}:${question.question_id}:${question.prompt_revision}`} refresh={refresh} />)}
  </Box>
}
