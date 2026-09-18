import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import { COMMUNITY_API, CommunityAuthor, CommunityList, communityErrorKey, notifyCommunityChanged, useCommunityLoad } from '../lib/community'

interface Notice { id: number; kind: string; actor: CommunityAuthor; url: string; read_at: string | null }
export default function CommunityNotificationsPage() {
  const { t } = useLanguage(); const navigate = useNavigate(); const [offset, setOffset] = useState(0), [error, setError] = useState('')
  const list = useCommunityLoad<CommunityList<Notice>>(`/notifications?offset=${offset}`)
  const read = async (id?: number, url?: string) => {
    try { await api.patch(`${COMMUNITY_API}/notifications/read`, id ? { id } : {}); notifyCommunityChanged(); if (url) navigate(url); else list.reload() } catch (e) { setError(communityErrorKey(e)) }
  }
  return <Box><Stack direction="row" justifyContent="space-between"><Typography variant="h1">{t('community.notifications')}</Typography><Button onClick={() => void read()}>{t('community.markAllRead')}</Button></Stack>
    {(error || list.error) && <Alert severity="error" action={<Button onClick={list.reload}>{t('community.retry')}</Button>}>{t(error || list.error)}</Alert>}{list.loading && <CircularProgress />}
    {list.data?.items.map(n => <Stack key={n.id} direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems={{ sm: 'center' }} sx={{ py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
      {!n.read_at && <Chip size="small" color="primary" label={t('community.unread', { count: 1 })} />}<Typography sx={{ flex: 1 }}>{n.actor.username || t('community.deactivated')} · {t(n.kind === 'answer' ? 'community.noticeAnswer' : n.kind === 'reply' ? 'community.noticeReply' : 'community.noticeComment')}</Typography><Button onClick={() => void read(n.id, n.url)}>{t('community.open')}</Button>{!n.read_at && <Button onClick={() => void read(n.id)}>{t('community.markRead')}</Button>}
    </Stack>)}
    {list.data?.items.length === 0 && <Typography sx={{ my: 3 }}>{t('community.empty')}</Typography>}
    {list.data && list.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= list.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </Box>
}
