import React from 'react'
import { Alert, Box, Button } from '@mui/material'
import { useNavigate, useParams } from 'react-router-dom'
import UploadTaskEditor from '../components/UploadTaskEditor'
import { useLanguage } from '../context/LanguageContext'

export default function PaperRevisionPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t } = useLanguage()
  const paperId = Number(id)
  if (!id || !/^\d+$/.test(id) || !Number.isSafeInteger(paperId) || paperId < 1) {
    return <Alert severity="error">{t('paperDetail.failure.invalid')}</Alert>
  }
  return <Box>
    <Button onClick={() => navigate(`/papers/${paperId}`)}>{t('common.back')}</Button>
    <UploadTaskEditor key={paperId} taskId={String(paperId)} revisionPaperId={paperId}
      onSubmitted={submittedId => navigate(`/papers/${submittedId}`, { replace: true })} />
  </Box>
}
