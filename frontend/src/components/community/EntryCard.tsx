import React, { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Link, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityEntry, communityErrorKey } from '../../lib/community'
import CommunityComposer from './CommunityComposer'
import CommunityMarkdown from './CommunityMarkdown'

export default function EntryCard({ entry, reload, children }: { entry: CommunityEntry; reload: () => void; onReply?: () => void; children?: React.ReactNode }) {
  const { t, lang } = useLanguage(); const { user } = useAuth()
  const [editing, setEditing] = useState(false), [action, setAction] = useState<'hide' | 'restore' | null>(null)
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [history, setHistory] = useState<Array<{ revision: number; body: string }> | null>(null)
  const manager = user?.role === 'superadmin' && user.is_email_verified
  const visible = entry.status === 'visible'
  const run = async (operation: () => Promise<unknown>) => {
    if (busy) return; setBusy(true); setError('')
    try { await operation(); setAction(null); reload() } catch (err) { setError(communityErrorKey(err)) } finally { setBusy(false) }
  }
  return <Box id={`entry-${entry.id}`} sx={{ py: 2, borderBottom: '1px solid', borderColor: 'divider', scrollMarginTop: 24, overflowWrap: 'anywhere' }}>
    {visible ? <>
      <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
        {entry.origin === 'ai' ? <><Chip size="small" label={t(entry.human_edited ? 'community.aiEdited' : 'community.aiGenerated')} /><Typography variant="body2">{entry.model_name} · {entry.model}</Typography></>
          : <>{entry.author?.username ? <Link component={RouterLink} to={`/users/${entry.author.username}`}>{entry.author.username}</Link> : <Typography>{t('community.deactivated')}</Typography>}{entry.human_edited && <Chip size="small" label={t('community.humanEdited')} />}</>}
        <Typography variant="caption" color="text.secondary">{new Date(entry.created_at).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US')}</Typography>
        {entry.category && <Chip size="small" label={t(`community.categories.${entry.category}`)} />}
      </Stack>
      {entry.title && <Typography variant="h2" sx={{ my: 2 }}>{entry.title}</Typography>}
      {entry.sources_available === false ? <Alert severity="info">{t('community.sourcesUnavailable')}</Alert> : editing ? <CommunityComposer initialBody={entry.body} markdown maxLength={20000} submitLabel="community.save" onCancel={() => setEditing(false)} onSubmit={async body => { await api.patch(`${COMMUNITY_API}/entries/${entry.id}`, { body, revision: entry.revision }); setEditing(false); reload() }} />
        : ['question', 'answer'].includes(entry.kind) ? <CommunityMarkdown content={entry.body} /> : <Typography sx={{ my: 1, whiteSpace: 'pre-wrap' }}>{entry.body}</Typography>}
      {!!entry.citations?.length && <Box sx={{ my: 1 }}><Typography fontWeight={600}>{t('community.sources')}</Typography>{entry.citations.map(source => <Typography key={source.id}><Link component={RouterLink} to={`/papers/${source.paper_id}`}>[{source.id}] {source.title}</Link></Typography>)}</Box>}
    </> : <Typography>{t(entry.status === 'hidden' ? 'community.hidden' : 'community.deleted')} #{entry.id}</Typography>}
    {manager && <Stack direction="row" gap={1} flexWrap="wrap">
      {visible && entry.can_edit && <Button onClick={() => setEditing(v => !v)}>{t('community.edit')}</Button>}
      {entry.status !== 'deleted' && <Button color="warning" onClick={() => { setAction(visible ? 'hide' : 'restore'); setReason('') }}>{t(visible ? 'community.hide' : 'community.restore')}</Button>}
      {entry.kind === 'answer' && <Button onClick={() => void run(async () => { const result = await api.get<{ items: Array<{ revision: number; body: string }> }>(`${COMMUNITY_API}/ai/entries/${entry.id}/revisions`); setHistory(result.items) })}>{t('community.history')}</Button>}
    </Stack>}
    {error && <Alert severity="error">{t(error)}</Alert>}{children}
    <Dialog open={!!action} onClose={() => { if (!busy) setAction(null) }} fullWidth maxWidth="sm"><DialogTitle>{t('community.reason')}</DialogTitle><DialogContent><TextField fullWidth multiline minRows={3} label={t('community.reason')} value={reason} onChange={e => setReason(e.target.value)} inputProps={{ maxLength: 1000 }} sx={{ mt: 1 }} /></DialogContent><DialogActions><Button disabled={busy} onClick={() => setAction(null)}>{t('community.cancel')}</Button><Button disabled={busy || reason.trim().length < 5} onClick={() => void run(() => api.post(`${COMMUNITY_API}/entries/${entry.id}/moderate`, { action, reason, revision: entry.revision }))}>{t('community.save')}</Button></DialogActions></Dialog>
    <Dialog open={history !== null} onClose={() => setHistory(null)} fullWidth maxWidth="md"><DialogTitle>{t('community.history')}</DialogTitle><DialogContent>{history?.length ? history.map(item => <Box key={item.revision} sx={{ mb: 3 }}><Typography>{t('community.version')} {item.revision}</Typography><CommunityMarkdown content={item.body} /></Box>) : <Typography>{t('community.empty')}</Typography>}</DialogContent><DialogActions><Button onClick={() => setHistory(null)}>{t('community.cancel')}</Button></DialogActions></Dialog>
  </Box>
}
