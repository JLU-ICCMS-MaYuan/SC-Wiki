import React, { useEffect, useState } from 'react'
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip,
  LinearProgress, Tab, Tabs, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import { api } from '../lib/api'
import { CitationExtractionStatus, PROCESSING_STAGES, UploadDraft, unwrapData, type WorkflowAssessment, type ParsingWorkflowBinding } from '../lib/paperProcessing'
import { useLanguage } from '../context/LanguageContext'
import UploadTaskEditor from './UploadTaskEditor'

interface ChunkDetail {
  chunk_id: string
  filename?: string
  file_role?: string
  section?: string
  page_start?: number | null
  page_end?: number | null
  status: string
  error?: string | null
  result?: Record<string, unknown>
}

interface ParsingDetail {
  workflow_policy?: string
  _parsing_workflow?: ParsingWorkflowBinding
  workflow_assessment?: WorkflowAssessment
  status: string
  stage: string
  processing_error?: string | null
  failed_stage?: string | null
  files?: Array<{
    file_id: string
    role: string
    original_filename: string
    extraction_status?: string
    error?: string | null
  }>
  chunks: ChunkDetail[]
  pending_visual_regions?: Array<{ file_id: string; pdf_page: number; block_id: string }>
  partial_draft?: UploadDraft | null
  preview_phase?: string | null
  citation_extraction_status?: CitationExtractionStatus | null
  citation_extraction_error?: string | null
  citation_reference_count?: number
  summary: { status: string; completed: number; total: number }
  next_poll_ms: number | null
}

interface Props {
  taskId: string
  onSubmitted?: (paperId: number) => void
}

