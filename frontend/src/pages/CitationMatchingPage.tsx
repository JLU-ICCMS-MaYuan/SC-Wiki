import React, { useEffect, useState } from 'react'
import { Alert, Box, Chip, CircularProgress, Link, Paper, Stack, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'

interface MatchedPaper {
  paper_id: number
  title: string
  authors: string[]
  year: number | null
  doi: string | null
}
interface Decision { method: string | null; reason: string; stale?: boolean }
interface MatchingSnapshot {
  status: string
  paper: MatchedPaper
  references: Array<{ reference_index: number; raw_citation: string; title?: string;
    matched_paper?: MatchedPaper | null; decision: Decision }>
  downstream: Array<{ paper: MatchedPaper; decision: Decision }>
  parser_error?: string | null
  stale_count?: number
}

const CitationMatchingPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const { t } = useLanguage()
  const [snapshot, setSnapshot] = useState<MatchingSnapshot | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setSnapshot(null)
    setError('')
    api.get<{ data: MatchingSnapshot }>(`/api/upload-tasks/${taskId}/citation-matching`)
      .then(result => { if (active) setSnapshot(result.data) })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : t('kg.matchingLoadFailed')) })
    return () => { active = false }
  }, [taskId, t])

  const card = (paper: MatchedPaper | null, text: string, decision: Decision | undefined, key: string,
    referenceIndex?: number) => {
    const matched = Boolean(paper && snapshot?.status !== 'stale' && !decision?.stale)
    return <Paper key={key} variant="outlined" data-matched={String(matched)} sx={{ p: 1.5,
      borderColor: matched ? 'primary.main' : 'divider',
      bgcolor: theme => matched ? alpha(theme.palette.primary.main, 0.10) : theme.palette.background.paper,
      overflowWrap: 'anywhere' }}>
      {referenceIndex != null && <Typography variant="caption" color="text.secondary">#{referenceIndex + 1}</Typography>}
      <Typography variant="body2" fontWeight={matched ? 600 : 400}>
        {matched && paper ? <Link component={RouterLink} to={`/papers/${paper.paper_id}`}
          target="_blank" rel="noopener noreferrer">{paper.title}</Link> : text}
      </Typography>
      {matched && <Chip size="small" label={t('kg.matchingHit')} sx={{ mt: 0.75 }} />}
      {referenceIndex != null && text && matched && <Typography variant="body2" sx={{ mt: 0.75, whiteSpace: 'pre-wrap' }}>{text}</Typography>}
      {decision?.reason && <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.75 }}>
        {decision.stale ? t('kg.matchingTargetStale') : decision.reason}
      </Typography>}
    </Paper>
  }

  return <Box component="main" sx={{ py: 2 }}>
    <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>{t('kg.matchingTitle')}</Typography>
    {error ? <Alert severity="error">{error}</Alert> : !snapshot ? <CircularProgress /> : <>
      {snapshot.status === 'stale' && <Alert severity="warning" sx={{ mb: 2 }}>{t('kg.matchingStale')}</Alert>}
      {!!snapshot.stale_count && <Alert severity="warning" sx={{ mb: 2 }}>{t('kg.matchingTargetStale')}</Alert>}
      {snapshot.status === 'unavailable' && <Alert severity="warning" sx={{ mb: 2 }}>
        {snapshot.parser_error || t('kg.matchingUnavailable')}
      </Alert>}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 0.85fr 1.25fr' }, gap: 3,
        alignItems: 'start' }}>
        <Stack component="section" aria-label={t('kg.matchingCiting')} spacing={1.5}>
          <Typography variant="h6">{t('kg.matchingCiting')}</Typography>
          {snapshot.downstream.length ? snapshot.downstream.map(entry =>
            card(entry.paper, entry.paper.title, entry.decision, String(entry.paper.paper_id))) :
            <Typography color="text.secondary">{t('kg.matchingNoCiting')}</Typography>}
        </Stack>
        <Paper component="section" aria-label={t('kg.matchingCurrent')} variant="outlined"
          sx={{ p: 2, position: { md: 'sticky' }, top: 20 }}>
          <Typography variant="overline" color="text.secondary">{t('kg.matchingCurrent')}</Typography>
          <Typography variant="h6" sx={{ overflowWrap: 'anywhere' }}>{snapshot.paper.title}</Typography>
          <Typography variant="body2" color="text.secondary">{snapshot.paper.authors.join(', ')}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
            {[snapshot.paper.year, snapshot.paper.doi].filter(Boolean).join(' · ')}
          </Typography>
        </Paper>
        <Stack component="section" aria-label={t('kg.matchingReferences')} spacing={1.5}>
          <Typography variant="h6">{t('kg.matchingReferences')}</Typography>
          {snapshot.references.length ? snapshot.references.map(reference =>
            card(reference.matched_paper || null, reference.raw_citation || reference.title || '', reference.decision,
              String(reference.reference_index), reference.reference_index)) :
            <Typography color="text.secondary">{t('kg.matchingNoReferences')}</Typography>}
        </Stack>
      </Box>
    </>}
  </Box>
}

export default CitationMatchingPage
