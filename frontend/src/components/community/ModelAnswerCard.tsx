import React, { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Alert, Avatar, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Link, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityTurn, communityErrorKey } from '../../lib/community'
import CommunityComposer from './CommunityComposer'
import CommunityMarkdown from './CommunityMarkdown'

function AnswerSegment({ entry, turn, index, reload }: { entry: CommunityEntry; turn: CommunityTurn; index: number; reload: () => void }) {
  const { t, lang } = useLanguage(); const { user } = useAuth()
  const [expanded, setExpanded] = useState(turn.body.length < 1200), [editing, setEditing] = useState(false), [error, setError] = useState('')
  const [history, setHistory] = useState<Array<{ revision: number; body: string }> | null>(null)
  useEffect(() => { const expand = (event: Event) => { if ((event as CustomEvent).detail === turn.key) setExpanded(true) }; window.addEventListener('community-expand-answer', expand); return () => window.removeEventListener('community-expand-answer', expand) }, [turn.key])
  const manager = user?.role === 'superadmin' && user.is_email_verified
  const revisions = async () => {
    try { const result = await api.get<{ items: Array<{ revision: number; body: string }> }>(turn.id ? `${COMMUNITY_API}/ai/turns/${turn.id}/revisions` : `${COMMUNITY_API}/ai/entries/${entry.id}/revisions`); setHistory(result.items) } catch (e) { setError(communityErrorKey(e)) }
  }
  return <Box id={`answer-${turn.key}`} sx={{ scrollMarginTop: 24, py: 2 }}>
    <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1.5 }}>
      <Typography fontWeight={700}>{t(index === 0 ? 'community.initialAnswer' : 'community.additionalAnswer')}</Typography>
      {turn.sequence > 0 && <Chip size="small" variant="outlined" label={`#${turn.sequence}`} />}
      <Typography variant="caption" color="text.secondary">{new Date(turn.created_at).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US')}</Typography>
      {turn.human_edited && <Chip size="small" label={t('community.humanEdited')} />}
    </Stack>
    {turn.sources_available === false ? <Alert severity="info">{t('community.sourcesUnavailable')}</Alert> : editing ? <CommunityComposer markdown initialBody={turn.body} maxLength={20000} submitLabel="community.save" onCancel={() => setEditing(false)} onSubmit={async body => {
      await api.patch(turn.id ? `${COMMUNITY_API}/ai/turns/${turn.id}` : `${COMMUNITY_API}/entries/${entry.id}`, { body, revision: turn.id ? turn.revision : entry.revision }); setEditing(false); reload()
    }} /> : <>
      <Box sx={{ maxHeight: expanded ? 'none' : 320, overflow: 'hidden', position: 'relative', fontSize: '1rem', lineHeight: 1.9, '& p': { lineHeight: 1.9 }, '& pre': { overflowX: 'auto' }, '& table': { display: 'block', overflowX: 'auto' }, ...(!expanded ? { maskImage: 'linear-gradient(to bottom, black 75%, transparent)' } : {}) }}><CommunityMarkdown content={turn.body} /></Box>
      {turn.body.length >= 1200 && <Button onClick={() => setExpanded(v => !v)}>{t(expanded ? 'community.collapseAnswer' : 'community.expandAnswer')}</Button>}
    </>}
    {!!turn.replies?.length && <Stack direction="row" gap={1} flexWrap="wrap" sx={{ my: 1 }}><Typography variant="caption" color="text.secondary">{t('community.respondingTo')}</Typography>{turn.replies.map(reply => <Link key={reply.key} href={`#answer-${reply.key}`} onClick={() => window.dispatchEvent(new CustomEvent('community-expand-answer', { detail: reply.key }))} variant="caption">{reply.model_name} {reply.sequence ? `#${reply.sequence}` : reply.key}</Link>)}</Stack>}
    {!!turn.citations?.length && <Box sx={{ bgcolor: 'action.hover', borderRadius: 1, px: 1.5, py: 1, mt: 1 }}><Typography variant="caption" color="text.secondary">{t('community.sources')}</Typography>{turn.citations.map(source => <Typography key={source.id} variant="body2"><Link component={RouterLink} to={`/papers/${source.paper_id}`}>[{source.id}] {source.title}</Link></Typography>)}</Box>}
    {manager && <Stack direction="row" gap={1} sx={{ mt: 1 }}>{turn.sources_available !== false && <Button size="small" onClick={() => setEditing(v => !v)}>{t('community.edit')}</Button>}<Button size="small" onClick={() => void revisions()}>{t('community.history')}</Button></Stack>}
    {error && <Alert severity="error">{t(error)}</Alert>}
    <Dialog open={history !== null} onClose={() => setHistory(null)} fullWidth maxWidth="md"><DialogTitle>{t('community.history')}</DialogTitle><DialogContent>{history?.map(item => <Box key={item.revision}><Typography>{t('community.version')} {item.revision}</Typography><CommunityMarkdown content={item.body} /></Box>)}</DialogContent><DialogActions><Button onClick={() => setHistory(null)}>{t('community.cancel')}</Button></DialogActions></Dialog>
  </Box>
}

