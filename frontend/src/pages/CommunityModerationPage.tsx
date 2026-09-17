import React, { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityList, communityErrorKey, useCommunityLoad } from '../lib/community'

interface Report { report: { id: number; reason: string }; entry: CommunityEntry; events: Array<{ id: number; action: string; reason: string; created_at: string }> }
export default function CommunityModerationPage() {
  const { t } = useLanguage(); const [status, setStatus] = useState('pending'), [offset, setOffset] = useState(0)
  const [action, setAction] = useState<{ id: number; name: string } | null>(null), [reason, setReason] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const list = useCommunityLoad<CommunityList<Report>>(`/moderation/reports?status=${status}&offset=${offset}`)
  const act = async () => {
    if (!action || busy) return; setBusy(true); setError('')
    try { await api.post(`${COMMUNITY_API}/entries/${action.id}/moderate`, { action: action.name, reason }); setAction(null); list.reload() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) }
  }
  return <Box><Typography variant="h1">{t('community.moderation')}</Typography><TextField select value={status} label={t('community.report')} onChange={e => { setStatus(e.target.value); setOffset(0) }} sx={{ my: 2, minWidth: 200 }}><MenuItem value="pending">{t('community.pending')}</MenuItem><MenuItem value="resolved">{t('community.resolved')}</MenuItem></TextField>
    {list.error && <Alert severity="error" action={<Button onClick={list.reload}>{t('community.retry')}</Button>}>{t(list.error)}</Alert>}
    {list.data?.items.map(item => <Card key={item.report.id} sx={{ mb: 2 }}><CardContent><Typography fontWeight={700}>{item.entry.title}</Typography><Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.entry.body}</Typography><Alert severity="warning" sx={{ my: 2 }}>{item.report.reason}</Alert>
      <Stack direction="row" gap={1}>{[...(item.entry.status === 'visible' ? ['hide'] : item.entry.status === 'hidden' ? ['restore'] : []), ...(status === 'pending' ? ['dismiss'] : [])].map(name => <Button key={name} onClick={() => { setAction({ id: item.entry.id, name }); setReason(''); setError('') }}>{t(`community.${name}`)}</Button>)}</Stack>
      {item.events.length > 0 && <Box sx={{ mt: 2 }}><Typography fontWeight={700}>{t('community.audit')}</Typography>{item.events.map(event => <Typography variant="body2" key={event.id}>{t(`community.${event.action}`)} · {event.reason} · {new Date(event.created_at).toLocaleString()}</Typography>)}</Box>}
    </CardContent></Card>)}
    {list.data?.items.length === 0 && <Typography>{t('community.empty')}</Typography>}
    {list.data && list.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= list.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
    <Dialog open={Boolean(action)} onClose={() => { if (!busy) setAction(null) }} fullWidth maxWidth="sm"><DialogTitle>{t('community.reason')}</DialogTitle><DialogContent>{error && <Alert severity="error">{t(error)}</Alert>}<TextField fullWidth multiline minRows={3} value={reason} label={t('community.reason')} onChange={e => setReason(e.target.value)} inputProps={{ maxLength: 1000 }} sx={{ mt: 1 }} /></DialogContent><DialogActions><Button disabled={busy} onClick={() => setAction(null)}>{t('community.cancel')}</Button><Button disabled={busy || Array.from(reason.trim()).length < 5} onClick={() => void act()}>{t('community.save')}</Button></DialogActions></Dialog>
  </Box>
}
