import { Box, Typography } from '@mui/material'
import type { EvidenceRecord } from './EvidenceWorkflow'
import { useLanguage } from '../context/LanguageContext'

/** 来源结论是当前字段的说明，不进入主表单的输入错误通道。 */
export default function EvidenceReviewSummary({ record }: { record: EvidenceRecord }) {
  const { t } = useLanguage()
  if (record.settings_part && record.settings_part !== 'raw' && record.current_value == null) return <Typography variant="body2" color="text.secondary">使用系统默认显示设置，无需科学核对。</Typography>
  if (record.pending_review || record.stale) return <Box data-evidence-review-summary sx={{ my: 1.5 }}>
    <Typography variant="body2" fontWeight={600}>待提交检查</Typography>
    <Typography variant="body2" color="text.secondary">已保存修改；下方理由属于上次内容。</Typography>
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