const UploadParsingDetail: React.FC<Props> = ({ taskId, onSubmitted = () => undefined }) => {
  const { t } = useLanguage()
  const [detail, setDetail] = useState<ParsingDetail | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState(0)
  const [reload, setReload] = useState(0)
  const [actionPending, setActionPending] = useState(false)

  const downloadOriginal = async (fileId: string, filename: string) => {
    try {
      const blob = await api.download(`/api/upload-tasks/${taskId}/files/${encodeURIComponent(fileId)}/download`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url; link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    } catch (reason: any) {
      setError(reason.message || t('upload.operationFailed'))
    }
  }

  useEffect(() => {
    let stopped = false
    let timer: number | undefined
    const poll = async () => {
      try {
        const response = await api.get<{ ok: boolean; data: ParsingDetail }>(`/api/upload-tasks/${taskId}/parsing`)
        if (stopped) return
        const value = unwrapData(response)
        setDetail(value)
        setError('')
        if (value.next_poll_ms) timer = window.setTimeout(poll, value.next_poll_ms)
      } catch (reason: any) {
        if (!stopped) {
          setError(reason.message || t('upload.detailLoadFailed'))
          if (![401, 403, 404].includes(reason.status)) timer = window.setTimeout(poll, 2000)
        }
      }
    }
    void poll()
    return () => { stopped = true; if (timer) window.clearTimeout(timer) }
  }, [taskId, reload])

  const runAction = async (path: 'retry' | 'manual') => {
    setActionPending(true)
    try {
      await api.post(`/api/rag/upload-tasks/${taskId}/${path}`)
      setReload(value => value + 1)
    } catch (reason: any) {
      setError(reason.message || t('upload.operationFailed'))
    } finally {
      setActionPending(false)
    }
  }

  // 处理阶段标签统一走 upload.step.<stage.key>，与处理流程组件保持一致
  const failedStageLabel = (key: string | null | undefined): string => {
    const stage = key ? PROCESSING_STAGES.find(item => item.key === key) : undefined
    return stage ? t('upload.step.' + stage.key) : (key || '')
  }

  const statusNote = (value: ParsingDetail): string => {
    switch (value.status) {
      case 'summarizing':
        if (value.preview_phase && ['assembling', 'organizing', 'reviewing', 'saving', 'spectra'].includes(value.preview_phase)) {
          return t(`upload.previewNotes.${value.preview_phase}`)
        }
        return t('upload.summarizingNote')
      case 'failed':
        return t('upload.failedPreviewNote')
      case 'reading':
        return t('upload.readingNote', { completed: value.summary.completed, total: value.summary.total })
      case 'extracting':
        return t('upload.extractingNote')
      case 'queued':
        return t('upload.queuedNote')
      default:
        return t('upload.defaultNote')
    }
  }

  return (
    <Box sx={{ mt: 2 }}>
      {error && (
        <Alert severity="warning" sx={{ mb: 1.5 }} action={
          <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={() => setReload(value => value + 1)}>
            {t('common.retry')}
          </Button>
        }>{error}</Alert>
      )}
      {!detail && !error && <LinearProgress aria-label={t('upload.loadingDetailAria')} />}
      {detail && (
        <>
          {detail.status !== 'ready' && detail.citation_extraction_status && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" fontWeight={700}>
                {t('upload.citationExtractionTitle')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t(`upload.citationStatus.${detail.citation_extraction_status}`)} · {t('upload.citationReferenceCount', { count: detail.citation_reference_count || 0 })}
              </Typography>
              {detail.citation_extraction_error && <Alert severity="info" sx={{ mt: 1 }}>{detail.citation_extraction_error}</Alert>}
            </Box>
          )}
          <Tabs
            value={tab}
            onChange={(_, value) => setTab(value)}
            aria-label={t('upload.parsingDetailAria')}
            sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
          >
            <Tab label={t('upload.tabAiForm')} />
            <Tab label={t('upload.tabChunks')} />
          </Tabs>

          {tab === 0 && (
            <Box role="tabpanel" aria-label={t('upload.tabAiForm')}>
              {detail.status === 'needs_workflow' ? (
                <Box data-workflow-paused>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    {t('upload.workflowPaused')} {detail.workflow_assessment?.reason}
                  </Alert>
                  <Typography variant="subtitle1">{detail.workflow_assessment?.paper?.title}</Typography>
                  <Typography variant="body2">{detail.workflow_assessment?.paper?.authors?.join(', ')}</Typography>
                  <Typography variant="body2">{detail.workflow_assessment?.paper?.year} {detail.workflow_assessment?.paper?.doi}</Typography>
                  {detail.files?.map(file => <Button key={file.file_id}
                    onClick={() => void downloadOriginal(file.file_id, file.original_filename)}>{file.original_filename}</Button>)}
                </Box>
              ) : detail.status === 'ready' ? (
                <UploadTaskEditor taskId={taskId} onSubmitted={onSubmitted} />
              ) : detail.status === 'failed' && !detail.partial_draft ? (
                <Typography variant="body2" color="text.secondary">
                  {t('upload.parseIncomplete')}
                </Typography>
              ) : (
                <UploadTaskEditor
                  taskId={taskId}
                  onSubmitted={onSubmitted}
                  readOnly
                  draftOverride={detail.partial_draft ?? null}
                  statusNote={statusNote(detail)}
                />
              )}
            </Box>
          )}

          {tab === 1 && (
            <Box role="tabpanel" aria-label={t('upload.tabChunks')}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                {t('upload.chunkProgressTitle', { completed: detail.summary.completed, total: detail.summary.total })}
              </Typography>
              {!!detail.pending_visual_regions?.length && <Alert severity="info" sx={{ mb: 1.5 }}>
                {t('upload.visualReadingPending', { count: detail.pending_visual_regions.length })}
                {detail.files?.map(file => {
                  const pages = [...new Set(detail.pending_visual_regions!.filter(region => region.file_id === file.file_id)
                    .map(region => region.pdf_page))].sort((a, b) => a - b)
                  return pages.length ? <Typography key={file.file_id} variant="body2">
                    {t('upload.visualReadingPendingPages', { filename: file.original_filename, pages: pages.join(', ') })}
                  </Typography> : null
                })}
              </Alert>}
              {detail.chunks.length === 0 && (
                <Typography variant="body2" color="text.secondary">{t('upload.noChunksYet')}</Typography>
              )}
              {detail.chunks.map(chunk => (
                <Accordion key={chunk.chunk_id} disableGutters elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', minWidth: 0, flexWrap: 'wrap' }}>
                      <Chip size="small" label={chunk.status} color={chunk.status === 'failed' ? 'error' : chunk.status === 'completed' ? 'success' : 'default'} />
                      <Typography variant="body2">{chunk.filename} · {chunk.section || t('upload.bodyText')}</Typography>
                      {chunk.page_start && <Typography variant="caption" color="text.secondary">{t('upload.pageRange', {
                        start: chunk.page_start,
                        end: chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : '',
                      })}</Typography>}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    {chunk.error && <Alert severity="error">{chunk.error}</Alert>}
                    {chunk.result && <Typography component="pre" variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', m: 0 }}>{JSON.stringify(chunk.result, null, 2)}</Typography>}
                  </AccordionDetails>
                </Accordion>
              ))}
            </Box>
          )}
        </>
      )}
    </Box>
  )
}

export default UploadParsingDetail
