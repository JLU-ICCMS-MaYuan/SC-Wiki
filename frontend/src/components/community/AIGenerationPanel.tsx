import React, { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Alert, Box, Button, LinearProgress, Stack, Typography } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityAIBatch, CommunityAITask, communityErrorKey, useCommunityLoad } from '../../lib/community'

export function ModelTasks({ tasks, onChanged }: { tasks: CommunityAITask[]; onChanged: () => void }) {
  const { user } = useAuth(); const { t } = useLanguage(); const [busy, setBusy] = useState<number | null>(null), [error, setError] = useState('')
  const retry = async (task: CommunityAITask) => {
    if (busy !== null) return; setBusy(task.id); setError('')
    try { await api.post(task.error === 'preparation_failed' && task.batch_id ? `${COMMUNITY_API}/ai/batches/${task.batch_id}/retry` : `${COMMUNITY_API}/ai/tasks/${task.id}/retry`); onChanged() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(null) }
  }
  return <Box sx={{ my: 2 }}>{tasks.map(task => <Stack key={task.id} direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ my: 1 }}>
    <Typography>{task.model_name} · {task.model}</Typography><Typography color="text.secondary">{t(`community.states.${task.state}`)}</Typography>
    {task.error && <Typography color="error">{t(`community.jobErrors.${task.error}`)}</Typography>}
    {user?.role === 'superadmin' && ['succeeded', 'failed'].includes(task.state) && <Button disabled={busy !== null} onClick={() => void retry(task)}>{t(task.state === 'failed' ? 'community.retry' : 'community.regenerate')}</Button>}
  </Stack>)}{error && <Alert severity="error">{t(error)}</Alert>}</Box>
}

export default function AIGenerationPanel({ version, onChanged }: { version: number; onChanged: () => void }) {
  const { t } = useLanguage(); const list = useCommunityLoad<{ items: CommunityAIBatch[] }>('/ai/batches')
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { list.reload() }, [version])
  const active = list.data?.items.some(item => ['queued', 'running'].includes(item.state))
  useEffect(() => { if (!active) return; const timer = window.setInterval(() => { list.reload(); onChanged() }, 3000); return () => window.clearInterval(timer) }, [active])
  const retry = async (id: string) => { setBusy(true); setError(''); try { await api.post(`${COMMUNITY_API}/ai/batches/${id}/retry`); list.reload(); onChanged() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) } }
  return <Box sx={{ my: 2 }}>
    {active && <LinearProgress />}{(list.error || error) && <Alert severity="error">{t(list.error || error)}</Alert>}
    {list.data?.items.map(item => <Box key={item.id} sx={{ py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
      <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap"><Typography>{t('community.generation')} · {t(`community.states.${item.state}`)}</Typography>
        {item.question_id && <Button component={RouterLink} to={`/share/discussions/${item.question_id}`}>{t('community.open')} #{item.question_id}</Button>}
        {item.can_retry && <Button disabled={busy} onClick={() => void retry(item.id)}>{t('community.retry')}</Button>}
      </Stack>{item.error && <Typography color="error">{t(`community.jobErrors.${item.error}`)}</Typography>}
      {item.question_id && <ModelTasks tasks={item.tasks} onChanged={() => { list.reload(); onChanged() }} />}
    </Box>)}
  </Box>
}
