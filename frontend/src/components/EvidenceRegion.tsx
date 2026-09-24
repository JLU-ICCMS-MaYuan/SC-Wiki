import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, LinearProgress, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import type { EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'

type Region = { status: string; image?: string; region?: number[]; pdf_page?: number; printed_page?: number; message?: string; parser?: { name: string; mode: string } }

export function EvidenceRegion({ target, source }: { target?: EvidenceTarget; source: EvidenceSource }) {
  const { t } = useLanguage()
  const [result, setResult] = useState<Region | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const generation = useRef(0)
  useEffect(() => {
    generation.current++
    setResult(null); setBusy(false); setError(false)
    return () => { generation.current++ }
  }, [target?.target, target?.target_id, source.file_id, source.page_start, source.quote, source.block_id])
  const open = async () => {
    if (!target || !source.quote || busy) return
    const current = generation.current
    setBusy(true); setError(false)
    try {
      const data = await api.post<Region>('/api/rag/evidence/region', { ...target, file_id: source.file_id, pdf_page: source.page_start, quote: source.quote, block_id: source.block_id })
      if (generation.current === current) setResult(data)
    } catch {
      if (generation.current === current) setError(true)
    } finally {
      if (generation.current === current) setBusy(false)
    }
  }
  return <Box sx={{ my: 1 }}>
    <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{source.source_name || source.file_id} · {source.page_start ? t('evidence.page', { page: source.page_start }) : t('evidence.pageUnknown')}：{source.quote || source.content}</Typography>
    {target && source.quote && <Button disabled={busy} onClick={() => void open()}>{t('evidence.viewRegion')}</Button>}
    {busy && <LinearProgress aria-label={t('evidence.regionLoading')} />}
    {error && <Alert severity="warning">{t('evidence.regionUnavailable')}</Alert>}
    {result && result.status !== 'located' && <Alert severity="info">{t('evidence.regionUnavailable')}</Alert>}
    {result?.image && result.region && <>
      <Typography>{result.parser?.name} · {result.parser?.mode}{result.printed_page != null ? ` · ${t('evidence.printedPage', { page: result.printed_page })}` : ''}</Typography>
      <Box sx={{ position: 'relative', width: '100%' }}>
        <Box component="img" src={result.image} alt={t('evidence.regionImage')} sx={{ display: 'block', width: '100%' }} onError={() => setError(true)} />
        <Box aria-hidden sx={{ position: 'absolute', pointerEvents: 'none', border: '2px solid #d32f2f', boxSizing: 'border-box',
          left: `${result.region[0] * 100}%`, top: `${result.region[1] * 100}%`, width: `${result.region[2] * 100}%`, height: `${result.region[3] * 100}%` }} />
      </Box>
    </>}
  </Box>
}
