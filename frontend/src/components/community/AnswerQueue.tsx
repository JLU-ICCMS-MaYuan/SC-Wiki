import React, { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, Stack, Typography } from '@mui/material'
import { api } from '../../lib/api'
import { useLanguage } from '../../context/LanguageContext'
import { COMMUNITY_API, communityErrorKey, useCommunityLoad } from '../../lib/community'

interface Model { key: string; name: string; model: string }
interface Request { id: number; sequence: number; model_name: string; model: string; state: string; error: string }
export default function AnswerQueue({ questionId, onChanged }: { questionId: number; onChanged: () => void }) {
  const { t } = useLanguage()
  const options = useCommunityLoad<{ items: Model[] }>('/ai/models')
  const queue = useCommunityLoad<{ items: Request[] }>(`/ai/questions/${questionId}/queue`)
  const [selected, setSelected] = useState<string[]>([]), [busy, setBusy] = useState(false), [error, setError] = useState(''), [showAll, setShowAll] = useState(false)
  const initialized = useRef(false), submitting = useRef(false)
  const pending = useRef<{ key: string; id: string } | null>(null)
  useEffect(() => {
    if (!options.data) return
    const keys = options.data.items.map(item => item.key)
    const wasInitialized = initialized.current
    initialized.current = true
    setSelected(value => wasInitialized ? value.filter(key => keys.includes(key)) : keys)
  }, [options.data])
  const active = queue.data?.items.some(item => ['queued', 'running'].includes(item.state))
  useEffect(() => { if (!active) return; const timer = window.setInterval(() => { queue.reload(); onChanged() }, 2500); return () => window.clearInterval(timer) }, [active, onChanged, queue.reload])
  const act = async (retry?: number) => {
    if (submitting.current || (retry === undefined && !selected.length)) return
    const key = retry === undefined ? JSON.stringify(selected) : `retry-${retry}`
    if (!pending.current || pending.current.key !== key) pending.current = { key, id: crypto.randomUUID() }
    submitting.current = true; setBusy(true); setError('')
    try {
      await api.post(retry === undefined ? `${COMMUNITY_API}/ai/questions/${questionId}/answers/batch` : `${COMMUNITY_API}/ai/answer-requests/${retry}/retry`, { request_id: pending.current.id, ...(retry === undefined ? { model_keys: selected } : {}) })
      pending.current = null; queue.reload(); onChanged()
    } catch (e) { setError(communityErrorKey(e)) } finally { submitting.current = false; setBusy(false) }
  }
  const visibleRequests = showAll ? queue.data?.items : queue.data?.items.filter((item, index, all) => ['queued', 'running'].includes(item.state) || index >= all.length - 3)
  const label = (item: Model) => /deepseek/i.test(`${item.name} ${item.model}`) ? 'DeepSeek' : /openai|gpt/i.test(`${item.name} ${item.model}`) ? 'OpenAI' : item.name
  const orderedNames = selected.map(key => options.data?.items.find(item => item.key === key)).filter((item): item is Model => !!item).map(label)
  return <Box sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 2, mb: 3 }}>
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>{t('community.chooseMultipleModels')}</Typography>
    <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
      <Stack direction="row" gap={1} flexWrap="wrap" role="group" aria-label={t('community.chooseMultipleModels')}>
        {options.data?.items.map(item => {
          const checked = selected.includes(item.key), name = label(item)
          const color = name === 'DeepSeek' ? '#4d6bfe' : name === 'OpenAI' ? '#138671' : '#6855b9'
          return <Button key={item.key} size="small" variant="outlined" aria-pressed={checked} title={item.model} disabled={busy} onClick={() => setSelected(value => value.includes(item.key) ? value.filter(key => key !== item.key) : [...value, item.key])} sx={{ textTransform: 'none', color: checked ? color : 'text.secondary', borderColor: checked ? color : 'divider', bgcolor: checked ? `${color}0b` : 'transparent', borderRadius: 1.5, px: 1.2, minHeight: 36 }}>
            <Box component="span" aria-hidden="true" sx={{ display: 'inline-grid', placeItems: 'center', width: 17, height: 17, bgcolor: color, color: '#fff', fontSize: 10, fontWeight: 800, borderRadius: .7, mr: .75 }}>{name[0]}</Box>{name}{options.data!.items.filter(other => label(other) === name).length > 1 ? ` · ${item.model}` : ''}<Box component="span" aria-hidden="true" sx={{ ml: .8 }}>{checked ? '✓' : '+'}</Box>
          </Button>
        })}
      </Stack>
      <Button variant="contained" disabled={busy || !selected.length || !!options.error} onClick={() => void act()} sx={{ minHeight: 36, borderRadius: 1.5, fontSize: 12, px: 1.5 }}>{t('community.generateAnswer')} ({selected.length})</Button>
    </Stack>
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{selected.length ? t('community.modelSequence', { names: orderedNames.join(' → ') }) : t('community.selectAtLeastOne')}</Typography>
    {options.error && <Alert severity="error" sx={{ mt: 1 }} action={<Button onClick={options.reload}>{t('community.retry')}</Button>}>{t(options.error)}</Alert>}
    {queue.error && <Alert severity="error" sx={{ mt: 1 }}>{t(queue.error)}</Alert>}
    {error && <Alert severity="error" sx={{ mt: 1 }}>{t(error)}</Alert>}
    {!!queue.data?.items.length && <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
      <Typography variant="caption" color="text.secondary">{t('community.answerQueue')}</Typography>
      {visibleRequests?.map(item => <Stack key={item.id} direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: .75 }}>
        <Typography variant="caption" color="text.secondary">#{item.sequence}</Typography><Typography variant="caption">{item.model_name} · {item.model}</Typography>
        <Chip size="small" label={t(`community.states.${item.state}`)} color={item.state === 'running' ? 'primary' : item.state === 'failed' ? 'error' : 'default'} sx={{ height: 22, fontSize: 10 }} />
        {item.error && <Typography variant="caption" color="error">{t(`community.jobErrors.${item.error}`)}</Typography>}
        {item.state === 'failed' && <Button size="small" disabled={busy} onClick={() => void act(item.id)}>{t('community.retryAtEnd')}</Button>}
      </Stack>)}
      {queue.data.items.length > 3 && <Button size="small" onClick={() => setShowAll(value => !value)}>{t(showAll ? 'community.collapseAnswer' : 'community.showAll')}</Button>}
    </Box>}
  </Box>
}
