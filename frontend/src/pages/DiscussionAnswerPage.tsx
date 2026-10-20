import React, { useEffect } from 'react'
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom'
import { Alert, Box, Button, CircularProgress, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { CommunityEntry, useCommunityLoad } from '../lib/community'
import ModelAnswerCard from '../components/community/ModelAnswerCard'
import EntryCard from '../components/community/EntryCard'
import CommentPanel from '../components/community/CommentPanel'

export default function DiscussionAnswerPage() {
  const { id, answerId } = useParams(); const { t } = useLanguage(); const location = useLocation()
  const valid = /^\d+$/.test(id || '') && /^\d+$/.test(answerId || '')
  const answer = useCommunityLoad<CommunityEntry>(valid ? `/questions/${id}/answers/${answerId}` : null)
  const question = useCommunityLoad<CommunityEntry>(valid && answer.data ? `/entries/${id}` : null)
  useEffect(() => {
    if (!valid) return
    const timer = window.setInterval(() => { answer.reload(); question.reload() }, 5000)
    return () => window.clearInterval(timer)
  }, [id, answerId, valid, answer.reload, question.reload])
  useEffect(() => {
    if (!answer.data || !location.hash) return
    const key = location.hash.slice(1)
    if (!/^answer-A\d+(T\d+)?$/.test(key)) return
    const frame = window.requestAnimationFrame(() => document.getElementById(key)?.scrollIntoView?.({ block: 'start' }))
    return () => window.cancelAnimationFrame(frame)
  }, [answer.data, location.hash])
  const reload = () => { answer.reload(); question.reload() }
  return <Box sx={{ width: '100%', maxWidth: 680, mx: 'auto' }}>
    <Button component={RouterLink} to={valid ? `/share/discussions/${id}#entry-${answerId}` : '/share/discussions'} sx={{ mb: 1.5 }}>{t('community.backToQuestion')}</Button>
    {answer.loading && !answer.data && <CircularProgress />}
    {(!valid || answer.error || (!answer.loading && !answer.data)) && <Alert severity="error" action={valid ? <Button onClick={answer.reload}>{t('community.retry')}</Button> : undefined}>{t(answer.error || 'community.unavailable')}</Alert>}
    {question.data && <Typography variant="h1" sx={{ fontSize: { xs: 19, sm: 23 }, lineHeight: 1.5, mb: 2.5 }}><RouterLink to={`/share/discussions/${id}`} style={{ color: 'inherit', textDecoration: 'none' }}>{question.data.title}</RouterLink></Typography>}
    {answer.data && !answer.error && (answer.data.origin === 'ai' ? <ModelAnswerCard key={answer.data.id} entry={answer.data} reload={reload} /> : <Box sx={{ bgcolor: 'background.paper', p: 2.5, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}><EntryCard entry={answer.data} reload={reload}><CommentPanel target={{ answer_id: answer.data.id }} /></EntryCard></Box>)}
  </Box>
}
