import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams, useParams } from 'react-router-dom'
import { Box, Button, CircularProgress, Typography } from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import { api } from '../lib/api'
import type { ApiError } from '../lib/api'
import PaperEditView from '../components/PaperEditView'
import { safeReturn } from '../lib/searchNavigation'
import { useLanguage } from '../context/LanguageContext'

// 论文可见性完全由后端 GET /api/papers/{id} 逐篇裁决（canViewPaper）。
// 本页不读取用户角色、不判断 review_status，只按状态码分流提示，避免权限规则出现两份实现。
const FAILURE_KEYS: Record<'invalid' | 'forbidden' | 'missing' | 'error', string> = {
  invalid: 'paperDetail.failure.invalid',
  forbidden: 'paperDetail.failure.forbidden',
  missing: 'paperDetail.failure.missing',
  error: 'paperDetail.failure.error',
}

type FailureKind = keyof typeof FAILURE_KEYS

// 路径参数由用户任意输入，先在本地拦截非正整数，避免无意义的网络往返。
const parsePaperId = (raw: string | undefined): number | null => {
  if (!raw || !/^\d+$/.test(raw)) return null
  const parsed = Number(raw)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}

const failureKindOf = (reason: unknown): FailureKind => {
  const status = (reason as ApiError | null)?.status
  if (status === 403) return 'forbidden'
  if (status === 404) return 'missing'
  if (status === 400) return 'invalid'
  return 'error'
}

const PaperDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useLanguage()
  const paperId = parsePaperId(id)

  const [loading, setLoading] = useState(paperId !== null)
  const [failure, setFailure] = useState<FailureKind | null>(paperId === null ? 'invalid' : null)
  const [paper, setPaper] = useState<any>(null)

  const [params] = useSearchParams()
  const returnTo = safeReturn(params.get('return'))
  const backLabel = returnTo.startsWith('/search') ? t('search.backResults') : t('common.back')
  const handleBack = useCallback(() => { navigate(returnTo) }, [navigate, returnTo])
  // 「我的论文」列表在用户中心，离开详情页后仍可由此回到任意已提交论文

  useEffect(() => {
    if (paperId === null) {
      setPaper(null)
      setFailure('invalid')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setFailure(null)
    setPaper(null)
    api.get<any>(`/api/papers/${paperId}`)
      .then(data => { if (!cancelled) setPaper(data) })
      .catch(reason => { if (!cancelled) setFailure(failureKindOf(reason)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [paperId])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  // 失败时不渲染 PaperEditView，避免任何论文字段泄漏。
  if (failure || !paper) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography color="error" gutterBottom>{t(FAILURE_KEYS[failure || 'error'])}</Typography>
        <Button onClick={handleBack} startIcon={<ArrowBackIcon />}>{backLabel}</Button>
      </Box>
    )
  }

  return <PaperEditView paper={paper} onBack={handleBack} backLabel={backLabel} myPapersHref="/account" />
}

export default PaperDetailPage
