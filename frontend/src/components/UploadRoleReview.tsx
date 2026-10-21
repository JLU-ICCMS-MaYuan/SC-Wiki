import { useEffect, useState } from 'react'
import { Alert, Box, Button, MenuItem, Select, Typography } from '@mui/material'

import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import type { UploadTaskFile, UploadTaskState } from '../lib/paperProcessing'
import { unwrapData } from '../lib/paperProcessing'

type Role = UploadTaskFile['role']

export default function UploadRoleReview({ task, onResolved }: {
  task: UploadTaskState
  onResolved: (state: UploadTaskState) => void
}) {
  const { t } = useLanguage()
  const assessment = task.role_assessment
  const [roles, setRoles] = useState<Record<string, Role>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setRoles(Object.fromEntries((task.files || []).map(file => [file.file_id, file.role])))
  }, [task.files])

  if (!assessment) return null
  const waiting = task.status === 'needs_role_review'
  const corrected = assessment.files.some(file => file.effective_role && file.effective_role !== file.declared_role)
  if (!waiting && !corrected) return null

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await api.post<{ ok: boolean; data: UploadTaskState }>(
        `/api/upload-tasks/${task.task_id}/resolve-roles`,
        { expected_revision: task.revision, roles: (task.files || []).map(file => ({
          file_id: file.file_id, role: roles[file.file_id],
        })) },
      )
      onResolved(unwrapData(response))
    } catch (reason: any) {
      setError(reason?.message || t('upload.roleReviewFailed'))
    } finally {
      setBusy(false)
    }
  }

  return <Alert severity={waiting ? 'warning' : 'info'} sx={{ mt: 2 }}>
    <Typography fontWeight={700}>{waiting ? t('upload.roleReviewNeeded') : t('upload.roleAutoCorrected')}</Typography>
    <Typography variant="body2">{assessment.reason}</Typography>
    {(task.files || []).map(file => {
      const details = assessment.files.find(item => item.file_id === file.file_id)
      return <Box key={file.file_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1, flexWrap: 'wrap' }}>
        <Typography variant="body2" sx={{ minWidth: 180, overflowWrap: 'anywhere' }}>{file.original_filename}</Typography>
        {waiting ? <Select size="small" value={roles[file.file_id] || file.role}
          aria-label={t('upload.roleForFile', { name: file.original_filename })}
          onChange={event => setRoles(current => ({ ...current, [file.file_id]: event.target.value as Role }))}>
          <MenuItem value="main">{t('upload.role.main')}</MenuItem>
          <MenuItem value="supplementary">{t('upload.role.supplementary')}</MenuItem>
          <MenuItem value="attachment">{t('upload.role.attachment')}</MenuItem>
        </Select> : <Typography variant="body2">{t(`upload.role.${file.role}`)}</Typography>}
        <Typography variant="caption" color="text.secondary">
          {[...(details?.article_signals || []), ...(details?.supplement_signals || [])].join('；') || t('upload.roleEvidenceMissing')}
        </Typography>
      </Box>
    })}
    {waiting && <Button size="small" variant="contained" disabled={busy || Object.values(roles).filter(role => role === 'main').length !== 1}
      onClick={() => void submit()} sx={{ mt: 1 }}>{t('upload.confirmRoles')}</Button>}
    {error && <Typography role="alert" color="error" variant="body2">{error}</Typography>}
  </Alert>
}
