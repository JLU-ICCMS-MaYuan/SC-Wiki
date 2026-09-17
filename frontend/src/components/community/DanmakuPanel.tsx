import React, { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, FormControlLabel, Stack, Switch, Typography, useMediaQuery } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { api } from '../../lib/api'
import { COMMUNITY_API, CommunityEntry, CommunityList, CommunityTarget, communityErrorKey, targetQuery, useCommunityLoad } from '../../lib/community'
import CommunityComposer from './CommunityComposer'
import EntryCard from './EntryCard'

interface RollingQueue { playing: Array<{ entry: CommunityEntry; lane: number }>; waiting: CommunityEntry[] }
function fillLanes(queue: RollingQueue): RollingQueue {
  const playing = [...queue.playing], waiting = [...queue.waiting]
  for (let lane = 0; lane < 6 && waiting.length; lane++) {
    if (!playing.some(item => item.lane === lane)) playing.push({ entry: waiting.shift()!, lane })
  }
  return { playing, waiting }
}

export default function DanmakuPanel({ target }: { target: CommunityTarget }) {
  const { t } = useLanguage(); const { token } = useAuth(); const reduceMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const [enabled, setEnabled] = useState(true), [history, setHistory] = useState(false), [offset, setOffset] = useState(0)
  const [queue, setQueue] = useState<RollingQueue>({ playing: [], waiting: [] }), [error, setError] = useState(''), [tick, setTick] = useState(0)
  const seen = useRef(new Set<number>())
  const query = targetQuery(target)
  const historyState = useCommunityLoad<CommunityList<CommunityEntry>>(history ? `/entries?kind=danmaku&${query}&offset=${offset}&limit=20` : null)
  useEffect(() => {
    setQueue({ playing: [], waiting: [] }); setError(''); seen.current.clear()
  }, [enabled, query, token])
  useEffect(() => {
    if (!enabled) return
    let stopped = false, pending = false
    const controller = new AbortController()
    const refresh = async () => {
      if (stopped || pending || document.hidden) return
      pending = true
      try {
        const result = await api.get<CommunityList<CommunityEntry>>(`${COMMUNITY_API}/entries?kind=danmaku&${query}&limit=50`, { signal: controller.signal })
        if (stopped) return
        const visible = new Set(result.items.map(item => item.id))
        const fresh = result.items.filter(item => !seen.current.has(item.id)).reverse()
        // 已见 ID 在当前目标会话内去重；被隐藏的弹幕从播放及等待队列移除。
        for (const item of result.items) seen.current.add(item.id)
        setQueue(previous => fillLanes({ playing: previous.playing.filter(item => visible.has(item.entry.id)), waiting: [...previous.waiting.filter(item => visible.has(item.id)), ...fresh] })); setError('')
      } catch (reason) {
        if (!stopped) {
          if ([401, 403, 404].includes((reason as { status?: number })?.status || 0)) setQueue({ playing: [], waiting: [] })
          setError(communityErrorKey(reason))
        }
      } finally { pending = false }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    document.addEventListener('visibilitychange', refresh)
    return () => { stopped = true; controller.abort(); window.clearInterval(timer); document.removeEventListener('visibilitychange', refresh) }
  }, [enabled, query, token, tick])
  useEffect(() => {
    if (!enabled || !reduceMotion) return
    const timer = window.setInterval(() => { if (!document.hidden) setQueue(previous => previous.waiting.length ? fillLanes({ playing: [], waiting: previous.waiting }) : previous) }, 12000)
    return () => window.clearInterval(timer)
  }, [enabled, reduceMotion])
  const refresh = () => { setTick(v => v + 1); historyState.reload() }
  return <Box component="section" aria-label={t('community.danmaku')} sx={{ my: 3, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
    <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap"><Typography variant="h2">{t('community.danmaku')}</Typography><FormControlLabel control={<Switch checked={enabled} onChange={(_, value) => setEnabled(value)} />} label={t('community.animation')} /></Stack>
    <Typography variant="caption" color="text.secondary">{t('community.danmakuHint')}</Typography>
    {error && <Alert severity="error" action={<Button onClick={refresh}>{t('community.retry')}</Button>}>{t(error)}</Alert>}
    {enabled && <Box data-testid="danmaku-stage" sx={{ position: 'relative', overflow: 'hidden', minHeight: 156, my: 1, bgcolor: 'action.hover', borderRadius: 2, '@keyframes community-float': { from: { left: '100%', transform: 'translateX(0)' }, to: { left: 0, transform: 'translateX(-100%)' } } }}>
      {queue.playing.map(({ entry: message, lane }) => <Typography key={message.id} data-entry-id={message.id} onAnimationEnd={() => setQueue(previous => fillLanes({ playing: previous.playing.filter(item => item.entry.id !== message.id), waiting: previous.waiting }))} sx={reduceMotion ? { px: 1, py: 0.25, overflowWrap: 'anywhere' } : { position: 'absolute', whiteSpace: 'nowrap', top: lane * 24 + 4, animation: 'community-float 12s linear forwards', fontSize: 14 }}>{message.body}</Typography>)}
    </Box>}
    <CommunityComposer maxLength={120} onSubmit={async body => { await api.post(`${COMMUNITY_API}/entries`, { ...target, kind: 'danmaku', body }); refresh() }} />
    <Button onClick={() => setHistory(value => !value)}>{t('community.history')}</Button>
    {history && <><Button onClick={historyState.reload}>{t('community.refresh')}</Button>{historyState.error && <Alert severity="error">{t(historyState.error)}</Alert>}{historyState.data?.items.map(entry => <EntryCard key={entry.id} entry={entry} reload={refresh} />)}{historyState.data?.items.length === 0 && <Typography>{t('community.empty')}</Typography>}
      <Stack direction="row"><Button disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 20))}>{t('community.previous')}</Button><Button disabled={!historyState.data || offset + 20 >= historyState.data.total} onClick={() => setOffset(v => v + 20)}>{t('community.next')}</Button></Stack></>}
  </Box>
}
