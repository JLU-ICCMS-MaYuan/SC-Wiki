import React, { useMemo, useState } from 'react'
import { Alert, Box, Button, Chip, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { EvidenceRegion } from './EvidenceRegion'
import type { EvidenceTarget } from './EvidenceWorkflow'
import { groupParsingDifferences, type ParsingSnapshot, type ParsingDifference, type TriageStatus } from '../lib/parsingDiagnostics'

interface Props { snapshot: ParsingSnapshot; paper: object; target?: EvidenceTarget }
const text = (value: unknown) => typeof value === 'string' ? value : JSON.stringify(value) ?? '—'
const same = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b)
const fieldValue = (paper: object, field: string) => (paper as Record<string, unknown>)[field]
const titleKey = (value: unknown) => String(value || '').replace(/<[^>]*>/g, '').toLocaleLowerCase().replace(/[^\p{L}\p{N}_]/gu, '')
const doiKey = (value: unknown) => String(value || '').trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').toLowerCase()
const currentCheck = (item: ParsingSnapshot['bibliography'][number], paper: object) =>
  same(item.triage?.checked_value, fieldValue(paper, item.field)) && (item.field !== 'year'
    || ((!item.triage?.evidence?.doi || doiKey(item.triage.evidence.doi) === doiKey(fieldValue(paper, 'doi')))
      && (!item.triage?.evidence?.title || titleKey(item.triage.evidence.title) === titleKey(fieldValue(paper, 'title')))))

function RegionDetails({ item, target }: { item: ParsingDifference; target?: EvidenceTarget }) {
  const { t } = useLanguage()
  const [raw, setRaw] = useState(false)
  const triage = item.triage
  return <Box sx={{ borderTop: 1, borderColor: 'divider', mt: 1, pt: 1 }} data-diagnostic-region={triage?.id || item.selected}>
    <EvidenceRegion target={target} hideQuote source={{ file_id: item.file_id, source_name: triage?.filename || t('upload.diagnosticSource'),
      page_start: item.pdf_page, block_id: item.selected, quote: item.selected_text }} />
    <Typography variant="body2">{t(`upload.diagnosticReasons.${triage?.reason || 'unclassified'}`)}</Typography>
    {!!triage?.evidence?.text_layer_match && <Typography variant="body2">{t(`upload.diagnosticTextMatch.${triage.evidence.text_layer_match}`)}</Typography>}
    <Typography variant="caption" component="p">{t('upload.diagnosticImpactScope')}</Typography>
    {triage?.impact?.references.length ? triage.impact.references.map(ref =>
      <Chip key={`${ref.state_key}:${ref.record_key || ref.kind}`} size="small" label={ref.label} sx={{ mr: .5, my: .5 }} />)
      : <Typography variant="body2">{t('upload.diagnosticUnmapped')}</Typography>}
    {triage?.differences?.map((difference, index) => <Box key={index} sx={{ bgcolor: 'action.hover', p: 1, my: 1 }}>
      <Typography variant="body2">{t('upload.diagnosticSelected')}：{difference.selected || '∅'}</Typography>
      <Typography variant="body2">{t('upload.diagnosticAlternative')}：{difference.alternative || '∅'}</Typography>
    </Box>)}
    {!!triage?.difference_count && triage.difference_count > (triage.differences?.length || 0) &&
      <Typography variant="caption">{t('upload.diagnosticMoreChanges', { count: triage.difference_count })}</Typography>}
    <Button size="small" onClick={() => setRaw(value => !value)}>{t(raw ? 'upload.diagnosticHideRaw' : 'upload.diagnosticRaw')}</Button>
    {raw && <Box sx={{ maxHeight: 380, overflow: 'auto' }}>
      <Typography fontWeight={600}>{t('upload.diagnosticSelected')} · {item.engine}</Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.selected_text}</Typography>
      {item.alternatives.map((alternative, index) => <Box key={alternative.block_id || `${alternative.engine}:${index}`} sx={{ mt: 1 }}>
        <Typography fontWeight={600}>{t('upload.diagnosticAlternative')} · {alternative.engine}</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{alternative.text}</Typography>
      </Box>)}
    </Box>}
  </Box>
}
const StableRegionDetails = React.memo(RegionDetails)

