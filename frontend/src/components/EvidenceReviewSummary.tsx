import { Box, Typography } from '@mui/material'
import type { EvidenceRecord } from './EvidenceWorkflow'
import { useLanguage } from '../context/LanguageContext'
import { evidenceStatus, evidenceStatusLabel } from '../lib/evidenceStatus'

/** 来源结论是当前字段的说明，不进入主表单的输入错误通道。 */
export default function EvidenceReviewSummary({ record, readOnly = false }: { record: EvidenceRecord; readOnly?: boolean }) {
  const { t } = useLanguage()
  const decision = record.field_decision
  if (decision && !record.pending_review && !record.stale) return <Box data-evidence-review-summary sx={{my: 1.5}}>
    <Typography fontWeight={600}>{t(decision.action === 'approve' ? 'evidence.humanApprove' : 'evidence.humanReject')}</Typography>
    <Typography variant="body2">{decision.actor_name || `#${decision.actor_user_id}`} · {new Date(decision.occurred_at).toLocaleString()}</Typography>
  </Box>
  if (record.settings_part && record.settings_part !== 'raw' && record.current_value == null) return <Typography variant="body2" color="text.secondary">使用系统默认显示设置，无需科学核对。</Typography>
  if (record.required === false && !record.human_modified && decision?.action !== 'reject') return <Typography variant="body2" color="text.secondary">此字段无需审核，不阻止提交。</Typography>
  const state = evidenceStatus(record)
  if (state !== 'passed') return <Box data-evidence-review-summary data-evidence-status={state} sx={{ my: 1.5 }}>
    <Typography variant="body2" fontWeight={600}>{evidenceStatusLabel[state]}</Typography>
    {(record.stale || record.pending_review && record.status !== 'unchecked') && <Typography variant="body2" color="text.secondary">当前内容待核对；以下为已有版本的核对意见。</Typography>}
    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>{state === 'processing'
      ? '正在处理当前字段，暂时无需人工操作。'
      : record.review_failure_message || record.reason || (record.human_modified ? '当前修改尚未完成核对。' : '当前内容尚无有效核对结论，请查看依据后处理。')}</Typography>
    {state === 'failed' && <Typography variant="body2" color="text.secondary">{readOnly ? '当前为只读，请由有编辑权限的经手人重试。' : '输入已保留；可点击“大模型核对”重试当前字段。'}</Typography>}
  </Box>
  const status = record.human_confirmed ? 'human' : record.stale ? 'stale'
    : record.required === false && record.current_value == null ? 'unreported' : record.status
  const summary = record.human_confirmed ? t('evidence.humanConfirmed')
    : record.status === 'unchecked' ? t('evidence.uncheckedHint') : record.reason
  return <Box data-evidence-review-summary sx={{ my: 1.5 }}>
    <Typography variant="body2" fontWeight={600}>{t(`evidence.reviewStatus.${status}`)}</Typography>
    {record.stale && <Typography variant="body2" color="text.secondary">{t('evidence.staleResult')}</Typography>}
    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', mt: .5 }}>
      {summary}
    </Typography>
    {record.reason && record.reason !== summary && <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{record.reason}</Typography>}
  </Box>
}
