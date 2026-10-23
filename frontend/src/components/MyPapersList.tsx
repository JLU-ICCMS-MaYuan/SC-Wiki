import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box, Button, Chip, CircularProgress, Stack, Typography, TextField, MenuItem, Pagination,
} from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'

interface MyPaper {
  id: number
  title: string | null
  doi: string | null
  journal: string | null
  year: number | null
  review_status: string | null
  created_at: string | null
  can_revise?: boolean
  checked_status?: string
  checked_at?: string
}

// 审核状态的颜色映射；标签文案按 value 查 dict.enums.reviewStatus。
const STATUS_COLORS: Record<string, 'warning' | 'success' | 'error' | 'info'> = {
  pending: 'warning', approved: 'success', rejected: 'error', needs_revision: 'info',
}

// 已提交论文永久保存在 MySQL，与上传页那份 24 小时后清理、受活动任务配额限制的
// 「上传解析记录」性质不同，因此单独放在用户中心，不混入上传工作区。
const MyPapersList: React.FC<{ kind?: 'uploads' | 'reviews' }> = ({ kind = 'uploads' }) => {
  const navigate = useNavigate()
  const { t, dict } = useLanguage()
  const [items, setItems] = useState<MyPaper[] | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const requestID = useRef(0)

  const load = useCallback(async () => {
    const request = ++requestID.current
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (page > 1) { params.set('offset', String((page - 1) * 20)); params.set('limit', '20') }
      if (query) params.set('keyword', query)
      if (status) params.set('review_status', status)
      const endpoint = kind === 'reviews' ? '/api/account/reviewed-papers' : '/api/papers/my-uploads'
      const data = await api.get<{ items?: MyPaper[]; total?: number }>(`${endpoint}${params.size ? `?${params}` : ''}`)
      if (request !== requestID.current) return
      setItems(Array.isArray(data?.items) ? data.items : [])
      setTotal(data.total ?? data.items?.length ?? 0)
    } catch (e: any) {
      if (request === requestID.current) setError(e?.message || t('paperDetail.loadMyPapersFailed'))
    } finally {
      if (request === requestID.current) setLoading(false)
    }
  }, [t, kind, query, status, page])

  useEffect(() => { void load(); return () => { requestID.current++ } }, [load])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={28} />
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ py: 2 }}>
        <Typography color="error" variant="body2" gutterBottom>{error}</Typography>
        <Button size="small" onClick={() => void load()}>{t('common.retry')}</Button>
      </Box>
    )
  }

  return (
    <>
    <Box component="form" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(keyword.trim()) }} sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2, mb: 1 }}>
      <TextField size="small" label={t('account.searchContributions')} value={keyword} onChange={e => setKeyword(e.target.value)} sx={{ flex: '1 1 240px' }} />
      <TextField select size="small" label={t('account.contributionStatus')} value={status} onChange={e => { setPage(1); setStatus(e.target.value) }} sx={{ minWidth: 130 }}><MenuItem value="">{t('account.allStatuses')}</MenuItem>{Object.keys(STATUS_COLORS).map(value => <MenuItem key={value} value={value}>{(dict.enums.reviewStatus as Record<string, string>)[value] || value}</MenuItem>)}</TextField>
      <Button type="submit" variant="outlined">{t('common.search')}</Button>
    </Box>
    {!items?.length && <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>{query || status ? t('account.noMatchingContributions') : kind === 'reviews' ? t('account.noChecks') : t('paperDetail.emptyMyPapers')}</Typography>}
    <Stack spacing={1} sx={{ mt: 1 }}>
      {(items || []).map(paper => (
        <Box
          key={paper.id}
          role="button"
          tabIndex={0}
          onClick={() => navigate(`/papers/${paper.id}`)}
          onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              navigate(`/papers/${paper.id}`)
            }
          }}
          sx={{
            p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider',
            cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' },
          }}
        >
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between" spacing={1}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" fontWeight={600} sx={{ overflowWrap: 'anywhere' }}>
                {paper.title || t('paperDetail.paperIndexFallback', { n: paper.id })}
              </Typography>
              {kind === 'reviews' && paper.checked_at && <Typography variant="caption" color="text.secondary" display="block">{t('account.checkedAt', { date: new Date(paper.checked_at).toLocaleString() })}</Typography>}
              <Typography variant="caption" color="text.secondary">
                {[paper.journal, paper.year, paper.doi].filter(Boolean).join(' · ') || '—'}
              </Typography>
            </Box>
            <Chip
              size="small"
              variant="outlined"
              label={(dict.enums.reviewStatus as Record<string, string>)[paper.checked_status || paper.review_status || ''] || paper.checked_status || paper.review_status || (dict.enums.reviewStatus as Record<string, string>).pending}
              color={STATUS_COLORS[paper.checked_status || paper.review_status || ''] || 'default'}
            />
          </Stack>
          {paper.can_revise && <Button size="small" onClick={event => {
            event.stopPropagation(); navigate(`/papers/${paper.id}/revise`)
          }} onKeyDown={event => event.stopPropagation()}>{t('paperDetail.revise')}</Button>}
        </Box>
      ))}
    </Stack>
    <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" sx={{ mt: 2 }}><Typography variant="caption" color="text.secondary">{t('account.contributionCount', { count: total })}</Typography>{total > 20 && <Pagination count={Math.ceil(total / 20)} page={page} onChange={(_, value) => setPage(value)} size="small" />}</Stack>
    </>
  )
}

export default MyPapersList