function ParsingDiagnosticsPanel({ snapshot, paper, target }: Props) {
  const { t } = useLanguage()
  const [opened, setOpened] = useState<string | null>(null)
  const [all, setAll] = useState(false)
  const [bibliographyOpen, setBibliographyOpen] = useState<string | null>(null)
  const stableTarget = useMemo(() => target, [target?.target, target?.target_id])
  const groups = useMemo(() => groupParsingDifferences(snapshot.regions).map(([category, items]) => ({ category, items,
    representative: items.find(item => item.triage?.status !== 'system_checked' && item.triage?.impact?.references.length)
      || items.find(item => item.triage?.status !== 'system_checked') || items[0],
    checked: items.filter(item => item.triage?.status === 'system_checked').length,
  })), [snapshot.regions])
  const regionCounts = useMemo(() => {
    const counts = { system_checked: 0, system_pending: 0, user_review: 0 }
    for (const item of snapshot.regions) counts[item.triage?.status || 'system_pending']++
    return counts
  }, [snapshot.regions])
  const bibliographyStatus = (item: ParsingSnapshot['bibliography'][number]): TriageStatus =>
    item.triage?.status === 'system_checked' && !currentCheck(item, paper)
      ? 'system_pending' : item.triage?.status || 'system_pending'
  const counts = { ...regionCounts }
  for (const item of snapshot.bibliography) counts[bibliographyStatus(item)]++
  if (!snapshot.regions.length && !snapshot.bibliography.length) return null
  return <Box sx={{ mb: 2 }} data-parsing-diagnostics>
    <Alert severity={counts.user_review ? 'warning' : 'info'}>
      <Typography fontWeight={600}>{t('upload.diagnosticTitle')}</Typography>
      <Typography variant="body2">{t('upload.diagnosticScope', { regions: snapshot.regions.length, bibliography: snapshot.bibliography.length })}</Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
        {(['system_checked', 'system_pending', 'user_review'] as const).map(status =>
          <Chip key={status} size="small" label={`${t(`upload.diagnosticStatus.${status}`)}：${counts[status]}`} />)}
      </Box>
      <Typography variant="body2" sx={{ mt: 1 }}>{t('upload.diagnosticResponsibility')}</Typography>
    </Alert>
    {snapshot.bibliography.length > 0 && <Box sx={{ mt: 1 }}>
      <Typography fontWeight={600}>{t('upload.diagnosticBibliography')}</Typography>
      {snapshot.bibliography.map(item => <Box key={item.triage?.id || item.field} sx={{ p: 1, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="body2">{t(`upload.diagnosticFields.${item.field}`)} · {t(`upload.diagnosticStatus.${bibliographyStatus(item)}`)}</Typography>
        <Typography variant="body2">{t('upload.diagnosticCurrent')}：{text(fieldValue(paper, item.field)).slice(0, 160)}{text(fieldValue(paper, item.field)).length > 160 ? '…' : ''}</Typography>
        <Typography variant="caption" component="p">{t(`upload.diagnosticReasons.${item.triage?.reason || 'bibliography_check_needed'}`)}</Typography>
        {item.triage?.status === 'system_checked' && !currentCheck(item, paper) &&
          <Typography color="warning.main" variant="body2">{t('upload.diagnosticValueChanged')}</Typography>}
        {item.triage?.evidence?.url?.startsWith('https://api.crossref.org/works/') &&
          <a href={item.triage.evidence.url} target="_blank" rel="noreferrer">{t('upload.diagnosticAuthority')}</a>}
        <Button size="small" onClick={event => {
          const field = event.currentTarget.closest('[data-evidence-scope]')?.querySelector(`[data-issue-field="${CSS.escape(`paper.${item.field}`)}"]`)
          field?.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }}>{t('upload.diagnosticGoField')}</Button>
        <Button size="small" onClick={() => setBibliographyOpen(bibliographyOpen === item.field ? null : item.field)}>{t('upload.diagnosticRaw')}</Button>
        {bibliographyOpen === item.field && <Box>
          <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>GROBID：{text(item.grobid_value)}</Typography>
          <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{t('upload.extractedCandidate')}：{text(item.extracted_value)}</Typography>
        </Box>}
      </Box>)}
    </Box>}
    {groups.map(({ category, items, representative, checked }) => {
      return <Box key={category} sx={{ mt: 1, p: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
        <Typography fontWeight={600}>{t(`upload.diagnosticCategories.${category}`)} · {items.length}</Typography>
        <Typography variant="body2">{t('upload.diagnosticGroupCount', { checked, pending: items.length - checked })}</Typography>
        <Button size="small" onClick={() => { setOpened(opened === category ? null : category); setAll(false) }}>
          {t(opened === category ? 'upload.diagnosticCollapse' : 'upload.diagnosticExample')}</Button>
        {opened === category && <>
          <StableRegionDetails key={representative.triage?.id || representative.selected} item={representative} target={stableTarget} />
          {items.length > 1 && <Button size="small" onClick={() => setAll(value => !value)}>{t(all ? 'upload.diagnosticOnlyExample' : 'upload.diagnosticAll')}</Button>}
          {all && items.filter(item => item !== representative).map(item =>
            <StableRegionDetails key={item.triage?.id || `${item.file_id}:${item.selected}:${item.pdf_page}`} item={item} target={stableTarget} />)}
        </>}
      </Box>
    })}
  </Box>
}

// 来源快照只由外部加载更新；仅比较题录真正依赖的当前字段，不遍历整张科学表单。
export default React.memo(ParsingDiagnosticsPanel, (a, b) => a.snapshot === b.snapshot
  && a.target?.target === b.target?.target && a.target?.target_id === b.target?.target_id
  && a.snapshot.bibliography.every(item => same(fieldValue(a.paper, item.field), fieldValue(b.paper, item.field))
    && currentCheck(item, a.paper) === currentCheck(item, b.paper)))
