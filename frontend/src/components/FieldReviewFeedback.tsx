import { Box, Button, LinearProgress, Typography } from '@mui/material'
import type { EvidenceRecord } from './EvidenceWorkflow'
import { useLanguage } from '../context/LanguageContext'

export interface ReviewActivity { stage: string; message: string; tool?: string; file_id?: string; page?: number; summary?: string }
export interface FieldReviewProgress {
  phase: 'checking' | 'countdown' | 'running' | 'completed' | 'error' | 'cancelled'
  percent?: number; message?: string; activity?: ReviewActivity; activity_log?: ReviewActivity[]; elapsed: number
}

/** 只解释现有资格和本次操作，不在前端产生科学通过结论。 */
export function fieldReviewVerdict(record: EvidenceRecord) {
  if (record.review_error && record.status !== 'supported') return 'failed'
  if (record.human_confirmed && record.field_decision?.mode === 'without_evidence' && !record.local_modified
      && !record.stale && (!record.pending_review || record.manual_pending)) return 'waived'
  if (record.local_modified || record.manual_pending || record.stale) return 'pending'
  if (record.human_confirmed && record.field_decision?.mode === 'empty' && !record.pending_review) return 'passed'
  if (record.required === false && !record.human_modified && record.field_decision?.action !== 'reject') return 'exempt'
  if (record.status === 'supported' && !record.pending_review && record.field_decision?.action !== 'reject') return 'passed'
  if (['unsupported', 'uncertain', 'missing'].includes(record.status) || record.field_decision?.action === 'reject') return 'rejected'
  return 'pending'
}

export default function FieldReviewFeedback({record, progress, onCancel, onRetry}: {
  record: EvidenceRecord; progress?: FieldReviewProgress; onCancel: () => void; onRetry: () => void
}) {
  const { t } = useLanguage()
  if (progress && !['error', 'cancelled'].includes(progress.phase)) return <Box data-field-review-progress sx={{display:'grid',gap:1}}>
    <Typography role="status">{progress.activity?.message || progress.message || t('evidence.running')}</Typography>
    <LinearProgress aria-label={t('evidence.progressLabel')} variant="determinate" value={progress.percent || 0}/>
    {Boolean(progress.activity_log?.length) && <Box component="ol" aria-label={t('evidence.reviewTrace')} sx={{my:0,pl:2.5}}>
      {progress.activity_log!.map((item,index)=><Typography component="li" variant="body2" key={index}>{item.message}</Typography>)}
    </Box>}
    {progress.activity?.summary && <Typography>{t('evidence.reviewSummary')}：{progress.activity.summary}</Typography>}
    <Typography variant="caption">{t('evidence.elapsed',{minutes:Math.floor(progress.elapsed/60),seconds:progress.elapsed%60})}</Typography>
    <Button onClick={onCancel}>{t('common.cancel')}</Button>
  </Box>
  const verdict=fieldReviewVerdict(record)
  if (progress?.phase === 'error' || progress?.phase === 'cancelled') return <Box data-field-review-result={progress.phase} sx={{display:'grid',gap:1}}>
    <Typography role="status" fontWeight={600}>{progress.phase === 'cancelled' ? t('evidence.reviewCancelled') : t('evidence.reviewIncomplete')}</Typography>
    {progress.message && <Typography>{progress.message}</Typography>}
    <Button onClick={onRetry}>{t('evidence.retry')}</Button>
  </Box>
  const labels={waived:'evidence.waivedPassed',passed:'evidence.reviewPassed',rejected:'evidence.reviewRejected',failed:'evidence.reviewIncomplete',pending:'evidence.reviewPending',exempt:'evidence.reviewExempt'} as const
  return <Typography role="status" data-field-review-result={verdict} fontWeight={600}
    color={['failed','rejected'].includes(verdict)?'error.main':verdict==='waived'?'warning.main':verdict==='passed'?'success.main':'text.secondary'} sx={{mb:1}}>
    {t(verdict === 'passed' && record.field_decision?.mode === 'empty' ? 'evidence.emptyHumanPassed' : labels[verdict])}
  </Typography>
}
