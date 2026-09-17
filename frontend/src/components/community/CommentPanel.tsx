import React, { useEffect, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Stack, Typography } from '@mui/material'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityList, CommunityTarget, focusedEntry, targetQuery, useCommunityLoad } from '../../lib/community'
import CommunityComposer from './CommunityComposer'
import EntryCard from './EntryCard'

export default function CommentPanel({ target }: { target: CommunityTarget }) {
  const { t } = useLanguage(); const [offset, setOffset] = useState<number | undefined>(), [reply, setReply] = useState<number | null>(null)
  const [focus, setFocus] = useState(focusedEntry())
  const { data, error, loading, reload } = useCommunityLoad<CommunityList<CommunityEntry>>(`/entries?kind=comment&${targetQuery(target)}${offset == null ? '' : `&offset=${offset}`}&limit=20${focus ? `&focus_id=${focus}` : ''}`)
  const pageOffset = data?.offset ?? offset ?? 0
  const entries = [...(data?.context || []), ...(data?.items || [])].sort((a, b) => ((a.parent_id || a.id) - (b.parent_id || b.id)) || a.id - b.id)
  useEffect(() => { if (data && focus) document.getElementById(`entry-${focus}`)?.scrollIntoView?.({ block: 'center' }) }, [data, focus])
  const create = async (body: string, replyTo?: number) => {
    const entry = await api.post<CommunityEntry>(`${COMMUNITY_API}/entries`, { ...target, kind: 'comment', body, ...(replyTo ? { reply_to_id: replyTo } : {}) })
    setReply(null); setOffset(undefined); setFocus(entry.id); reload()
  }
  return <Box sx={{ mt: 3 }}>
    <Typography variant="h2">{t('community.comments')}</Typography>
    {focus && <Alert severity="info" action={<Button onClick={() => { setFocus(undefined); setOffset(0) }}>{t('community.showAll')}</Button>}>{t('community.focused')}</Alert>}
    {error && <Alert severity="error" action={<Button onClick={reload}>{t('community.retry')}</Button>}>{t(error)}</Alert>}
    {(!error || data) && <>
      <CommunityComposer key={targetQuery(target)} onSubmit={body => create(body)} label={t('community.comment')} />
      {loading ? <CircularProgress size={24} /> : !entries.length ? <Typography color="text.secondary">{t('community.empty')}</Typography> : entries.map(entry => <Box key={entry.id} sx={{ pl: entry.parent_id ? { xs: 1, sm: 3 } : 0 }}>
        <EntryCard entry={entry} reload={reload} onReply={() => setReply(reply === entry.id ? null : entry.id)}>
          {reply === entry.id && <CommunityComposer key={entry.id} onSubmit={body => create(body, entry.id)} onCancel={() => setReply(null)} label={t('community.replyTo', { id: entry.id })} />}
        </EntryCard>
      </Box>)}
      {data && data.total > 20 && <Stack direction="row" spacing={2} sx={{ mt: 2 }}><Button disabled={pageOffset === 0} onClick={() => setOffset(Math.max(0, pageOffset - 20))}>{t('community.previous')}</Button><Typography sx={{ alignSelf: 'center' }}>{t('community.total', { count: data.total })}</Typography><Button disabled={pageOffset + 20 >= data.total} onClick={() => setOffset(pageOffset + 20)}>{t('community.next')}</Button></Stack>}
    </>}
  </Box>
}