export default function ModelAnswerCard({ entry, reload }: { entry: CommunityEntry; reload: () => void }) {
  const { t } = useLanguage(); const { user } = useAuth(); const [hiding, setHiding] = useState(false), [reason, setReason] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const brand = `${entry.model_name} ${entry.model}`.toLowerCase()
  const deepseek = brand.includes('deepseek'), openai = brand.includes('openai') || brand.includes('gpt')
  const color = deepseek ? '#4D6BFE' : openai ? '#087F6F' : '#7355B5'
  const label = deepseek ? 'DeepSeek' : openai ? 'OpenAI' : entry.model_name
  const turns = entry.turns?.length ? entry.turns : [{ key: `A${entry.id}`, id: null, body: entry.body, sequence: 0, revision: entry.revision || 1, human_edited: entry.human_edited, created_at: entry.created_at, citations: entry.citations, sources_available: entry.sources_available }]
  return <Card id={`entry-${entry.id}`} variant="outlined" sx={{ mb: 2.5, borderRadius: 2.5, borderColor: 'divider', borderTop: `3px solid ${color}`, boxShadow: '0 3px 14px rgba(25,40,65,.04)' }}>
    <CardContent sx={{ px: { xs: 2, sm: 3.5 }, py: 2.5 }}>
      <Stack direction="row" gap={1.5} alignItems="center"><Avatar sx={{ bgcolor: color, width: 44, height: 44, fontWeight: 800 }}>{deepseek ? 'D' : openai ? 'O' : 'AI'}</Avatar><Box sx={{ minWidth: 0, flex: 1 }}><Typography fontWeight={800} fontSize={18}>{label}</Typography><Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{entry.model}</Typography></Box><Chip size="small" variant="outlined" label={t('community.aiGenerated')} /></Stack>
      <Box sx={{ maxWidth: '88ch', ml: { xs: 0, md: 7 }, mt: 1 }}>{turns.map((turn, index) => <React.Fragment key={turn.key}>{index > 0 && <Divider sx={{ my: 1 }} />}<AnswerSegment entry={entry} turn={turn} index={index} reload={reload} /></React.Fragment>)}</Box>
      {user?.role === 'superadmin' && <Box sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 1, textAlign: 'right' }}><Button size="small" color="inherit" onClick={() => setHiding(true)}>{t('community.hide')}</Button></Box>}
      {error && <Alert severity="error">{t(error)}</Alert>}
    </CardContent>
    <Dialog open={hiding} onClose={() => !busy && setHiding(false)} fullWidth maxWidth="sm"><DialogTitle>{t('community.reason')}</DialogTitle><DialogContent><TextField fullWidth multiline minRows={3} label={t('community.reason')} value={reason} onChange={e => setReason(e.target.value)} sx={{ mt: 1 }} /></DialogContent><DialogActions><Button disabled={busy} onClick={() => setHiding(false)}>{t('community.cancel')}</Button><Button disabled={busy || reason.trim().length < 5} onClick={async () => { setBusy(true); try { await api.post(`${COMMUNITY_API}/entries/${entry.id}/moderate`, { action: 'hide', reason, revision: entry.revision }); setHiding(false); reload() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) } }}>{t('community.hide')}</Button></DialogActions></Dialog>
  </Card>
}
