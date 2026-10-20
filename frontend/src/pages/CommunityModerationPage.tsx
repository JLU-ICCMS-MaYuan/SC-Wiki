import React, { useState } from 'react'
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { CommunityEntry, CommunityList, useCommunityLoad } from '../lib/community'
import EntryCard from '../components/community/EntryCard'

export default function CommunityModerationPage() {
  const { t } = useLanguage(); const { user } = useAuth(); const [status, setStatus] = useState('hidden'), [offset, setOffset] = useState(0)
  const list = useCommunityLoad<CommunityList<CommunityEntry>>(user?.role === 'superadmin' ? `/moderation/entries?status=${status}&offset=${offset}` : null)
  if (user?.role !== 'superadmin') return <Alert severity="info">{t('community.readOnly')}</Alert>
  return <Box><Typography variant="h1">{t('community.moderation')}</Typography><TextField select label={t('community.moderation')} value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }} sx={{ my: 2, minWidth: 200 }}><MenuItem value="hidden">{t('community.hidden')}</MenuItem><MenuItem value="visible">{t('community.visible')}</MenuItem></TextField>
    {list.error && <Alert severity="error">{t(list.error)}</Alert>}{list.data?.items.map(entry => <EntryCard key={entry.id} entry={entry} reload={list.reload} />)}
    {list.data?.items.length === 0 && <Typography>{t('community.empty')}</Typography>}
    {list.data && list.data.total > 20 && <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => v - 20)}>{t('community.previous')}</Button><Button disabled={offset + 20 >= list.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack>}
  </Box>
}
