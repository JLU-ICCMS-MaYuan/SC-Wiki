import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress, Typography } from '@mui/material'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { api } from '../lib/api'
import { UploadTaskState, unwrapData } from '../lib/paperProcessing'
import { useLanguage } from '../context/LanguageContext'


// 倒计时归零时的显示文案由 zh 字典 upload.cleanupPending 提供；源码中的「等待清理」
// 字面量是前端契约测试 tests/01_decentralized_uploading/test_issue24_persistence_and_ui.py
// 的检索锚点，改动需同步该测试。
function countdownParts(
  cleanupAt: number | null | undefined,
  now: number,
): { hours: number; minutes: number; seconds: number; pending: boolean } | null {
  if (!cleanupAt) return null
  const seconds = Math.max(0, cleanupAt - Math.floor(now / 1000))
  if (seconds === 0) return { hours: 0, minutes: 0, seconds: 0, pending: true }
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return { hours, minutes, seconds: rest, pending: false }
}

// 任务状态 → upload.status.<value> 字典键（UploadTaskStatus 的可显示子集）
const STATUS_KEYS = [
  'uploading', 'queued', 'extracting', 'needs_role_review', 'reading', 'summarizing', 'ready',
  'submitting', 'failed', 'duplicate', 'cancelling', 'cancelled',
] as const

interface Props {
  refreshKey?: number
}

