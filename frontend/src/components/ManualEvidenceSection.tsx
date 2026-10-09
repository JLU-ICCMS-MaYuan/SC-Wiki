import { useEffect, useState } from 'react'
import { Alert, Box, Button, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'
import type { EvidenceRecord, EvidenceTarget } from './EvidenceWorkflow'
import EvidenceReadableValue from './EvidenceReadableValue'

interface ManualItem {
  id: string
  kind: 'text' | 'image' | 'text_file'
  text?: string
  filename?: string
  source_description: string
  ai_read_status?: string
}
interface ManualRecord {
  id?: string
  changed: boolean
  before_value?: unknown
  after_value?: unknown
  actor_user_id?: number
  actor_name?: string
  status?: string
  reason: string
  no_evidence_reason: string
  items: ManualItem[]
  history?: ManualRecord[]
}

export default function ManualEvidenceSection({ target, record, version }: {
  target?: EvidenceTarget
  record: EvidenceRecord
  version?: string
}) {
  const { t } = useLanguage()
  const [saved, setSaved] = useState<ManualRecord | null>(null)
  const [reason, setReason] = useState('')
  const [absence, setAbsence] = useState('')
  const [text, setText] = useState('')
  const [textSource, setTextSource] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileSource, setFileSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<{ url: string; kind: string } | null>(null)
  const itemKey = record.item_key
  const endpoint = target && itemKey ? `/api/rag/evidence/${target.target}/${target.target_id}/manual/${itemKey}` : ''

  useEffect(() => {
    if (!endpoint || !/^[0-9a-f]{64}$/.test(itemKey || '')) { setSaved(null); return }
    let active = true
    setSaved(null)
    void api.get<{ ok: boolean; data: ManualRecord }>(endpoint).then(response => {
      if (!active) return
      setSaved(response.data)
      setReason(response.data.reason || '')
      setAbsence(response.data.no_evidence_reason || '')
      setError('')
    }).catch(reason => { if (active) setError(reason.message || t('evidence.manualLoadFailed')) })
    return () => { active = false }
  }, [endpoint, itemKey, version, t])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url) }, [preview])

  const save = async () => {
    if (!endpoint || !version || busy) return
    setBusy(true); setError('')
    try {
      const direct = (saved?.items || []).filter(item => item.kind === 'text' && item.text)
        .map(item => ({ text: item.text!, source_description: item.source_description }))
      if (text.trim()) direct.push({ text: text.trim(), source_description: textSource.trim() })
      const response = await api.put<{ ok: boolean; data: ManualRecord }>(endpoint, {
        expected_version: version, reason, no_evidence_reason: absence, text_items: direct,
      })
      setSaved(current => ({ ...current, ...response.data, before_value: current?.before_value, after_value: current?.after_value }))
      setText(''); setTextSource('')
    } catch (reason: any) { setError(reason.message || t('evidence.manualSaveFailed')) }
    finally { setBusy(false) }
  }

  const upload = async () => {
    if (!endpoint || !version || !file || busy) return
    setBusy(true); setError('')
    try {
      const body = new FormData()
      body.append('expected_version', version)
      body.append('source_description', fileSource.trim())
      body.append('file', file)
      const response = await api.post<{ ok: boolean; data: ManualRecord }>(`${endpoint}/files`, body)
      setSaved(current => ({ ...current, ...response.data, before_value: current?.before_value, after_value: current?.after_value }))
      setFile(null); setFileSource('')
    } catch (reason: any) { setError(reason.message || t('evidence.manualUploadFailed')) }
    finally { setBusy(false) }
  }

  const showFile = async (item: ManualItem) => {
    try {
      const blob = await api.download(`${endpoint}/files/${item.id}`)
      setPreview({ url: URL.createObjectURL(blob), kind: item.kind })
    } catch (reason: any) { setError(reason.message || t('evidence.manualLoadFailed')) }
  }

  const removeItem = async (item: ManualItem) => {
    if (!endpoint || !version || busy) return
    setBusy(true); setError('')
    try {
      if (item.kind === 'text') {
        const remaining = (saved?.items || []).filter(entry => entry.kind === 'text' && entry.id !== item.id && entry.text)
          .map(entry => ({ text: entry.text!, source_description: entry.source_description }))
        await api.put(endpoint, { expected_version: version, reason, no_evidence_reason: absence, text_items: remaining })
      } else await api.del(`${endpoint}/files/${item.id}`)
      setSaved(current => current ? { ...current, items: current.items.filter(entry => entry.id !== item.id) } : current)
    } catch (reason: any) { setError(reason.message || t('evidence.manualSaveFailed')) }
    finally { setBusy(false) }
  }

  if (!saved) return error ? <Alert severity="error">{error}</Alert> : <Typography color="text.secondary">{t('evidence.noManualEdits')}</Typography>
  const previewView = preview && (preview.kind === 'image'
    ? <Box component="img" src={preview.url} alt={t('evidence.manualImage')} sx={{ maxWidth: '100%' }} />
    : <Button component="a" href={preview.url} target="_blank" rel="noopener noreferrer">{t('evidence.openManualFile')}</Button>)
  const history = saved.history || []
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
          : <Button size="small" onClick={() => void showFile(item)}>{item.filename || t('evidence.manualFile')}</Button>}
      </Box>)}
    </Box>)}
  </Box>
  if (!saved.changed) return <>{historyView || <Typography color="text.secondary">{t('evidence.noManualEdits')}</Typography>}{previewView}{error && <Alert severity="error">{error}</Alert>}</>
  return <Box sx={{ display: 'grid', gap: 1.5, mt: 1 }}>
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
      <Box><Typography variant="caption" color="text.secondary">{t('evidence.beforeEditValue')}</Typography><EvidenceReadableValue value={saved.before_value} /></Box>
      <Box><Typography variant="caption" color="text.secondary">{t('evidence.afterEditValue')}</Typography><EvidenceReadableValue value={saved.after_value} /></Box>
    </Box>
    {saved.actor_user_id && <Typography variant="caption">{saved.actor_name || t('evidence.manualContributor', { id: saved.actor_user_id })}</Typography>}
    {saved.items.map(item => <Box key={item.id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Typography variant="caption">{t('evidence.humanProvided')} · {item.source_description}</Typography>
      {item.kind === 'text' ? <EvidenceReadableValue value={item.text} />
        : <Button size="small" onClick={() => void showFile(item)}>{item.filename || t('evidence.manualFile')}</Button>}
      {saved.status === 'draft' && <Button size="small" color="error" disabled={busy} onClick={() => void removeItem(item)}>{t('evidence.removeManualItem')}</Button>}
      {item.kind === 'image' && item.ai_read_status !== 'read' && <Typography variant="caption" display="block">{t('evidence.imageNotRead')}</Typography>}
    </Box>)}
    {previewView}
    {saved.status === 'submitted' ? <>
      <Typography>{t('evidence.manualReason')}：{saved.reason}</Typography>
      {saved.no_evidence_reason && <Typography>{t('evidence.noEvidenceReason')}：{saved.no_evidence_reason}</Typography>}
    </> : <>
      <TextField fullWidth multiline minRows={2} label={t('evidence.manualReason')} value={reason} onChange={event => setReason(event.target.value)} />
      {saved.items.length === 0 && !text.trim() && <TextField fullWidth multiline minRows={2} label={t('evidence.noEvidenceReason')} value={absence} onChange={event => setAbsence(event.target.value)} />}
      <TextField fullWidth multiline minRows={2} label={t('evidence.manualText')} value={text} onChange={event => setText(event.target.value)} />
      {text && <TextField fullWidth label={t('evidence.manualSource')} value={textSource} onChange={event => setTextSource(event.target.value)} />}
      <Button size="small" variant="outlined" disabled={busy} onClick={() => void save()}>{t('evidence.saveManualEvidence')}</Button>
      <Button component="label" size="small" variant="outlined" disabled={busy}>{t('evidence.chooseManualFile')}
        <input hidden type="file" accept=".png,.jpg,.jpeg,.webp,.txt,.md" onChange={event => setFile(event.target.files?.[0] || null)} />
      </Button>
      {file && <><Typography variant="caption">{file.name}</Typography><TextField fullWidth label={t('evidence.manualSource')} value={fileSource} onChange={event => setFileSource(event.target.value)} />
        <Button size="small" disabled={busy || !fileSource.trim()} onClick={() => void upload()}>{t('evidence.uploadManualFile')}</Button></>}
    </>}
    {error && <Alert severity="error">{error}</Alert>}
    {historyView}
  </Box>
}
