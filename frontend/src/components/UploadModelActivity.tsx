import React, { useEffect, useRef, useState } from 'react'
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, CircularProgress, Typography } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import { type UploadTaskState, type ModelActivity, unwrapData } from '../lib/paperProcessing'

// 请求动态独立于科学表单；本地计时不触发草稿扫描或模型调用。
const UploadModelActivity: React.FC<{ task: UploadTaskState; onUpdated: (task: UploadTaskState) => void;
  onRetry: () => void; onManual: () => void }> = ({ task, onUpdated, onRetry, onManual }) => {
  const { t } = useLanguage()
  const [now, setNow] = useState(Date.now() / 1000)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [earlier, setEarlier] = useState<ModelActivity[]>([])
  const [more, setMore] = useState(true)
  const [historyLoading, setHistoryLoading] = useState(false)
  const currentTask = useRef(task.task_id)
  const mounted = useRef(true)
  currentTask.current = task.task_id
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { setEarlier([]); setMore(true); setError(''); setPending(false); setHistoryLoading(false) }, [task.task_id])
  const activity = task.model_activity
  const active = ['queued', 'extracting', 'reading', 'summarizing'].includes(task.status || '')
  const pausing = task.status === 'pausing'
  useEffect(() => {
    if (!active && !pausing) return
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => window.clearInterval(timer)
  }, [active, pausing])
  const action = async (name: 'pause' | 'resume') => {
    const targetId = task.task_id
    setPending(true); setError('')
    try {
      const result = await api.post<{ ok: boolean; data: UploadTaskState }>(`/api/upload-tasks/${task.task_id}/${name}`)
      if (mounted.current && currentTask.current === targetId) onUpdated(unwrapData(result))
    } catch (reason: any) { if (mounted.current && currentTask.current === targetId) setError(reason.message || t('upload.operationFailed')) }
    finally { if (mounted.current && currentTask.current === targetId) setPending(false) }
  }
  const history = [...new Map([...earlier, ...(activity?.history || [])]
    .map(event => [`${event.updated_at}:${event.status}:${event.phase}:${event.attempt}`, event] as const)).values()]
    .sort((a, b) => (a.updated_at || 0) - (b.updated_at || 0))
  const loadEarlier = async () => {
    const targetId = task.task_id
    if (!history[0]?.updated_at) return
    setHistoryLoading(true)
    try {
      const response = await api.get<{ ok: boolean; data: { events: ModelActivity[]; has_more: boolean } }>(
        `/api/upload-tasks/${task.task_id}/model-activity?before=${history[0].updated_at}`)
      const data = unwrapData(response)
      if (!mounted.current || currentTask.current !== targetId) return
      setEarlier(previous => [...data.events, ...previous]); setMore(data.has_more)
    } catch (reason: any) { if (mounted.current && currentTask.current === targetId) setError(reason.message || t('upload.operationFailed')) }
    finally { if (mounted.current && currentTask.current === targetId) setHistoryLoading(false) }
  }
  const status = ['paused', 'pausing', 'ready', 'failed', 'cancelled'].includes(task.status || '')
    ? task.status : activity?.status || task.status || 'queued'
  const phase = activity?.phase || task.reading_state || task.stage
  const phaseKey = `upload.modelPhase.${phase}`
  const phaseText = t(phaseKey) === phaseKey ? phase : t(phaseKey)
  const statusKey = `upload.modelStatus.${status}`
  const statusText = t(statusKey) === statusKey ? t(`upload.status.${task.status}`) : t(statusKey)
  const failed = task.processing_status === 'failed'
  return <Box data-testid="upload-model-activity" sx={{ mt: 2, p: 2, border: 1, borderColor: failed ? 'error.light' : 'divider', borderRadius: 2 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      {(active || pausing) && <CircularProgress size={16} />}
      <Typography fontWeight={700}>{t('upload.modelActivityTitle')} · {statusText}</Typography>
      <Box sx={{ flex: 1 }} />
      {(active || pausing) && <Button disabled={pending} color="warning" onClick={() => void action('pause')}>{t('upload.stopAndKeep')}</Button>}
      {task.status === 'paused' && <Button disabled={pending} variant="contained" onClick={() => void action('resume')}>{t('upload.continueParsing')}</Button>}
      {failed && <>
        <Button disabled={pending} variant="contained" onClick={task.execution_resumable ? () => void action('resume') : onRetry}>
          {t(task.execution_resumable ? 'upload.continueParsing' : 'upload.retryParse')}</Button>
        <Button disabled={pending} onClick={onManual}>{t('upload.manualFill')}</Button>
      </>}
    </Box>
    <Typography variant="body2" sx={{ mt: 1 }}>{phaseText}{activity?.filename ? ` · ${activity.filename}` : ''}
      {activity?.pages?.length ? ` · ${t('upload.modelPages', { pages: activity.pages.join(', ') })}` : ''}</Typography>
    {!!activity?.attempt && <Typography variant="body2" color="text.secondary">
      {t('upload.modelAttempt', { attempt: activity.attempt })}
      {active && activity.started_at ? ` · ${t('upload.modelWaitSeconds', { seconds: Math.max(0, Math.floor(now - activity.started_at)) })}` : ''}
    </Typography>}
    {activity?.status === 'retry_wait' && activity.retry_at && active && <Typography variant="body2">
      {t('upload.modelRetrySeconds', { seconds: Math.max(0, Math.ceil(activity.retry_at - now)) })}</Typography>}
    {activity?.action && <Typography variant="body2">{t('upload.modelTool', { name: activity.action })}</Typography>}
    {activity?.note && <Typography variant="body2">{t('upload.modelNote', { note: activity.note })}</Typography>}
    {activity?.error && <Alert severity={failed ? 'error' : 'warning'} sx={{ mt: 1 }}>
      {activity.error.status_code ? `HTTP ${activity.error.status_code} · ` : ''}{activity.error.message || activity.error.code}
      {` · ${t(activity.error.output_started ? 'upload.modelOutputStarted' : 'upload.modelNoOutput')}`}
      {activity.error.request_id && <Typography variant="caption" display="block">Request ID: {activity.error.request_id}</Typography>}
    </Alert>}
    {task.processing_error && !activity?.error && <Alert severity={failed ? 'error' : 'info'} sx={{ mt: 1 }}>{task.processing_error}</Alert>}
    {task.status === 'paused' && <Typography variant="body2" sx={{ mt: 1 }}>{t('upload.pausedRetention')}</Typography>}
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
    {!!activity?.history?.length && <Accordion disableGutters elevation={0} sx={{ mt: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>{t('upload.modelHistory')}</AccordionSummary>
      <AccordionDetails sx={{ maxHeight: 280, overflow: 'auto' }}>
        {more && (activity.history.length >= 100 || earlier.length > 0) && <Button disabled={historyLoading} onClick={() => void loadEarlier()}>{t('upload.modelEarlier')}</Button>}
        {history.map((event, index) => <Box key={`${event.updated_at}-${index}`} sx={{ mb: 1 }}>
          <Typography variant="body2">{event.updated_at ? new Date(event.updated_at * 1000).toLocaleTimeString() : ''}
            {' · '}{t(`upload.modelStatus.${event.status}`)}{event.attempt ? ` · ${t('upload.modelAttempt', { attempt: event.attempt })}` : ''}</Typography>
          <Typography variant="caption" display="block">{event.phase ? t(`upload.modelPhase.${event.phase}`) : ''}
            {event.filename ? ` · ${event.filename}` : ''}{event.pages?.length ? ` · ${t('upload.modelPages', { pages: event.pages.join(', ') })}` : ''}
            {event.action ? ` · ${t('upload.modelTool', { name: event.action })}` : ''}</Typography>
          {event.note && <Typography variant="caption" display="block">{t('upload.modelNote', { note: event.note })}</Typography>}
          {event.error && <Typography variant="caption" sx={{ overflowWrap: 'anywhere' }}>
            {event.error.status_code ? `HTTP ${event.error.status_code} · ` : ''}{event.error.message}
            {event.error.request_id ? ` · Request ID: ${event.error.request_id}` : ''}</Typography>}
        </Box>)}
      </AccordionDetails>
    </Accordion>}
  </Box>
}
export default UploadModelActivity
