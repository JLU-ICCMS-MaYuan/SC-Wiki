import React, { useRef, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, IconButton, LinearProgress, Tooltip, Typography } from '@mui/material'
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { getStoredToken } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import { buildLlmHeaders } from '../lib/llmProvider'
import { UploadTaskState, unwrapData } from '../lib/paperProcessing'

// 单文件大小上限（字节）。界面上的「每个最大 50 MB」提示由 zh 字典 upload.limit 提供；
// 源码中的「最大 50 MB」字面量是前端契约测试
// tests/01_decentralized_uploading/test_issue18_upload_limits.py 的检索锚点，改动需同步该测试。
const MAX_BYTES = 50 * 1024 * 1024
type Role = 'main' | 'supplementary' | 'attachment'
interface Selected { clientId: string; file: File; role: Role; progress: number; status: string }

interface Props { onCreated: (task: UploadTaskState) => void }

function uploadOne(
  taskId: string,
  item: Selected,
  progress: (value: number) => void,
  t: (key: string, vars?: Record<string, string | number>) => string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/upload-tasks/${taskId}/files/${item.clientId}`)
    const token = getStoredToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    Object.entries(buildLlmHeaders()).forEach(([key, value]) => xhr.setRequestHeader(key, value))
    xhr.upload.onprogress = event => event.lengthComputable && progress(Math.round(event.loaded / event.total * 100))
    xhr.onerror = () => reject(new Error(t('upload.networkError')))
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else {
        try { reject(new Error(JSON.parse(xhr.responseText)?.detail?.message || t('upload.uploadFailed'))) }
        catch { reject(new Error(xhr.status === 413 ? t('upload.fileTooLarge') : t('upload.uploadFailedHttp', { status: xhr.status }))) }
      }
    }
    const body = new FormData()
    body.append('file', item.file)
    xhr.send(body)
  })
}

const MultiFileUploadPanel: React.FC<Props> = ({ onCreated }) => {
  const { t } = useLanguage()
  const inputs = useRef<Partial<Record<Role, HTMLInputElement | null>>>({})
  const [items, setItems] = useState<Selected[]>([])
  const [busy, setBusy] = useState(false)
  const [dragOver, setDragOver] = useState<Role | null>(null)
  const [error, setError] = useState('')

  const choose = (role: Role, files: FileList | File[] | null) => {
    if (!files || busy) return
    if (role === 'main' && (files.length > 1 || (files.length > 0 && items.some(item => item.role === 'main')))) {
      setError(t('upload.onlyOneMain'))
      return
    }
    const signatures = new Set(items.map(item => `${item.file.name}:${item.file.size}:${item.file.lastModified}`))
    const rejected: string[] = []
    const accepted: File[] = []
    for (const file of Array.from(files)) {
      const signature = `${file.name}:${file.size}:${file.lastModified}`
      const supported = role === 'attachment'
        ? /\.(cif|poscar|vasp)$/i.test(file.name) || /^(POSCAR|CONTCAR)$/i.test(file.name)
        : /\.(pdf|txt|md)$/i.test(file.name)
      if (!supported) rejected.push(t(role === 'attachment' ? 'upload.unsupportedSourceFile' : 'upload.unsupportedTextFile', { name: file.name }))
      else if (file.size > MAX_BYTES) rejected.push(t('upload.fileTooLargeNamed', { name: file.name }))
      else if (signatures.has(signature)) rejected.push(t('upload.fileDuplicate', { name: file.name }))
      else { accepted.push(file); signatures.add(signature) }
    }
    const additions = accepted.map((file): Selected => ({
      clientId: crypto.randomUUID().replaceAll('-', ''), file,
      role, progress: 0, status: '等待上传',
    }))
    if (additions.length) setItems(current => [...current, ...additions])
    setError(rejected.join(t('upload.sentenceSeparator')))
  }

  const remove = (clientId: string) => {
    setItems(current => current.filter(item => item.clientId !== clientId))
  }

  const clear = () => {
    if (!items.length || !window.confirm(t('upload.confirmClear'))) return
    setItems([])
    setError('')
    Object.values(inputs.current).forEach(input => { if (input) input.value = '' })
  }

  const start = async () => {
    if (busy) return
    if (items.filter(item => item.role === 'main').length !== 1) {
      setError(t('upload.mustSelectMain'))
      return
    }
    setBusy(true); setError('')
    try {
      const created = await api.post<{ ok: boolean; data: UploadTaskState }>('/api/upload-tasks', {
          parser_profile: 'complementary',
        files: items.map(item => ({
          client_id: item.clientId, role: item.role, filename: item.file.name,
          size: item.file.size, media_type: item.file.type || null,
        })),
      })
      const task = unwrapData(created)
      const serverFiles = task.files || []
      const queue = items.map((item, index) => ({
        ...item,
        clientId: serverFiles[index]?.file_id || '',
      }))
      let cursor = 0
      const worker = async () => {
        while (cursor < queue.length) {
          const item = queue[cursor++]
          await uploadOne(task.task_id, item, value => setItems(current => current.map(existing =>
            existing.file === item.file ? { ...existing, progress: value, status: '上传中' } : existing)), t)
          setItems(current => current.map(existing => existing.file === item.file ? { ...existing, progress: 100, status: '完成' } : existing))
        }
      }
      await Promise.all(Array.from({ length: Math.min(3, queue.length) }, worker))
      const detail = await api.get<{ ok: boolean; data: UploadTaskState }>(`/api/upload-tasks/${task.task_id}`)
      onCreated(unwrapData(detail))
      setItems([])
    } catch (reason: any) {
      setError(reason.message || t('upload.batchUploadFailed'))
    } finally { setBusy(false) }
  }

  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" fontWeight={700}>{t('upload.newTaskTitle')}</Typography>
        <Typography variant="body2" color="text.secondary">{t('upload.newTaskHint')}</Typography>

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          {t('upload.uploadLimits', { size: 50, count: 3 })}
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' }, gap: 2, mt: 2 }}>
          {(['main', 'supplementary', 'attachment'] as const).map(role => <Box
            key={role} role="region" aria-label={t('upload.role.' + role)}
            onDragOver={event => { event.preventDefault(); if (!busy) setDragOver(role) }}
            onDragLeave={() => setDragOver(null)}
            onDrop={event => { event.preventDefault(); setDragOver(null); choose(role, event.dataTransfer.files) }}
            sx={{ minWidth: 0, p: 2, border: '1px solid', borderColor: dragOver === role ? 'primary.main' : 'divider', borderRadius: 2 }}
          >
            <Typography fontWeight={700}>{t('upload.role.' + role)}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5, minHeight: { md: 40 } }}>
              {t('upload.fileAreaHelp.' + role)}
            </Typography>
            <Button
              variant="outlined" fullWidth disabled={busy} startIcon={<CloudUploadOutlinedIcon />}
              onClick={() => inputs.current[role]?.click()}
              sx={{ minHeight: 72, mb: 1, bgcolor: dragOver === role ? 'action.hover' : undefined }}
            >{t('upload.chooseForRole', { role: t('upload.role.' + role) })}</Button>
            <input ref={element => { inputs.current[role] = element }} type="file" hidden
              aria-label={t('upload.chooseForRole', { role: t('upload.role.' + role) })}
              multiple={role !== 'main'} disabled={busy}
              accept={role === 'attachment' ? '.cif,.poscar,.vasp,POSCAR,CONTCAR' : '.pdf,.txt,.md'}
              onChange={event => { choose(role, event.target.files); event.target.value = '' }} />
            {items.filter(item => item.role === role).map(item => <Box key={item.clientId}
              sx={{ display: 'flex', gap: 0.5, mb: 1, alignItems: 'center', minWidth: 0 }}>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{item.file.name}</Typography>
                <LinearProgress variant="determinate" value={item.progress} aria-label={item.file.name} />
              </Box>
              <Tooltip title={t('upload.removeFile')}><span><IconButton aria-label={t('upload.removeFileAria', { name: item.file.name })}
                size="small" disabled={busy} onClick={() => remove(item.clientId)}><DeleteOutlineIcon fontSize="small" /></IconButton></span></Tooltip>
            </Box>)}
          </Box>)}
        </Box>
        {error && <Alert severity="error" sx={{ my: 1 }}>{error}</Alert>}
        <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
          <Button variant="contained" onClick={() => void start()} disabled={busy || items.length === 0}>{busy ? t('upload.uploadingInProgress') : t('upload.startUpload')}</Button>
          {items.length > 0 && <Button color="inherit" onClick={clear} disabled={busy}>{t('upload.clearList')}</Button>}
        </Box>
      </CardContent>
    </Card>
  )
}

export default MultiFileUploadPanel
