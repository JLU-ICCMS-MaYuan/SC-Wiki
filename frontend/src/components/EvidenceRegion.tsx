import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Dialog, DialogContent, DialogTitle, IconButton, LinearProgress, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import type { EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'
import SnapshotFileButton from './SnapshotFileButton'

type Crop = { image: string; highlights: number[][]; width?: number; height?: number; pdf_page?: number; source_raster_dpi?: number }
type Region = { status: string; image?: string; region?: number[]; regions?: number[][]; crops?: Crop[]; dpi?: number; pdf_page?: number; printed_page?: number; message?: string; parser?: { name: string; mode: string }; context_text?: string; text_locator?: { char_interval: [number, number] | null; match_kind: string; text_sha256: string } }

function CropView({ crop, label, onClick, onFailure, marked = true }: { crop: Crop; label: string; onClick: () => void; onFailure?: () => void; marked?: boolean }) {
  const { t } = useLanguage()
  const [failed, setFailed] = useState(false)
  useEffect(() => { setFailed(false) }, [crop.image])
  if (failed) return onFailure ? null : <Alert severity="warning">{t('evidence.regionUnavailable')}</Alert>
  return <Box component="button" type="button" onClick={onClick} aria-label={label} sx={{ display: 'block', position: 'relative', p: 0, border: 0, bgcolor: 'transparent', cursor: 'zoom-in', width: crop.width || 'max-content' }}>
    <Box component="img" src={crop.image} alt={t('evidence.regionImage')} onError={() => { setFailed(true); onFailure?.() }} sx={{ display: 'block', maxWidth: 'none', width: crop.width ? `${crop.width}px` : 'auto', height: crop.height ? `${crop.height}px` : 'auto' }} />
    {marked && crop.highlights.map((region, index) => <Box key={index} aria-hidden sx={{ position: 'absolute', pointerEvents: 'none', border: '2px solid #d32f2f', boxSizing: 'border-box',
      left: `${region[0] * 100}%`, top: `${region[1] * 100}%`, width: `${region[2] * 100}%`, height: `${region[3] * 100}%` }} />)}
  </Box>
}

// 直接按PDF块定位时没有RAG分段编号，不编造chunk_index。
export function EvidenceRegion({ target, source, hideQuote = false, plain = false }: { target?: EvidenceTarget; source: Omit<EvidenceSource, 'chunk_index'> & { chunk_index?: number }; hideQuote?: boolean; plain?: boolean }) {
  const { t, lang } = useLanguage()
  const [marked, setMarked] = useState(true)
  const [result, setResult] = useState<Region | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [expandedCrop, setExpandedCrop] = useState<number | null>(null)
  const generation = useRef(0)
  useEffect(() => {
    generation.current++
    setResult(null); setBusy(false); setError(false); setExpandedCrop(null); setMarked(true)
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
  if (source.origin_kind === 'external_bibliography' && source.source_url?.startsWith('https://api.crossref.org/works/')) {
    let citation = quote
    try {
      const data = JSON.parse(source.quote || source.content || '{}')
      citation = [data.title?.join('；'), data['container-title']?.join('；'),
        data.volume && `${data.volume} 卷`, data.issue && `${data.issue} 期`,
        data.page || data['article-number'], data.DOI].filter(Boolean).join(' · ')
    } catch { /* 旧文字来源仍直接可读。 */ }
    return <Box sx={{ my: 1 }}>
      <Typography component="a" href={source.source_url} target="_blank" rel="noopener noreferrer">Crossref 正式题录（外部来源）</Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{citation}</Typography>
    </Box>
  }
  return <Box sx={{ my: 1 }}>
    {source.snapshot_file_url&&<SnapshotFileButton url={source.snapshot_file_url} name={source.source_name||source.file_id}/>}
    <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{source.source_name || source.file_id} · {page ? t('evidence.page', { page }) : t('evidence.pageUnknown')}{quote ? `：${!plain && quote.length > 500 ? quote.slice(0, 360) + '…' : quote}` : ''}</Typography>
    {!plain && quote.length > 500 && <Box component="details" sx={{ my: 1 }}><Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>{t('evidence.fullQuote')}</Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{quote}</Typography>
    </Box>}
    {target && (source.quote || source.block_id) && source.evidence_kind !== 'pdf_image' && <Button disabled={busy} onClick={() => void open()}>{t('evidence.viewRegion')}</Button>}
    {busy && <LinearProgress aria-label={t('evidence.regionLoading')} />}
    {error && <Alert severity="warning">{t('evidence.regionUnavailable')}</Alert>}
    {source.evidence_kind === 'pdf_image' && (error || result && result.status !== 'located') && <Button disabled={busy} onClick={() => void open()}>{t('evidence.retryRegion')}</Button>}
    {result && result.status !== 'located' && <Typography role="status" color="text.secondary">{unavailable}</Typography>}
    {result && (result.context_text || crops.length > 0) && <Button aria-pressed={marked} onClick={() => setMarked(value => !value)}>
      {lang === 'zh' ? (marked ? '隐藏来源标记' : '显示来源标记') : (marked ? 'Hide source highlights' : 'Show source highlights')}
    </Button>}
    {result?.context_text && <Typography data-source-context sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{(() => {
      const text = result.context_text!, span = result.text_locator?.char_interval
      // Python区间按Unicode字符计数；不能直接套用JavaScript的UTF-16索引。
      const characters = Array.from(text)
      return marked && span ? <>{characters.slice(0, span[0]).join('')}<mark>{characters.slice(span[0], span[1]).join('')}</mark>{characters.slice(span[1]).join('')}</> : text
    })()}</Typography>}
    {crops.length > 0 && <>
      {!plain && <Typography>{result?.parser?.mode === 'legacy_text' ? t('evidence.legacyTextLocator') : result?.parser?.name}{result?.printed_page != null ? ` · ${t('evidence.printedPage', { page: result.printed_page })}` : ''}{result?.dpi ? ` · ${result.dpi} DPI` : ''}</Typography>}
      {!plain && <Typography variant="caption" color="text.secondary">{t('evidence.scrollRegionHint')}</Typography>}
      {crops.map((crop, index) => <Box key={index} sx={{ my: 1 }}>
        {crop.pdf_page && crops.length > 1 && <Typography variant="caption">{t('evidence.page', { page: crop.pdf_page })}</Typography>}
        {crop.source_raster_dpi && <Alert severity="warning">{t('evidence.sourceRasterLowDpi', { dpi: crop.source_raster_dpi })}</Alert>}
        <Box sx={{ maxHeight: 440, overflow: 'auto', border: 1, borderColor: 'divider' }}>
          <CropView crop={crop} marked={marked} label={t('evidence.expandRegion')} onClick={() => setExpandedCrop(index)} onFailure={() => setError(true)} />
        </Box>
      </Box>)}
    </>}
    <Dialog open={expandedCrop !== null} onClose={() => setExpandedCrop(null)} maxWidth="xl" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>{source.source_name || source.file_id} · {(expandedCrop !== null && crops[expandedCrop]?.pdf_page || page) ? t('evidence.page', { page: (expandedCrop !== null && crops[expandedCrop]?.pdf_page) || page! }) : t('evidence.pageUnknown')}
        <IconButton aria-label={t('evidence.collapseRegion')} onClick={() => setExpandedCrop(null)}><CloseIcon /></IconButton>
      </DialogTitle>
      <DialogContent sx={{ overflow: 'auto', maxHeight: '80vh' }}>
        {expandedCrop !== null && crops[expandedCrop] && <CropView crop={crops[expandedCrop]} marked={marked} label={t('evidence.collapseRegion')} onClick={() => setExpandedCrop(null)} />}
      </DialogContent>
    </Dialog>
  </Box>
}
