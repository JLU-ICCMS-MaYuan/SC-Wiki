import React, { useEffect, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Stack, Typography } from '@mui/material'
import { useLanguage } from '../../context/LanguageContext'
import { CommunityEntry, CommunityList, CommunityTarget, focusedEntry, targetQuery, useCommunityLoad } from '../../lib/community'
import EntryCard from './EntryCard'

export default function CommentPanel({ target }: { target: CommunityTarget }) {
  const { t } = useLanguage(); const [offset, setOffset] = useState<number | undefined>()
  const [focus, setFocus] = useState(focusedEntry())
  const { data, error, loading, reload } = useCommunityLoad<CommunityList<CommunityEntry>>(`/entries?kind=comment&${targetQuery(target)}${offset == null ? '' : `&offset=${offset}`}&limit=20${focus ? `&focus_id=${focus}` : ''}`)
  const pageOffset = data?.offset ?? offset ?? 0
  const entries = [...(data?.context || []), ...(data?.items || [])].sort((a, b) => ((a.parent_id || a.id) - (b.parent_id || b.id)) || a.id - b.id)
  useEffect(() => { if (data && focus) document.getElementById(`entry-${focus}`)?.scrollIntoView?.({ block: 'center' }) }, [data, focus])
  return <Box sx={{ mt: 3 }}>
    <Typography variant="h2">{t('community.comments')}</Typography>
    {focus && <Alert severity="info" action={<Button onClick={() => { setFocus(undefined); setOffset(0) }}>{t('community.showAll')}</Button>}>{t('community.focused')}</Alert>}
    {error && <Alert severity="error" action={<Button onClick={reload}>{t('community.retry')}</Button>}>{t(error)}</Alert>}
    {(!error || data) && <>
      <Typography variant="caption" color="text.secondary">{t('community.readOnly')}</Typography>
      {loading ? <CircularProgress size={24} /> : !entries.length ? <Typography color="text.secondary">{t('community.empty')}</Typography> : entries.map(entry => <Box key={entry.id} sx={{ pl: entry.parent_id ? { xs: 1, sm: 3 } : 0 }}>
        <EntryCard entry={entry} reload={reload} />
      </Box>)}
      {data && data.total > 20 && <Stack direction="row" spacing={2} sx={{ mt: 2 }}><Button disabled={pageOffset === 0} onClick={() => setOffset(Math.max(0, pageOffset - 20))}>{t('community.previous')}</Button><Typography sx={{ alignSelf: 'center' }}>{t('community.total', { count: data.total })}</Typography><Button disabled={pageOffset + 20 >= data.total} onClick={() => setOffset(pageOffset + 20)}>{t('community.next')}</Button></Stack>}
    </>}
  </Box>
}
