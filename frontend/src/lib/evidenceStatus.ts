import type { EvidenceRecord } from '../components/EvidenceWorkflow'

export type EvidenceStatus = 'passed' | 'processing' | 'attention' | 'failed'

/** 展示状态不授予审核资格；待核对不等于模型正在执行。 */
export function evidenceStatus(record: EvidenceRecord): EvidenceStatus {
  if (record.review_in_progress) return 'processing'
  const rejected = record.field_decision?.action === 'reject'
  if (record.required === false && !record.human_modified && !rejected) return 'passed'
  if (record.status === 'supported' && !record.stale && !record.pending_review && !rejected) return 'passed'
  if (record.review_error || record.status === 'unchecked'
      && /技术失败|核对失败|补查失败|超时|返回缺少|响应格式/.test(record.reason || '')) return 'failed'
  return 'attention'
}

export const evidenceStatusLabel: Record<EvidenceStatus, string> = {
  passed: '已通过', processing: '处理中', attention: '待核对', failed: '处理失败',
}
