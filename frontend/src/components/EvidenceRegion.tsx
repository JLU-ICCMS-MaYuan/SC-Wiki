import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Dialog, DialogContent, DialogTitle, IconButton, LinearProgress, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import type { EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'

type Crop = { image: string; highlights: number[][]; width?: number; height?: number; pdf_page?: number; source_raster_dpi?: number }
type Region = { status: string; image?: string; region?: number[]; regions?: number[][]; crops?: Crop[]; dpi?: number; pdf_page?: number; printed_page?: number; message?: string; parser?: { name: string; mode: string } }

function CropView({ crop, label, onClick, onFailure }: { crop: Crop; label: string; onClick: () => void; onFailure?: () => void }) {
  const { t } = useLanguage()
  const [failed, setFailed] = useState(false)
  useEffect(() => { setFailed(false) }, [crop.image])
  if (failed) return onFailure ? null : <Alert severity="warning">{t('evidence.regionUnavailable')}</Alert>
  return <Box component="button" type="button" onClick={onClick} aria-label={label} sx={{ display: 'block', position: 'relative', p: 0, border: 0, bgcolor: 'transparent', cursor: 'zoom-in', width: crop.width || 'max-content' }}>
    <Box component="img" src={crop.image} alt={t('evidence.regionImage')} onError={() => { setFailed(true); onFailure?.() }} sx={{ display: 'block', maxWidth: 'none', width: crop.width ? `${crop.width}px` : 'auto', height: crop.height ? `${crop.height}px` : 'auto' }} />
    {crop.highlights.map((region, index) => <Box key={index} aria-hidden sx={{ position: 'absolute', pointerEvents: 'none', border: '2px solid #d32f2f', boxSizing: 'border-box',
      left: `${region[0] * 100}%`, top: `${region[1] * 100}%`, width: `${region[2] * 100}%`, height: `${region[3] * 100}%` }} />)}
  </Box>
}

// 直接按PDF块定位时没有RAG分段编号，不编造chunk_index。
export function EvidenceRegion({ target, source, hideQuote = false }: { target?: EvidenceTarget; source: Omit<EvidenceSource, 'chunk_index'> & { chunk_index?: number }; hideQuote?: boolean }) {
  const { t } = useLanguage()
  const [result, setResult] = useState<Region | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [expandedCrop, setExpandedCrop] = useState<number | null>(null)
  const generation = useRef(0)
  useEffect(() => {
    generation.current++
    setResult(null); setBusy(false); setError(false); setExpandedCrop(null)
    return () => { generation.current++ }
  }, [target?.target, target?.target_id, source.file_id, source.page_start, source.page_end, source.chunk_index, source.quote, source.block_id, source.evidence_kind])
  const open = async () => {
    if (!target || (!source.quote && !source.block_id) || busy) return
    const current = generation.current
    setBusy(true); setError(false); setResult(null); setExpandedCrop(null)
    try {
      const data = await api.post<Region>('/api/rag/evidence/region', { ...target, file_id: source.file_id, pdf_page: source.page_start, quote: source.quote, block_id: source.block_id })
      if (generation.current === current) setResult(data)
    } catch {
      if (generation.current === current) setError(true)
    } finally {
      if (generation.current === current) setBusy(false)
    }
  }
  useEffect(() => {
    if (source.evidence_kind === 'pdf_image' && source.block_id) void open()
  }, [source.evidence_kind, source.block_id, source.file_id, source.page_start, target?.target, target?.target_id])
  const page = result?.pdf_page || source.page_start
  const highlights = result?.regions?.length ? result.regions : result?.region ? [result.region] : []
  const crops = result?.crops?.length ? result.crops : result?.image && highlights.length ? [{ image: result.image, highlights }] : []
  const unavailable = result?.status === 'legacy_text' ? t('evidence.regionLegacyNoLocator')
    : result?.status === 'unlocated' ? t('evidence.regionQuoteUnlocated')
      : result?.status === 'render_unavailable' ? t('evidence.regionRenderFailed')
        : t('evidence.regionUnavailable')
  const quote = hideQuote ? '' : source.quote || source.content || ''
  return <Box sx={{ my: 1 }}>
    <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{source.source_name || source.file_id} · {page ? t('evidence.page', { page }) : t('evidence.pageUnknown')}{quote ? `：${quote.length > 500 ? quote.slice(0, 360) + '…' : quote}` : ''}</Typography>
    {quote.length > 500 && <Box component="details" sx={{ my: 1 }}><Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>{t('evidence.fullQuote')}</Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{quote}</Typography>
    </Box>}
    {target && (source.quote || source.block_id) && source.evidence_kind !== 'pdf_image' && <Button disabled={busy} onClick={() => void open()}>{t('evidence.viewRegion')}</Button>}
    {busy && <LinearProgress aria-label={t('evidence.regionLoading')} />}
    {error && <Alert severity="warning">{t('evidence.regionUnavailable')}</Alert>}
    {source.evidence_kind === 'pdf_image' && (error || result && result.status !== 'located') && <Button disabled={busy} onClick={() => void open()}>{t('evidence.retryRegion')}</Button>}
    {result && result.status !== 'located' && <Alert severity="info">{unavailable}</Alert>}
    {crops.length > 0 && <>
      <Typography>{result?.parser?.mode === 'legacy_text' ? t('evidence.legacyTextLocator') : result?.parser?.name}{result?.printed_page != null ? ` · ${t('evidence.printedPage', { page: result.printed_page })}` : ''}{result?.dpi ? ` · ${result.dpi} DPI` : ''}</Typography>
      <Typography variant="caption" color="text.secondary">{t('evidence.scrollRegionHint')}</Typography>
      {crops.map((crop, index) => <Box key={index} sx={{ my: 1 }}>
        {crop.pdf_page && crops.length > 1 && <Typography variant="caption">{t('evidence.page', { page: crop.pdf_page })}</Typography>}
        {crop.source_raster_dpi && <Alert severity="warning">{t('evidence.sourceRasterLowDpi', { dpi: crop.source_raster_dpi })}</Alert>}
        <Box sx={{ maxHeight: 440, overflow: 'auto', border: 1, borderColor: 'divider' }}>
          <CropView crop={crop} label={t('evidence.expandRegion')} onClick={() => setExpandedCrop(index)} onFailure={() => setError(true)} />
        </Box>
      </Box>)}
    </>}
    <Dialog open={expandedCrop !== null} onClose={() => setExpandedCrop(null)} maxWidth="xl" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>{source.source_name || source.file_id} · {(expandedCrop !== null && crops[expandedCrop]?.pdf_page || page) ? t('evidence.page', { page: (expandedCrop !== null && crops[expandedCrop]?.pdf_page) || page! }) : t('evidence.pageUnknown')}
        <IconButton aria-label={t('evidence.collapseRegion')} onClick={() => setExpandedCrop(null)}><CloseIcon /></IconButton>
      </DialogTitle>
      <DialogContent sx={{ overflow: 'auto', maxHeight: '80vh' }}>
        {expandedCrop !== null && crops[expandedCrop] && <CropView crop={crops[expandedCrop]} label={t('evidence.collapseRegion')} onClick={() => setExpandedCrop(null)} />}
      </DialogContent>
    </Dialog>
  </Box>
}
