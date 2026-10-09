import { useEffect, useState } from 'react'
import { Box, Button, CircularProgress, Drawer, IconButton, Stack, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'

export interface SourceTarget {
  term: string
  kind: 'paper' | 'papers' | 'definition'
  paper_id?: number
  paper_ids?: number[]
  definition_id?: number
}

interface Fragment { id: number; section: string; page: number | null; preview: string; content?: string }
type Wrapped<T> = { ok: boolean; data: T }

export default function RagSourceDrawer({ target, onClose, onExited }: {
  target: SourceTarget | null
  onClose: () => void
  onExited?: () => void
}) {
  const { t } = useLanguage()
  const [detail, setDetail] = useState<any>(null)
  const [fragments, setFragments] = useState<Fragment[]>([])
  const [choices, setChoices] = useState<any[]>([])
  const [selected, setSelected] = useState<Fragment | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    setDetail(null); setFragments([]); setChoices([]); setSelected(null); setError(false)
    if (!target) return
    setLoading(true)
    const load = async () => {
      if (target.kind === 'definition' && target.definition_id) {
        const result = await api.get<Wrapped<any>>(`/api/rag/definitions/${target.definition_id}`)
        return { detail: result.data, fragments: [], choices: [] }
      }
      if (target.kind === 'paper' && target.paper_id) {
        const [paper, chunks] = await Promise.all([
          api.get<Wrapped<any>>(`/api/rag/papers/${target.paper_id}`),
          api.get<Wrapped<Fragment[]>>(`/api/rag/papers/${target.paper_id}/fragments`),
        ])
        return { detail: paper.data, fragments: chunks.data, choices: [] }
      }
      if (target.kind === 'papers' && target.paper_ids?.length) {
        const results = await Promise.allSettled(target.paper_ids.map(id =>
          api.get<Wrapped<any>>(`/api/rag/papers/${id}`)))
        return { detail: null, fragments: [], choices: results.flatMap(result =>
          result.status === 'fulfilled' ? [result.value.data] : []) }
      }
      throw new Error('invalid source')
    }
    void load().then(value => {
      if (current) {
        setDetail(value.detail); setFragments(value.fragments); setChoices(value.choices)
        setError(value.choices.length === 0 && !value.detail)
        setLoading(false)
      }
    }).catch(() => { if (current) { setError(true); setLoading(false) } })
    return () => { current = false }
  }, [target])

  const openFragment = async (fragment: Fragment) => {
    const paperId = detail?.id || target?.paper_id
    if (!paperId) return
    try {
      const response = await api.get<Wrapped<Fragment>>(
        `/api/rag/papers/${paperId}/fragments/${fragment.id}`,
      )
      setSelected(response.data)
      setError(false)
    } catch { setError(true) }
  }

  const openPaper = async (paperId: number) => {
    setLoading(true)
    try {
      const [paper, chunks] = await Promise.all([
        api.get<Wrapped<any>>(`/api/rag/papers/${paperId}`),
        api.get<Wrapped<Fragment[]>>(`/api/rag/papers/${paperId}/fragments`),
      ])
      setDetail(paper.data); setFragments(chunks.data); setSelected(null); setError(false)
    } catch { setError(true) }
    finally { setLoading(false) }
  }

  return <Drawer anchor="right" open={Boolean(target)} onClose={onClose}
    ModalProps={{ keepMounted: false, disableRestoreFocus: true }}
    slotProps={{ transition: { onExited } }}
    PaperProps={{ 'data-rag-source-drawer': '', sx: { width: { xs: '100%', sm: 440 }, maxWidth: '100vw', p: 3, boxSizing: 'border-box' } }}>
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
      <Typography variant="h6">{t('rag.sourceDetail')}</Typography>
      <IconButton aria-label={t('rag.closeDetail')} onClick={onClose}><CloseIcon /></IconButton>
    </Box>
    {loading && <CircularProgress size={24} aria-label={t('rag.loadingDetail')} />}
    {error && <Typography color="error">{t('rag.sourceUnavailable')}</Typography>}
    {choices.length > 0 && !detail && <Stack spacing={1}>
      <Typography variant="subtitle1">{t('rag.choosePaper')}</Typography>
      {choices.map(paper => <Button key={paper.id} variant="outlined" onClick={() => void openPaper(paper.id)}
        sx={{ justifyContent: 'flex-start', textAlign: 'left' }}>{paper.title}</Button>)}
    </Stack>}
    {detail && <Stack spacing={2} sx={{ overflowY: 'auto' }}>
      {choices.length > 0 && <Button onClick={() => { setDetail(null); setFragments([]); setSelected(null) }}
        sx={{ alignSelf: 'flex-start' }}>{t('rag.backToPapers')}</Button>}
      <Typography variant="h6">{detail.title || detail.name}</Typography>
      {detail.journal && <Typography variant="body2" color="text.secondary">
        {detail.journal}{detail.year ? ` (${detail.year})` : ''}
      </Typography>}
      {detail.doi && <Typography variant="body2">DOI: {detail.doi}</Typography>}
      {detail.description && <Typography sx={{ whiteSpace: 'pre-wrap' }}>{detail.description}</Typography>}
      {(detail.abstract || detail.summary) && <Typography sx={{ whiteSpace: 'pre-wrap' }}>
        {detail.abstract || detail.summary}
      </Typography>}
      {fragments.length > 0 && <>
        <Typography variant="subtitle1">{t('rag.paperFragments')}</Typography>
        {fragments.map(fragment => <Button key={fragment.id} variant="outlined"
          onClick={() => void openFragment(fragment)} sx={{ textAlign: 'left', justifyContent: 'flex-start' }}>
          {fragment.section || t('rag.paperFragment')}{fragment.page ? ` · ${t('rag.page')} ${fragment.page}` : ''}
          {' · '}{fragment.preview.slice(0, 80)}
        </Button>)}
      </>}
      {selected && <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
        <Typography variant="subtitle2">{selected.section || t('rag.paperFragment')}</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap', mt: 1 }}>{selected.content}</Typography>
      </Box>}
    </Stack>}
  </Drawer>
}
