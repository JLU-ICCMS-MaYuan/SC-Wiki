import React, { useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { Alert, Box, Button, CircularProgress, Link, Stack, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { useCommunityLoad } from '../lib/community'
import CommentPanel from '../components/community/CommentPanel'

interface SystemDetail { system_key: string; papers: Array<{ id: number; title: string; year?: number }>; total: number }
function SystemDetailView({ systemKey }: { systemKey: string }) {
  const { t } = useLanguage(); const [offset, setOffset] = useState(0)
  const { data, error, loading, reload } = useCommunityLoad<SystemDetail>(`/systems/${encodeURIComponent(systemKey)}?offset=${offset}`)
  if (loading) return <CircularProgress />
  if (error || !data) return <Alert severity="error" action={<Button onClick={reload}>{t('community.retry')}</Button>}>{t(error || 'community.unavailable')}</Alert>
  return <Box sx={{ maxWidth: 1100, mx: 'auto' }}>
    <Typography variant="h1">{t('community.system', { key: data.system_key })}</Typography><Typography sx={{ my: 2 }} color="text.secondary">{t('community.systemHint')}</Typography>
    <Typography variant="h2">{t('community.papers')}</Typography>
    {data.papers.length ? <Stack gap={1} sx={{ my: 2 }}>{data.papers.map(p => <Link key={p.id} component={RouterLink} to={`/papers/${p.id}`}>{p.title} {p.year ? `(${p.year})` : ''}</Link>)}</Stack> : <Typography sx={{ my: 2 }}>{t('community.noPapers')}</Typography>}
    {data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
    <CommentPanel key={`comments-${data.system_key}`} target={{ system_key: data.system_key }} />
  </Box>
}
export default function SystemCommunityPage() { const { systemKey = '' } = useParams(); return <SystemDetailView key={systemKey} systemKey={systemKey} /> }
