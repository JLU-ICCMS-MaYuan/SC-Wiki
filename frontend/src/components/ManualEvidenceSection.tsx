import { useEffect, useRef, useState, useSyncExternalStore, type MutableRefObject } from 'react'
import { Alert, Box, Button, FormControlLabel, Radio, RadioGroup, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import type { EvidenceRecord, EvidenceTarget } from './EvidenceWorkflow'
import { createManualEvidenceDrafts, manualDraftKey, manualFieldIdentity,
  type ManualEvidenceDrafts, type ManualItem, type ManualRecord, type PreparedManualEvidence } from '../lib/manualEvidenceDrafts'
import EvidenceReadableValue from './EvidenceReadableValue'

function PendingImage({ file, alt }: { file: File; alt: string }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!file.type.startsWith('image/') || !URL.createObjectURL) return
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file])
  return url ? <Box component="img" src={url} alt={alt} sx={{ maxWidth: '100%', maxHeight: 200, objectFit: 'contain' }} /> : null
}

export default function ManualEvidenceSection({ target, record, version, drafts, value = record.current_value,
  localChanged = false, prepare, readOnly = false, showHistory = true, onRecords, saveBeforeReview }: {
  target?: EvidenceTarget
  record: EvidenceRecord
  version?: string
  drafts?: ManualEvidenceDrafts
  value?: unknown
  localChanged?: boolean
  prepare?: () => Promise<PreparedManualEvidence>
  saveBeforeReview?: MutableRefObject<(() => Promise<boolean>) | null>
  readOnly?: boolean; showHistory?: boolean; onRecords?: (key: string, entries: ManualRecord[]) => void
}) {
  const { t } = useLanguage()
  const [fallback] = useState(createManualEvidenceDrafts)
  const store = drafts || fallback
  const key = manualDraftKey(target, record, value)
  const draft = useSyncExternalStore(store.subscribe, () => store.read(key))
  const { saved, reason, absence, choice, files, busy, error, notice } = draft
  useEffect(() => { onRecords?.(record.item_key || record.key, saved ? [...(saved.id ? [saved] : []), ...(saved.history || [])] : []) }, [saved, onRecords, record.item_key, record.key])
  const [loading, setLoading] = useState(true)
  const [reload, setReload] = useState(0)
  const [dragging, setDragging] = useState(false)
  const [preview, setPreview] = useState<{ url: string; kind: string } | null>(null)
  const currentKey = useRef(key)
  currentKey.current = key
  const itemKey = record.item_key
  const endpoint = target && /^[0-9a-f]{64}$/.test(itemKey || '')
    ? `/api/rag/evidence/${target.target}/${target.target_id}/manual/${itemKey}` : ''

  useEffect(() => {
    let active = true
    setLoading(true)
    if (!endpoint) { setLoading(false); return }
    const writes = store.read(key).writes
    void api.get<{ ok: boolean; data: ManualRecord }>(endpoint).then(response => {
      if (active) store.hydrate(key, response.data, writes)
    }).catch(error => { if (active) store.patch(key, { error: error.message || t('evidence.manualLoadFailed') }) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [endpoint, key, version, store, t, reload])
  useEffect(() => { setPreview(null) }, [key])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url) }, [preview])

  const addFiles = (incoming: File[]) => {
    if (busy) return
    const accepted: File[] = [], failures: string[] = []
    for (const file of incoming) {
      if (!/\.(png|jpe?g|webp|txt|md|pdf)$/i.test(file.name)) failures.push(t('evidence.manualInvalidType', { name: file.name }))
      else if (!file.size || file.size > 10 * 1024 * 1024) failures.push(t('evidence.manualInvalidSize', { name: file.name }))
      else if ((saved?.items.length || 0) + files.length + accepted.length >= 5) failures.push(t('evidence.manualItemLimit'))
      else accepted.push(file)
    }
    if (accepted.length) store.edit(key, { files: [...files, ...accepted], choice: 'provide' })
    store.patch(key, { error: failures.join(' ') })
  }

  const context = async (): Promise<PreparedManualEvidence> => {
    if (prepare) return prepare()
    if (!endpoint || !version) throw new Error(t('evidence.manualContextMissing'))
    return { endpoint, version, isCurrent: () => currentKey.current === key, complete: () => {} }
  }
  const saveBlockers = (input = draft) => [
    !input.reason.trim() && t('evidence.manualReasonRequired'),
    !input.choice && t('evidence.manualChoiceRequired'),
    input.choice === 'provide' && !input.files.length && !input.saved?.items.length && t('evidence.manualEvidenceRequired'),
    input.choice === 'none' && Boolean(input.saved?.items.length || input.files.length) && t('evidence.removeEvidenceBeforeNoEvidence'),
    input.choice === 'none' && !input.absence.trim() && t('evidence.manualAbsenceRequired'),
  ].filter((message): message is string => Boolean(message))
  // 请求只确认送出的输入修订；旧响应不可清空之后输入的理由和新文件。
  const save = async (uploadFiles = false) => {
    const input = store.read(key)
    if (input.busy) return
    if (!input.dirty && !input.files.length) return
    if (input.choice === 'none' && input.saved?.items.length) {
      store.patch(key, { error: t('evidence.removeEvidenceBeforeNoEvidence') }); return
    }
    if (!uploadFiles && input.files.length) {
      store.patch(key, { error: t('evidence.manualPendingFiles') }); return
    }
    const missing = saveBlockers(input)
    if (missing.length) { store.patch(key, { error: missing.join('；') }); return }
    store.patch(key, { busy: true, error: '', notice: '' })
    let stage = t('evidence.manualStageValue')
    let explanationSaved = false
    try {
      const ready = await context()
      const assertCurrent = () => { if (!ready.isCurrent()) throw new Error(t('evidence.changedDuringSave')) }
      assertCurrent()
      stage = t('evidence.manualStageReason')
      const direct = (input.saved?.items || []).filter(item => item.kind === 'text' && item.text)
        .map(item => ({ text: item.text!, source_description: item.source_description }))
      const response = await api.put<{ ok: boolean; data: ManualRecord }>(ready.endpoint, {
        expected_version: ready.version, reason: input.reason,
        no_evidence_reason: input.choice === 'none' ? input.absence : '', text_items: direct,
      })
      store.acknowledge(key, response.data, input.revision)
      explanationSaved = true
      if (uploadFiles) for (const file of input.files) {
        assertCurrent()
        stage = t('evidence.manualStageFile')
        const body = new FormData()
        body.append('expected_version', ready.version)
        body.append('file', file)
        const uploaded = await api.post<{ ok: boolean; data: ManualRecord }>(`${ready.endpoint}/files`, body)
        store.acknowledge(key, uploaded.data, input.revision, file)
      }
      assertCurrent()
      store.patch(key, { notice: t('common.saved') })
      if (store.read(key).revision === input.revision && !store.read(key).files.length) ready.complete()
    } catch (error: any) {
      store.patch(key, { error: `${stage}：${error.message || t('evidence.manualSaveFailed')}`,
        notice: explanationSaved ? t('evidence.manualPartialSaved') : '' })
    } finally { store.patch(key, { busy: false }) }
  }

  useEffect(() => {
    if (!saveBeforeReview) return
    const persist = async () => {
      if (store.read(key).busy) return false
      if (store.read(key).dirty || store.read(key).files.length) await save(true)
      const current = store.read(key)
      return !current.dirty && !current.busy && !current.files.length && !current.error
    }
    saveBeforeReview.current = persist
    return () => { if (saveBeforeReview.current === persist) saveBeforeReview.current = null }
  })

  const showFile = async (item: ManualItem) => {
    try {
      const blob = await api.download(`${endpoint}/files/${item.id}`)
      if (currentKey.current === key) setPreview({ url: URL.createObjectURL(blob), kind: item.kind })
    } catch (error: any) { store.patch(key, { error: error.message || t('evidence.manualLoadFailed') }) }
  }

  const removeItem = async (item: ManualItem) => {
    if (store.read(key).busy) return
    store.patch(key, { busy: true, error: '' })
    try {
      const ready = await context()
      if (!ready.isCurrent()) throw new Error(t('evidence.changedDuringSave'))
      if (item.kind === 'text') {
        const remaining = (saved?.items || []).filter(entry => entry.kind === 'text' && entry.id !== item.id && entry.text)
          .map(entry => ({ text: entry.text!, source_description: entry.source_description }))
        await api.put(ready.endpoint, { expected_version: ready.version, reason, no_evidence_reason: '', text_items: remaining })
      } else await api.del(`${ready.endpoint}/files/${item.id}`)
      const current = store.read(key)
      if (current.saved) store.patch(key, { saved: { ...current.saved, items: current.saved.items.filter(entry => entry.id !== item.id) }, writes: current.writes + 1 })
    } catch (error: any) { store.patch(key, { error: error.message || t('evidence.manualSaveFailed') }) }
    finally { store.patch(key, { busy: false }) }
  }

  const previewView = preview && (preview.kind === 'image'
    ? <Box component="img" src={preview.url} alt={t('evidence.manualImage')} sx={{ maxWidth: '100%' }} />
    : <Button component="a" href={preview.url} target="_blank" rel="noopener noreferrer">{t('evidence.openManualFile')}</Button>)
  const history = saved?.history || []
  const historyView = history.length > 0 && <Box component="details" sx={{ mt: 1 }}>
    <Typography component="summary">{t('evidence.historyLabel')}（{history.length}）</Typography>
    {history.map((entry, index) => <Box key={entry.id || index} sx={{ borderTop: 1, borderColor: 'divider', py: 1 }}>
      <Typography variant="caption">{entry.actor_name || t('evidence.manualContributor', { id: entry.actor_user_id || 0 })} · {t('evidence.historyReadonly')}</Typography>
      <EvidenceReadableValue value={entry.before_value} />
      <EvidenceReadableValue value={entry.after_value} />
      <Typography>{entry.reason}</Typography>
      {entry.no_evidence_reason && <Typography>{t('evidence.noEvidenceReason')}：{entry.no_evidence_reason}</Typography>}
      {entry.items.map(item => <Box key={item.id}>
        <Typography variant="caption">{t('evidence.humanProvided')} · {item.source_description}</Typography>
        {item.kind === 'text' ? <EvidenceReadableValue value={item.text} />
          : <Button type="button" size="small" onClick={() => void showFile(item)}>{item.filename || t('evidence.manualFile')}</Button>}
      </Box>)}
    </Box>)}
  </Box>
  const changed = localChanged || saved?.changed || draft.dirty
  const previous = store.previous(manualFieldIdentity(target, record), key)
  return <Box sx={{ display: 'grid', gap: 1.5, mt: 1 }}>
    {previous.length > 0 && <Box component="details"><Typography component="summary">{t('evidence.manualPreviousDraft')}</Typography>
      {previous.map(({ key: oldKey, draft: entry }) => <Box key={oldKey}><Typography>{entry.reason}</Typography><Typography>{entry.absence}</Typography>
        {entry.files.map((file, i) => <Typography key={i}>{file.name}</Typography>)}
        <Button type="button" disabled={readOnly || entry.busy} onClick={() => store.discard(oldKey)}>{t('evidence.manualDiscardPrevious')}</Button></Box>)}
    </Box>}
    {localChanged && !saved?.changed && <Alert severity="info">{t('evidence.manualSyncPending')}</Alert>}
    {!changed && readOnly ? <>{loading ? <Typography role="status">{t('evidence.manualLoading')}</Typography>
      : !error && !history.length && <Typography color="text.secondary">{t('evidence.noManualEdits')}</Typography>}</> : <>
      {(saved?.status === 'submitted' && !localChanged) || readOnly ? <>
        <Typography>{t('evidence.manualReason')}：{saved?.reason || reason}</Typography>
        {saved?.no_evidence_reason && <Typography>{t('evidence.noEvidenceReason')}：{saved.no_evidence_reason}</Typography>}
      </> : <>
        <TextField fullWidth multiline minRows={2} label={t('evidence.manualReason')} value={reason} onChange={event => store.edit(key, { reason: event.target.value })} />
        <RadioGroup aria-label={t('evidence.evidenceChoice')} value={choice} onChange={event => store.edit(key, { choice: event.target.value as 'provide' | 'none' })}>
          <FormControlLabel value="provide" control={<Radio />} label={t('evidence.provideEvidence')} disabled={busy} />
          <FormControlLabel value="none" control={<Radio />} label={t('evidence.doNotProvideEvidence')} disabled={busy} />
        </RadioGroup>
        {choice === 'none' && <>
          <TextField fullWidth multiline minRows={2} label={t('evidence.noEvidenceReason')} value={absence} onChange={event => store.edit(key, { absence: event.target.value })} />
        </>}
        {choice === 'provide' && <Box tabIndex={0} role="region" aria-label={t('evidence.manualDropZone')}
          onDragOver={event => { event.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={event => { event.preventDefault(); event.stopPropagation(); setDragging(false); addFiles(Array.from(event.dataTransfer.files)) }}
          onPaste={event => {
            if ((event.target as HTMLElement).closest('input,textarea,[contenteditable="true"]')) return
            const images = Array.from(event.clipboardData.items).filter(item => item.kind === 'file' && item.type.startsWith('image/'))
              .map(item => item.getAsFile()).filter((file): file is File => Boolean(file))
            if (!images.length) return
            event.preventDefault()
            const extensions: Record<string, string> = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' }
            addFiles(images.map((file, index) => new File([file], `screenshot-${Date.now()}-${index + 1}.${extensions[file.type] || 'unsupported'}`, { type: file.type })))
          }}
          sx={{ display: 'grid', gap: 1, p: 1.5, border: '2px dashed', borderColor: dragging ? 'primary.main' : 'divider', borderRadius: 1, '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' } }}>
          <Typography>{t('evidence.manualDropHint')}</Typography>
          <Typography variant="caption">{t('evidence.manualLimits')}</Typography>
          <Button component="label" size="small" variant="outlined" disabled={busy}>{t('evidence.chooseManualFile')}
            <input hidden type="file" multiple accept=".png,.jpg,.jpeg,.webp,.txt,.md,.pdf" onChange={event => { addFiles(Array.from(event.target.files || [])); event.target.value = '' }} />
          </Button>
        </Box>}
        {files.map((file, index) => <Box key={`${file.name}:${index}`}>
          <Typography variant="caption">{t('evidence.manualPendingFile')}：{file.name}</Typography>
          <PendingImage file={file} alt={t('evidence.manualImage')} />
          <Button type="button" size="small" disabled={busy} onClick={() => store.edit(key, { files: files.filter(entry => entry !== file) })}>{t('evidence.removeManualItem')}</Button>
        </Box>)}
        {(saveBlockers().length > 0 || loading || busy) && <Alert severity="info" role="status">
          {loading ? t('evidence.manualLoading') : busy ? t('evidence.manualSaving') : saveBlockers().map(message => <Typography key={message} variant="body2">{message}</Typography>)}
        </Alert>}
        <Button type="button" size="small" variant="contained" disabled={loading || busy || saveBlockers().length > 0} onClick={() => void save(true)}>{busy ? t('evidence.manualSaving') : t('evidence.saveAndComplete')}</Button>
      </>}
    </>}
    {(saved?.items || []).map(item => <Box key={item.id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Typography variant="caption">{t('evidence.humanProvided')} · {item.source_description}</Typography>
      {item.kind === 'text' ? <EvidenceReadableValue value={item.text} />
        : <Button type="button" size="small" onClick={() => void showFile(item)}>{item.filename || t('evidence.manualFile')}</Button>}
      {saved?.status === 'draft' && !readOnly && <Button type="button" size="small" color="error" disabled={busy} onClick={() => void removeItem(item)}>{t('evidence.removeManualItem')}</Button>}
      {(item.kind === 'image' || item.kind === 'pdf') && item.ai_read_status !== 'read' && <Typography variant="caption" display="block">{t('evidence.fileNotRead')}</Typography>}
    </Box>)}
    {previewView}
    {notice && <Alert severity="info">{notice}</Alert>}
    {error && <Alert severity="error">{error}</Alert>}
    {error && !saved && <Button type="button" disabled={loading} onClick={() => { store.patch(key, { error: '' }); setReload(value => value + 1) }}>{t('evidence.manualRetryLoad')}</Button>}
    {showHistory && historyView}
  </Box>
}
