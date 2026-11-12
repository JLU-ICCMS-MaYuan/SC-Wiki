import { useState } from 'react'
import { Alert, Box, Button, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import { unwrapData, type UploadTaskState } from '../lib/paperProcessing'

export default function UploadParsingModeChoice({ task, onStarted }: {
  task: UploadTaskState; onStarted: (task: UploadTaskState) => void
}) {
  const { t } = useLanguage()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (task.status !== 'uploading' || !task.defer_parsing || !task.files?.length
    || task.files.some(file => file.upload_status !== 'completed')) return null
  const start = async (parsing_mode: 'shallow' | 'deep') => {
    if (busy) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ data: UploadTaskState }>(`/api/upload-tasks/${task.task_id}/finalize`, { parsing_mode })
      onStarted(unwrapData(result))
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <Box sx={{ my: 2 }} role="region" aria-label={t('upload.chooseParsingMode')}>
    <Typography variant="subtitle1">{t('upload.chooseParsingMode')}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{t('upload.parsingModeHint')}</Typography>
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Button variant="contained" disabled={busy} onClick={() => void start('shallow')}>{t('upload.shallowParsing')}</Button>
      <Button variant="outlined" disabled={busy} onClick={() => void start('deep')}>{t('upload.deepParsing')}</Button>
    </Box>
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
  </Box>
}
