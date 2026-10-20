import React, { useEffect, useRef, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { Alert, Box, Button, Card, CardContent, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityList, CommunityAIBatch, communityErrorKey, focusedEntry, useCommunityLoad } from '../lib/community'
import CommunityComposer from '../components/community/CommunityComposer'
import CommentPanel from '../components/community/CommentPanel'
import EntryCard from '../components/community/EntryCard'
import AIGenerationPanel, { ModelTasks } from '../components/community/AIGenerationPanel'

function QuestionDetail({ id }: { id: string }) {
  const { t } = useLanguage(); const [offset, setOffset] = useState(0), [focus, setFocus] = useState(focusedEntry())
  const question = useCommunityLoad<CommunityEntry>(`/entries/${id}`)
  const answerSort = question.data?.generation_tasks?.length ? 'models' : 'latest'
  const answers = useCommunityLoad<CommunityList<CommunityEntry>>(question.data?.kind === 'question' && question.data.status === 'visible' ? `/entries?kind=answer&question_id=${id}&sort=${answerSort}&offset=${offset}${focus ? `&focus_id=${focus}` : ''}` : null)
  const reload = () => { question.reload(); answers.reload() }
  const active = question.data?.generation_tasks?.some(task => ['queued', 'running'].includes(task.state))
  useEffect(() => { if (!active) return; const timer = window.setInterval(reload, 3000); return () => window.clearInterval(timer) }, [active])
  useEffect(() => { if (answers.data && focus) document.getElementById(`entry-${focus}`)?.scrollIntoView?.({ block: 'center' }) }, [answers.data, focus])
  if (question.loading && !question.data) return <CircularProgress />
  if (question.data?.kind !== 'question') return <Alert severity="error" action={<Button onClick={question.reload}>{t('community.retry')}</Button>}>{t(question.error || 'community.unavailable')}</Alert>
  return <>
    <Button component={RouterLink} to="/share/discussions">{t('community.back')}</Button>
    <EntryCard entry={question.data} reload={reload} />
    <ModelTasks tasks={question.data.generation_tasks || []} onChanged={reload} />
    <Typography variant="h2">{t('community.answers')}</Typography>
    {focus && <Alert severity="info" action={<Button onClick={() => { setFocus(undefined); window.history.replaceState(null, '', window.location.pathname) }}>{t('community.showAll')}</Button>}>{t('community.focused')}</Alert>}
    {answers.loading && <CircularProgress size={24} />}{answers.error && <Alert severity="error" action={<Button onClick={answers.reload}>{t('community.retry')}</Button>}>{t(answers.error)}</Alert>}
    {answers.data?.items.map(entry => <EntryCard key={entry.id} entry={entry} reload={reload}>{entry.origin !== 'ai' && <CommentPanel target={{ answer_id: entry.id }} />}</EntryCard>)}
    {answers.data?.items.length === 0 && <Typography sx={{ my: 2 }}>{t('community.empty')}</Typography>}
    {answers.data && answers.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= answers.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </>
}
export default function DiscussionPage() {
  const { id } = useParams(); const { t } = useLanguage(); const { user } = useAuth(); const navigate = useNavigate()
  const [asking, setAsking] = useState(false), [term, setTerm] = useState(''), [query, setQuery] = useState(''), [sort, setSort] = useState('latest'), [offset, setOffset] = useState(0)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [version, setVersion] = useState(0), [jobs, setJobs] = useState(true)
  const request = useRef<{ content: string; id: string } | null>(null)
  const list = useCommunityLoad<CommunityList<CommunityEntry>>(id ? null : `/questions?q=${encodeURIComponent(query)}&sort=${sort}&offset=${offset}`)
  useEffect(() => { const timer = window.setTimeout(() => { setQuery(term); setOffset(0) }, 300); return () => window.clearTimeout(timer) }, [term])
  const submit = async (body?: string, title?: string) => {
    const content = JSON.stringify([body, title])
    if (!request.current || request.current.content !== content) request.current = { content, id: crypto.randomUUID() }
    const batch = await api.post<CommunityAIBatch>(`${COMMUNITY_API}/ai/questions${title === undefined ? '/generate' : ''}`, { request_id: request.current.id, ...(title === undefined ? {} : { title, body }) })
    request.current = null; setAsking(false); setJobs(true); setVersion(v => v + 1); list.reload()
    if (batch.question_id) navigate(`/share/discussions/${batch.question_id}`)
  }
  const generate = async () => { if (busy) return; setBusy(true); setError(''); try { await submit() } catch (e) { setError(communityErrorKey(e)) } finally { setBusy(false) } }
  if (id) return <QuestionDetail key={id} id={id} />
  const manager = user?.role === 'superadmin'
  return <Box>
    <Typography variant="h1">{t('community.title')}</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>{t('community.intro')}</Typography>
    {manager && <Stack direction="row" gap={1} flexWrap="wrap" sx={{ my: 2 }}><Button variant="contained" disabled={busy} onClick={() => setAsking(v => !v)}>{t('community.ask')}</Button><Button variant="outlined" disabled={busy} onClick={() => void generate()}>{t(busy ? 'community.publishing' : 'community.aiAsk')}</Button><Button onClick={() => setJobs(v => !v)}>{t('community.generation')}</Button><Button component={RouterLink} to="/admin/community">{t('community.moderation')}</Button></Stack>}
    {error && <Alert severity="error">{t(error)}</Alert>}
    {manager && asking && <Card sx={{ my: 2 }}><CardContent><CommunityComposer question markdown maxLength={20000} onCancel={() => setAsking(false)} onSubmit={submit} /></CardContent></Card>}
    {manager && jobs && <AIGenerationPanel version={version} onChanged={list.reload} />}
    <Stack direction={{ xs: 'column', sm: 'row' }} gap={2} sx={{ my: 3 }}><TextField fullWidth label={t('community.search')} value={term} onChange={e => setTerm(e.target.value)} inputProps={{ maxLength: 200 }} /><TextField select label={t('community.title')} value={sort} onChange={e => { setSort(e.target.value); setOffset(0) }} sx={{ minWidth: 160 }}><MenuItem value="latest">{t('community.latest')}</MenuItem><MenuItem value="active">{t('community.active')}</MenuItem></TextField></Stack>
    {list.loading && <CircularProgress />}{list.error && <Alert severity="error" action={<Button onClick={list.reload}>{t('community.retry')}</Button>}>{t(list.error)}</Alert>}
    {list.data?.items.map(entry => <Card key={entry.id} sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ overflowWrap: 'anywhere' }}><RouterLink to={`/share/discussions/${entry.id}`}>{entry.title}</RouterLink></Typography><Typography color="text.secondary" sx={{ mt: 1 }}>{entry.origin === 'ai' ? `${t('community.aiGenerated')} · ${entry.model_name}` : entry.author?.username || t('community.deactivated')} · {t('community.answerCount', { count: entry.answer_count })}</Typography></CardContent></Card>)}
    {list.data?.items.length === 0 && <Typography>{t('community.empty')}</Typography>}
    {list.data && list.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= list.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </Box>
}
