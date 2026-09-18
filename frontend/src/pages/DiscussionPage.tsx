import React, { useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { Alert, Box, Button, Card, CardContent, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityList, focusedEntry, useCommunityLoad } from '../lib/community'
import CommunityComposer from '../components/community/CommunityComposer'
import CommentPanel from '../components/community/CommentPanel'
import EntryCard from '../components/community/EntryCard'

function QuestionDetail({ id }: { id: string }) {
  const { t } = useLanguage(); const [sort, setSort] = useState('votes'), [offset, setOffset] = useState(0), [focus, setFocus] = useState(focusedEntry())
  const question = useCommunityLoad<CommunityEntry>(`/entries/${id}`)
  const answers = useCommunityLoad<CommunityList<CommunityEntry>>(question.data?.kind === 'question' && question.data.status === 'visible' ? `/entries?kind=answer&question_id=${id}&sort=${sort}&offset=${offset}${focus ? `&focus_id=${focus}` : ''}` : null)
  const reload = () => { question.reload(); answers.reload() }
  useEffect(() => { if (answers.data && focus) document.getElementById(`entry-${focus}`)?.scrollIntoView?.({ block: 'center' }) }, [answers.data, focus])
  if (question.loading && !question.data) return <CircularProgress />
  if (question.data?.kind !== 'question') return <Alert severity="error" action={<Button onClick={question.reload}>{t('community.retry')}</Button>}>{t(question.error || 'community.unavailable')}</Alert>
  return <>
    <Button component={RouterLink} to="/share/discussions">{t('community.back')}</Button>
    {question.error && <Alert severity="warning" action={<Button onClick={question.reload}>{t('community.retry')}</Button>}>{t(question.error)}</Alert>}
    <EntryCard entry={question.data} reload={reload} />
    <Box sx={{ my: 3 }}><Typography variant="h2">{t('community.answer')}</Typography><CommunityComposer markdown maxLength={20000} onSubmit={async body => { const entry = await api.post<CommunityEntry>(`${COMMUNITY_API}/entries`, { kind: 'answer', question_id: Number(id), body }); setFocus(entry.id); setOffset(0); reload() }} /></Box>
    <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="h2">{t('community.answers')}</Typography><TextField select size="small" label={t('community.answers')} value={sort} onChange={e => { setSort(e.target.value); setOffset(0) }}><MenuItem value="votes">{t('community.votes')}</MenuItem><MenuItem value="latest">{t('community.latest')}</MenuItem></TextField></Stack>
    {focus && <Alert severity="info" action={<Button onClick={() => { setFocus(undefined); window.history.replaceState(null, '', window.location.pathname) }}>{t('community.showAll')}</Button>}>{t('community.focused')}</Alert>}
    {answers.loading && <CircularProgress size={24} />}{answers.error && <Alert severity="error" action={<Button onClick={answers.reload}>{t('community.retry')}</Button>}>{t(answers.error)}</Alert>}
    {answers.data?.items.map(entry => <EntryCard key={entry.id} entry={entry} reload={reload}><CommentPanel key={`comments-${entry.id}-${focus || 'all'}`} target={{ answer_id: entry.id }} /></EntryCard>)}
    {answers.data?.items.length === 0 && <Typography sx={{ my: 2 }}>{t('community.empty')}</Typography>}
    {answers.data && answers.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= answers.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </>
}
export default function DiscussionPage() {
  const { id } = useParams(); const { t } = useLanguage(); const navigate = useNavigate()
  const [asking, setAsking] = useState(false), [term, setTerm] = useState(''), [query, setQuery] = useState(''), [sort, setSort] = useState('latest'), [offset, setOffset] = useState(0)
  const list = useCommunityLoad<CommunityList<CommunityEntry>>(id ? null : `/questions?q=${encodeURIComponent(query)}&sort=${sort}&offset=${offset}`)
  useEffect(() => { const timer = window.setTimeout(() => { setQuery(term); setOffset(0) }, 300); return () => window.clearTimeout(timer) }, [term])
  if (id) return <QuestionDetail key={id} id={id} />
  return <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
    <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2}><Box><Typography variant="h1">{t('community.title')}</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>{t('community.intro')}</Typography></Box><Button variant="contained" sx={{ flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => setAsking(v => !v)}>{t('community.ask')}</Button></Stack>
    {asking && <Card sx={{ my: 2 }}><CardContent><CommunityComposer question markdown maxLength={20000} onCancel={() => setAsking(false)} onSubmit={async (body, title) => { const created = await api.post<CommunityEntry>(`${COMMUNITY_API}/entries`, { kind: 'question', body, title }); setAsking(false); navigate(`/share/discussions/${created.id}`) }} /></CardContent></Card>}
    <Stack direction={{ xs: 'column', sm: 'row' }} gap={2} sx={{ my: 3 }}><TextField fullWidth label={t('community.search')} value={term} onChange={e => setTerm(e.target.value)} inputProps={{ maxLength: 200 }} /><TextField select label={t('community.title')} value={sort} onChange={e => { setSort(e.target.value); setOffset(0) }} sx={{ minWidth: 160 }}><MenuItem value="latest">{t('community.latest')}</MenuItem><MenuItem value="active">{t('community.active')}</MenuItem></TextField></Stack>
    {list.loading && <CircularProgress />}{list.error && <Alert severity="error" action={<Button onClick={list.reload}>{t('community.retry')}</Button>}>{t(list.error)}</Alert>}
    {list.data?.items.map(entry => <Card key={entry.id} sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ overflowWrap: 'anywhere' }}><RouterLink to={`/share/discussions/${entry.id}`}>{entry.title}</RouterLink></Typography><Typography color="text.secondary" sx={{ mt: 1 }}>{entry.author?.username || t('community.deactivated')} · {t('community.answerCount', { count: entry.answer_count })}</Typography></CardContent></Card>)}
    {list.data?.items.length === 0 && <Typography>{t('community.empty')}</Typography>}
    {list.data && list.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= list.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </Box>
}
