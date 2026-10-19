import { useState } from 'react'
import { Box, MenuItem, TextField, Typography } from '@mui/material'
import type { EvidenceRecord, EvidenceHistory } from './EvidenceWorkflow'
import type { ManualRecord } from '../lib/manualEvidenceDrafts'
import { useLanguage } from '../context/LanguageContext'
import EvidenceReadableValue from './EvidenceReadableValue'

export interface AuditEvent { id: string; actor?: { kind?: string; name?: string; user_id?: number; model?: string }; occurred_at?: string
  kind?: string; summary?: string; reason?: string; before_value?: unknown; after_value?: unknown; before_settings?: unknown; after_settings?: unknown; legacy_scope?: string }
export default function EvidenceHistoryTimeline({ record, manual }: { record: EvidenceRecord; manual: ManualRecord[] }) {
  const { t, lang } = useLanguage(), [sort, setSort] = useState('desc')
  const events: AuditEvent[] = [...(record.audit_events || [])]
  const legacyRecords = (record.history || []).filter(entry => entry.legacy_scope === 'record')
  for (const [index, entry] of (record.history || []).entries()) {
    if (entry.legacy_scope === 'record') continue
    if (entry.audit_events?.length && !entry.legacy_scope) events.push(...entry.audit_events)
    else events.push({ id: `legacy:${index}`, legacy_scope: entry.legacy_scope, summary: t('evidence.legacyHistory'), reason: entry.ai_reason || entry.reason,
      before_value: undefined, after_value: entry.current_value })
  }
  for (const entry of manual) events.push({ id: 'manual:' + entry.id, actor: { kind: 'human', user_id: entry.actor_user_id, name: entry.actor_name },
    occurred_at: entry.created_at, kind: 'manual_note', summary: t('evidence.savedManualNote'), reason: entry.reason,
    before_value: entry.before_value, after_value: entry.after_value })
  const unique = events.filter((event, i, all) => all.findIndex(e => e.id === event.id) === i)
  const hasTime = (event: AuditEvent) => Boolean(event.occurred_at && /(?:Z|[+-]\d\d:\d\d)$/.test(event.occurred_at) && Number.isFinite(Date.parse(event.occurred_at)))
  const known = unique.filter(hasTime).sort((a, b) => (Date.parse(a.occurred_at!) - Date.parse(b.occurred_at!)) * (sort === 'asc' ? 1 : -1))
  const unknown = unique.filter(e => !hasTime(e))
  const actor = (event: AuditEvent) => event.actor?.kind === 'ai' ? `AI · ${event.actor.model || t('evidence.actorUnknown')}`
    : event.actor?.name || (event.actor?.user_id ? t('evidence.actorId', { id: event.actor.user_id }) : t('evidence.actorUnknown'))
  const scalar = (value: unknown) => value == null || ['number', 'string', 'boolean'].includes(typeof value)
  const short = (value: unknown) => value == null || value === '' ? '—' : String(value).slice(0, 100)
  const row = (event: AuditEvent) => <Box component="article" key={event.id} sx={{ borderLeft: 2, borderColor: 'divider', pl: 2, pb: 2, ml: .5 }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
      <Typography variant="caption" fontWeight={600}>{actor(event)}</Typography>
      <Typography component="time" variant="caption" color="text.secondary">{hasTime(event)
        ? new Date(event.occurred_at!).toLocaleString(lang === 'en' ? 'en-GB' : 'zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) + ' (UTC+8)'
        : event.occurred_at ? event.occurred_at + ' · ' + t('evidence.timezoneUnknown') : t('evidence.timeUnknown')}</Typography>
    </Box>
    <Typography variant="body2">{event.summary}</Typography>
    {event.before_value !== undefined && scalar(event.before_value) && scalar(event.after_value) && <Typography variant="caption" sx={{ display: 'block', overflowWrap: 'anywhere' }}>
      {short(event.before_value)} → {short(event.after_value)}
    </Typography>}
    {event.legacy_scope && <Typography variant="caption" color="text.secondary">{t('evidence.legacyRecordScope')}</Typography>}
    <Box component="details" sx={{ mt: .5 }}><Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>{t('evidence.historyDetails')}</Typography>
      {event.before_value !== undefined && <><Typography variant="caption">{t('evidence.beforeValue')}</Typography><EvidenceReadableValue value={event.before_value} /></>}
      {event.after_value !== undefined && <><Typography variant="caption">{t('evidence.afterValue')}</Typography><EvidenceReadableValue value={event.after_value} /></>}
      {event.after_settings !== undefined && <><Typography variant="caption">{t('evidence.settingsTab')}</Typography>
        <EvidenceReadableValue value={{ [t('evidence.beforeValue')]: event.before_settings, [t('evidence.afterValue')]: event.after_settings }} /></>}
      {event.reason && <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{event.reason}</Typography>}
    </Box>
  </Box>
  return <Box>
    <TextField size="small" select label={t('evidence.historyOrder')} value={sort} onChange={event => setSort(event.target.value)} sx={{ my: 1, minWidth: 140 }}>
      <MenuItem value="desc">{t('evidence.newestFirst')}</MenuItem><MenuItem value="asc">{t('evidence.oldestFirst')}</MenuItem>
    </TextField>
    {!unique.length && <Typography color="text.secondary">{t('evidence.noFieldHistory')}</Typography>}
    {known.map(row)}
    {unknown.length > 0 && <><Typography variant="caption" color="text.secondary" component="p">{t('evidence.unknownTimeGroup')}</Typography>{unknown.map(row)}</>}
    {legacyRecords.length > 0 && <Box component="details" sx={{ my: 1 }}>
      <Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>{t('evidence.legacyRecordScope')}（{legacyRecords.length}）</Typography>
      {legacyRecords.map((entry, index) => <Box key={index} sx={{ mt: 1 }}><EvidenceReadableValue value={entry.current_value} />
        <Typography variant="caption">{entry.reason}</Typography>
      </Box>)}
    </Box>}
  </Box>
}
