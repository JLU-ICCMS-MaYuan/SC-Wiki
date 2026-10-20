import React, { useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, LinearProgress, Stack, Typography } from '@mui/material'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityAIBatch, communityErrorKey, useCommunityLoad } from '../../lib/community'

export default function AIGenerationPanel({ version, pendingId, onChanged }: { version: number; pendingId?: string | null; onChanged: () => void }) {
  const { t } = useLanguage(); const list = useCommunityLoad<{ items: CommunityAIBatch[] }>('/ai/batches')
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { list.reload() }, [version])
  const navigate = useNavigate()
  const observed = React.useRef(new Set<string>())
  useEffect(() => {
    for (const item of list.data?.items || []) {
      if (item.state === 'queued' || item.state === 'running') observed.current.add(item.id)
      if (item.question_id && item.state === 'succeeded' && (observed.current.has(item.id) || item.id === pendingId)) { observed.current.delete(item.id); navigate(`/share/discussions/${item.question_id}`); break }
    }
  }, [list.data, pendingId])
  const active = list.data?.items.some(item => ['queued', 'running'].includes(item.state))
  useEffect(() => { if (!active) return; const timer = window.setInterval(() => { list.reload(); onChanged() }, 3000); return () => window.clearInterval(timer) }, [active])
  const retry = async (id: string) => { setBusy(true); setError(''); try { await api.post(`${COMMUNITY_API}/ai/batches/${id}/retry`); list.reload(); onChanged() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) } }
  return <Box sx={{ my: 2 }}>
    {active && <LinearProgress />}{(list.error || error) && <Alert severity="error">{t(list.error || error)}</Alert>}
    {list.data?.items.map(item => <Box key={item.id} sx={{ py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
      <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap"><Typography>{t('community.questionGeneration')} · {t(`community.states.${item.state}`)}</Typography>
        {item.question_id && <Button component={RouterLink} to={`/share/discussions/${item.question_id}`}>{t('community.open')} #{item.question_id}</Button>}
        {item.can_retry && <Button disabled={busy} onClick={() => void retry(item.id)}>{t('community.retry')}</Button>}
      </Stack>{item.error && <Typography color="error">{t(`community.jobErrors.${item.error}`)}</Typography>}

    </Box>)}
  </Box>
}