const UploadTaskCenter: React.FC<Props> = ({ refreshKey }) => {
  const { t } = useLanguage()
  const [tasks, setTasks] = useState<UploadTaskState[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [now, setNow] = useState(Date.now())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchDeleting, setBatchDeleting] = useState(false)
  const [notice, setNotice] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const response = await api.get<{ ok: boolean; data: UploadTaskState[] }>('/api/upload-tasks')
      const next = unwrapData(response)
      setTasks(next)
      // 清除已被清理或过期的选中项，避免向批量接口提交无效 ID。
      setSelectedIds(prev => {
        const alive = new Set(next.map(task => task.task_id))
        const pruned = [...prev].filter(id => alive.has(id))
        return pruned.length === prev.size ? prev : new Set(pruned)
      })
      setError('')
    } catch (reason: any) {
      setError(reason.message || t('upload.recordsLoadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [refreshKey])
  useEffect(() => {
    const refresh = () => { void load() }
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const activeCount = useMemo(() => tasks.filter(task => task.status !== 'submitted').length, [tasks])

  const cancel = async (event: React.MouseEvent, taskId: string) => {
    event.stopPropagation()
    if (!window.confirm(t('upload.cancelTaskConfirm'))) return
    await api.post(`/api/upload-tasks/${taskId}/cancel`)
    await load()
  }

  const remove = async (event: React.MouseEvent, taskId: string) => {
    event.stopPropagation()
    try {
      await api.del(`/api/upload-tasks/${taskId}`)
      setError('')
      await load()
    } catch (reason: any) {
      setError(reason.message || t('upload.operationFailed'))
    }
  }

  const allSelected = tasks.length > 0 && tasks.every(task => selectedIds.has(task.task_id))
  const someSelected = selectedIds.size > 0

  const toggleSelect = (taskId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(tasks.map(task => task.task_id)))
  }

  const batchDelete = async () => {
    if (!someSelected || batchDeleting) return
    if (!window.confirm(t('upload.batchDeleteConfirm', { n: selectedIds.size }))) return
    setBatchDeleting(true)
    setNotice('')
    try {
      const result = await api.post<{ deleted: { task_id: string }[]; failed: { task_id: string; reason: string }[] }>(
        '/api/upload-tasks/batch-delete', { task_ids: [...selectedIds] },
      )
      const deleted = result?.deleted?.length || 0
      const failed = result?.failed || []
      setNotice(failed.length > 0
        ? t('upload.batchDeletePartialFailed', { n: deleted, reason: failed.map(item => item.reason).join('；') })
        : t('upload.batchDeleteDone', { n: deleted }))
      setSelectedIds(new Set())
      await load()
    } catch (reason: any) {
      setError(reason.message || t('upload.operationFailed'))
    } finally {
      setBatchDeleting(false)
    }
  }

  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, gap: 1, flexWrap: 'wrap' }}>
        <Typography variant="h6" fontWeight={700}>{t('upload.recordsTitle')} <Chip size="small" label={`${activeCount}/100`} /></Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
          <Box component="label" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: tasks.length > 0 ? 'pointer' : 'default' }}>
            <Checkbox
              size="small"
              checked={allSelected}
              indeterminate={someSelected && !allSelected}
              disabled={tasks.length === 0}
              onChange={toggleSelectAll}
              inputProps={{ 'aria-label': t('upload.selectAll') }}
            />
            <Typography variant="body2" color="text.secondary">{t('upload.selectAll')}</Typography>
          </Box>
          {someSelected && (
            <>
              <Chip size="small" color="primary" label={t('upload.selectedCount', { n: selectedIds.size })} onDelete={() => setSelectedIds(new Set())} />
              <Button size="small" color="error" variant="outlined" disabled={batchDeleting} onClick={() => void batchDelete()}>{t('upload.batchDelete')}</Button>
            </>
          )}
          <Button size="small" onClick={() => void load()} disabled={loading}>{t('common.refresh')}</Button>
        </Box>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 1 }}>{notice}</Alert>}
      {loading && tasks.length === 0 && <CircularProgress size={22} />}
      {tasks.length === 0 && !loading && <Typography color="text.secondary">{t('upload.noActiveTasks')}</Typography>}
      <Box sx={{ display: 'grid', gap: 1 }}>
        {tasks.map(task => {
          const remaining = countdownParts(task.cleanup_at, now)
          const running = ['uploading', 'queued', 'extracting', 'reading', 'summarizing', 'submitting', 'cancelling']
            .includes(task.status || '')
          const statusText = task.status && (STATUS_KEYS as readonly string[]).includes(task.status)
            ? t('upload.status.' + task.status)
            : task.stage || ''
          return (
            <Card key={task.task_id} variant="outlined" sx={{ position: 'relative', '&:hover': { borderColor: 'primary.main' }, '&:focus-within': { borderColor: 'primary.main' } }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 }, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: { xs: 'wrap', sm: 'nowrap' } }}>
                <Checkbox
                  size="small"
                  sx={{ p: 0.5, position: 'relative', zIndex: 2 }}
                  checked={selectedIds.has(task.task_id)}
                  onChange={() => toggleSelect(task.task_id)}
                  inputProps={{ 'aria-label': t('upload.toggleSelectAria', { filename: task.filename || task.files?.[0]?.original_filename || task.task_id }) }}
                />
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography component="a"
                    href={`/upload/tasks/${encodeURIComponent(task.task_id)}`}
                    target="_blank" rel="noopener"
                    aria-label={t('upload.openTaskNewTab', { filename: task.filename || task.files?.[0]?.original_filename || task.task_id })}
                    fontWeight={700} noWrap sx={{ display: 'block', color: 'inherit', textDecoration: 'none',
                      '&::after': { content: '\'\'', position: 'absolute', inset: 0, zIndex: 1 },
                      '&:focus-visible': { outline: 'none', '&::after': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: '-2px' } },
                    }}>{task.filename || task.files?.[0]?.original_filename || task.task_id}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {statusText}
                    {task.total_chunks > 0 ? t('upload.chunkCount', { done: task.completed_chunks, total: task.total_chunks }) : ''}
                  </Typography>
                  {remaining && <Typography variant="caption" color={remaining.pending ? 'error' : 'warning.main'} sx={{ ml: 1 }}>
                    {remaining.pending
                      ? t('upload.cleanupPending')
                      : remaining.hours > 0
                        ? t('upload.cleanupHours', { hours: remaining.hours, minutes: remaining.minutes })
                        : t('upload.cleanupMinutes', { minutes: remaining.minutes, seconds: remaining.seconds })}
                  </Typography>}
                </Box>
                <OpenInNewIcon aria-hidden="true" sx={{ color: 'text.disabled', fontSize: 18 }} />
                {running
                  ? <Button sx={{ position: 'relative', zIndex: 2 }} size="small" color="warning" onClick={event => void cancel(event, task.task_id)}>{t('upload.cancel')}</Button>
                  : ['failed', 'duplicate', 'cancelled'].includes(task.status || '')
                    ? <Button sx={{ position: 'relative', zIndex: 2 }} size="small" color="error" onClick={event => void remove(event, task.task_id)}>{t('upload.clean')}</Button>
                    : null}
              </CardContent>
            </Card>
          )
        })}
      </Box>
    </Box>
  )
}

export default UploadTaskCenter
