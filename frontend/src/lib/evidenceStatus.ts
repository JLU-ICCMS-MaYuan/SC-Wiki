import type { EvidenceRecord } from '../components/EvidenceWorkflow'

export type EvidenceStatus = 'passed' | 'processing' | 'attention' | 'failed' | 'waived'

/** 展示状态不授予审核资格；待核对不等于模型正在执行。 */
function resultStatus(record: EvidenceRecord): EvidenceStatus {
  const rejected = record.field_decision?.action === 'reject'
  if (record.review_error && record.status !== 'supported') return 'failed'
  const waived = record.field_decision?.mode === 'without_evidence' && record.status==='supported'
    && !record.stale && !record.local_modified && (!record.pending_review || record.manual_pending) && record.human_confirmed
  if (record.local_modified || record.manual_pending) return waived ? 'waived' : 'attention'
  if (waived) return 'waived'
  if (record.field_decision?.mode === 'empty' && (record.stale || record.pending_review)) return 'attention'
  if (record.required === false && !record.human_modified && !rejected) return 'passed'
  if (record.status === 'supported' && !record.stale && !record.pending_review && !rejected) return 'passed'
  if (record.review_error || record.status === 'unchecked'
      && /技术失败|核对失败|补查失败|超时|返回缺少|响应格式/.test(record.reason || '')) return 'failed'
  return 'attention'
}

export function evidenceStatus(record: EvidenceRecord): EvidenceStatus {
  return record.review_in_progress ? 'processing' : resultStatus(record)
}

/** 进度不是消红资格；仍有问题时保留字段提醒。 */
export function evidenceNeedsAttention(record: EvidenceRecord): boolean {
  return ['attention', 'failed'].includes(resultStatus(record))
}

export const evidenceStatusLabel: Record<EvidenceStatus, string> = {
  waived: '人工通过，未提供证据', passed: '已通过', processing: '处理中', attention: '待核对', failed: '处理失败',
}
