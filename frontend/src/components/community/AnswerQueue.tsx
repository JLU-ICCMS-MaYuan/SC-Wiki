import React, { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../../lib/api'
import { useLanguage } from '../../context/LanguageContext'
import { COMMUNITY_API, communityErrorKey, useCommunityLoad } from '../../lib/community'

interface Model { key: string; name: string; model: string }
interface Request { id: number; sequence: number; model_name: string; model: string; state: string; error: string }
export default function AnswerQueue({ questionId, onChanged }: { questionId: number; onChanged: () => void }) {
  const { t } = useLanguage()
  const options = useCommunityLoad<{ items: Model[] }>('/ai/models')
  const queue = useCommunityLoad<{ items: Request[] }>(`/ai/questions/${questionId}/queue`)
  const [open, setOpen] = useState(false), [model, setModel] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [showAll, setShowAll] = useState(false)
  const pending = useRef<{ key: string; id: string } | null>(null)
  const active = queue.data?.items.some(item => ['queued', 'running'].includes(item.state))
  useEffect(() => { if (!active) return; const timer = window.setInterval(() => { queue.reload(); onChanged() }, 2500); return () => window.clearInterval(timer) }, [active])
  const act = async (retry?: number) => {
    if (busy) return
    const key = retry === undefined ? model : `retry-${retry}`
    if (!pending.current || pending.current.key !== key) pending.current = { key, id: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      await api.post(retry === undefined ? `${COMMUNITY_API}/ai/questions/${questionId}/answers` : `${COMMUNITY_API}/ai/answer-requests/${retry}/retry`, { request_id: pending.current.id, ...(retry === undefined ? { model_key: model } : {}) })
      pending.current = null; setOpen(false); queue.reload(); onChanged()
    } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) }
  }
  const visibleRequests = showAll ? queue.data?.items : queue.data?.items.filter((item, index, all) => ['queued', 'running'].includes(item.state) || index >= all.length - 3)
  return <Box>
    <Button variant="contained" onClick={() => { setOpen(true); setModel(options.data?.items[0]?.key || '') }}>{t('community.generateAnswer')}</Button>
    {queue.error && <Alert severity="error" sx={{ mt: 1 }}>{t(queue.error)}</Alert>}
    {error && <Alert severity="error" sx={{ mt: 1 }}>{t(error)}</Alert>}
    {!!queue.data?.items.length && <Box sx={{ mt: 2, bgcolor: 'action.hover', borderRadius: 2, p: 2 }}>
      <Typography variant="subtitle2">{t('community.answerQueue')}</Typography>
      {visibleRequests?.map(item => <Stack key={item.id} direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}>
        <Typography variant="caption" color="text.secondary">#{item.sequence}</Typography><Typography variant="body2">{item.model_name} · {item.model}</Typography>
        <Chip size="small" label={t(`community.states.${item.state}`)} color={item.state === 'running' ? 'primary' : item.state === 'failed' ? 'error' : 'default'} />
        {item.error && <Typography variant="caption" color="error">{t(`community.jobErrors.${item.error}`)}</Typography>}
        {item.state === 'failed' && <Button size="small" disabled={busy} onClick={() => void act(item.id)}>{t('community.retryAtEnd')}</Button>}
      </Stack>)}
      {queue.data.items.length > 3 && <Button size="small" onClick={() => setShowAll(value => !value)}>{t(showAll ? 'community.collapseAnswer' : 'community.showAll')}</Button>}
    </Box>}
    <Dialog open={open} onClose={() => !busy && setOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>{t('community.generateAnswer')}</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" sx={{ mb: 2 }}>{t('community.continuationHint')}</Typography>
        {options.error && <Alert severity="error">{t(options.error)}</Alert>}
        <TextField select fullWidth label={t('community.chooseModel')} value={model} onChange={e => setModel(e.target.value)} disabled={busy}>{options.data?.items.map(item => <MenuItem key={item.key} value={item.key}>{item.name} · {item.model}</MenuItem>)}</TextField>
        {error && <Alert severity="error" sx={{ mt: 1 }}>{t(error)}</Alert>}
      </DialogContent>
      <DialogActions><Button disabled={busy} onClick={() => setOpen(false)}>{t('community.cancel')}</Button><Button variant="contained" disabled={busy || !model} onClick={() => void act()}>{t('community.enqueueAnswer')}</Button></DialogActions>
    </Dialog>
  </Box>
}
