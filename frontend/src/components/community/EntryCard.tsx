import React, { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Alert, Avatar, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Link, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityEntry, communityErrorKey } from '../../lib/community'
import CommunityComposer from './CommunityComposer'
import CommunityMarkdown from './CommunityMarkdown'

export default function EntryCard({ entry, reload, onReply, children }: { entry: CommunityEntry; reload: () => void; onReply?: () => void; children?: React.ReactNode }) {
  const { t, lang } = useLanguage(); const { user } = useAuth()
  const [editing, setEditing] = useState(false), [action, setAction] = useState<'delete' | 'report' | null>(null)
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [reported, setReported] = useState(false)
  const run = async (operation: () => Promise<unknown>) => {
    if (busy) return; setBusy(true); setError('')
    try { await operation(); setAction(null); reload() } catch (err) { setError(communityErrorKey(err)) } finally { setBusy(false) }
  }
  const visible = entry.status === 'visible'
  return <Box id={`entry-${entry.id}`} sx={{ py: 2, borderBottom: '1px solid', borderColor: 'divider', scrollMarginTop: 24, '&:target': { bgcolor: 'action.hover' } }}>
    {visible ? <>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Avatar src={entry.author?.avatar_url} sx={{ width: 28, height: 28 }}>{entry.author?.username?.[0]}</Avatar>
        {entry.author?.username ? <Link component={RouterLink} to={`/users/${entry.author.username}`}>{entry.author.username}</Link> : <Typography variant="body2">{t('community.deactivated')}</Typography>}
        {entry.author?.banned && <Chip size="small" label={t('community.banned')} />}
        <Typography variant="caption" color="text.secondary">{new Date(entry.created_at).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US')}</Typography>
        {entry.reply_to_id && <Typography variant="caption">{t('community.replyTo', { id: entry.reply_to_id })}</Typography>}
      </Stack>
      {entry.title && <Typography variant="h2" sx={{ my: 2, overflowWrap: 'anywhere' }}>{entry.title}</Typography>}
      {editing ? <CommunityComposer key={entry.id} initialBody={entry.body} initialTitle={entry.title} question={entry.kind === 'question'} markdown={['question', 'answer'].includes(entry.kind)} maxLength={entry.kind === 'comment' ? 2000 : 20000} submitLabel="community.save" onCancel={() => setEditing(false)} onSubmit={async (body, title) => { await api.patch(`${COMMUNITY_API}/entries/${entry.id}`, { body, ...(entry.kind === 'question' ? { title } : {}) }); setEditing(false); reload() }} />
        : ['question', 'answer'].includes(entry.kind) ? <CommunityMarkdown content={entry.body} /> : <Typography sx={{ my: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{entry.body}</Typography>}
      <Stack direction="row" gap={1} flexWrap="wrap">
        {entry.kind === 'answer' && <Button size="small" disabled={!user?.is_email_verified || busy} variant={entry.voted ? 'contained' : 'outlined'} onClick={() => void run(() => entry.voted ? api.del(`${COMMUNITY_API}/entries/${entry.id}/vote`) : api.put(`${COMMUNITY_API}/entries/${entry.id}/vote`))}>{t(entry.voted ? 'community.voted' : 'community.vote')} {entry.votes}</Button>}
        {onReply && entry.can_reply && <Button size="small" onClick={onReply}>{t('community.reply')}</Button>}
        {entry.can_edit && <Button size="small" onClick={() => setEditing(v => !v)}>{t('community.edit')}</Button>}
        {entry.can_delete && <Button size="small" color="warning" onClick={() => setAction('delete')}>{t('community.remove')}</Button>}
        {user?.is_email_verified && <Button size="small" color="inherit" onClick={() => { setAction('report'); setReason('') }}>{t('community.report')}</Button>}
      </Stack>
    </> : <Typography color="text.secondary">{t(entry.status === 'hidden' ? 'community.hidden' : 'community.deleted')}</Typography>}
    {error && <Alert severity="error">{t(error)}</Alert>}{reported && <Alert severity="success" onClose={() => setReported(false)}>{t('community.reportSent')}</Alert>}
    {children}
    <Dialog open={Boolean(action)} onClose={() => { if (!busy) setAction(null) }} fullWidth maxWidth="sm">
      <DialogTitle>{t(action === 'delete' ? 'community.confirmDelete' : 'community.report')}</DialogTitle>
      {action === 'report' && <DialogContent><TextField label={t('community.reportReason')} value={reason} onChange={e => setReason(e.target.value)} multiline minRows={3} fullWidth inputProps={{ maxLength: 1000 }} sx={{ mt: 1 }} /></DialogContent>}
      <DialogActions><Button disabled={busy} onClick={() => setAction(null)}>{t('community.cancel')}</Button><Button disabled={busy || (action === 'report' && Array.from(reason.trim()).length < 5)} onClick={() => void run(async () => { if (action === 'delete') await api.del(`${COMMUNITY_API}/entries/${entry.id}`); else { await api.post(`${COMMUNITY_API}/entries/${entry.id}/reports`, { reason }); setReported(true) } })}>{t(action === 'delete' ? 'community.remove' : 'community.report')}</Button></DialogActions>
    </Dialog>
  </Box>
}
