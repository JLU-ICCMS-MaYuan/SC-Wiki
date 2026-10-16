import { Alert, Box, Button, Typography } from '@mui/material'
import { dosSourceGroups, hasDosConflict } from '../lib/fermiDos'
import type { PropertyRecordDraft } from '../lib/propertyModules'
import type { EvidenceRecord, EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'
import { EvidenceRegion } from './EvidenceRegion'

export function dosRecordForEvidence(record: EvidenceRecord): PropertyRecordDraft | undefined {
  const value = record.current_value as { record?: PropertyRecordDraft } | PropertyRecordDraft | undefined
  if (!value || typeof value !== 'object') return
  const candidate = ('record' in value ? value.record : value) as PropertyRecordDraft | undefined
  if (!candidate || candidate.property_code !== 'dos_fermi') return
  return { ...candidate, module_code: record.module_code || candidate.module_code || 'electronic_properties' } as PropertyRecordDraft
}

export default function DosFermiConflict({ record, target, onEdit }: {
  record: EvidenceRecord; target?: EvidenceTarget; onEdit?: () => void
}) {
  const dos = dosRecordForEvidence(record)
  if (!dos || !hasDosConflict(dos)) return null
  const state = (record.current_value as { state?: Record<string, unknown> })?.state
  const humanConfirmed = !record.stale && record.human_confirmed
  return <Box data-dos-conflict-sources sx={{ my: 1.5 }}>
    <Alert severity={humanConfirmed ? 'info' : 'warning'}>{humanConfirmed
      ? '来源仍有差异；当前值已完成人工核对。原始报告及人工依据继续保留。'
      : '发现不同 DOS 数值，待人工核对。请对照单位、条件及原文，再返回主表单决定。'}</Alert>
    {dosSourceGroups(dos).map((source, index) => {
      const evidences = (source.evidences || []).map(item => {
        const reference = typeof item === 'number' ? { paper_evidence_id: item } : item as { paper_evidence_id?: number; id?: number }
        const id = reference?.paper_evidence_id ?? reference?.id
        return id == null ? item : record.evidences.find(evidence => evidence.paper_evidence_id === id) || item
      }).filter(item => Boolean(item) && typeof item === 'object') as EvidenceSource[]
      const conditions = source.payload?.calculation_conditions || source.payload?.experimental_conditions
      return <Box key={index} data-dos-source-candidate sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, my: 1 }}>
        <Typography fontWeight={600} sx={{ overflowWrap: 'anywhere' }}>来源候选 {index + 1} · {source.value_raw} {source.unit_raw || '单位未说明'}</Typography>
        {state && <Typography variant="caption" color="text.secondary">
          {[state.material_name || state.material, state.pressure_value_gpa != null ? String(state.pressure_value_gpa) + ' GPa' : '压强未说明'].filter(Boolean).join(' · ')}
        </Typography>}
        {Boolean(conditions) && <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
          条件：{Object.entries(conditions as Record<string, unknown>).filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value)).map(([key, value]) => key + '：' + String(value)).join('；') || '见对应原文'}
        </Typography>}
        {!evidences.length && <Alert severity="info" sx={{ mt: 1 }}>此候选缺少可核验的出处，不能据此认定数值正确。</Alert>}
        {evidences.map((evidence, sourceIndex) => evidence.file_id && evidence.quote
          ? <EvidenceRegion key={sourceIndex} target={target} source={evidence} />
          : <Box key={sourceIndex} sx={{ mt: 1 }}>
              <Typography variant="caption">{evidence.source_name || evidence.file_id || '来源文件未说明'} · {evidence.page_start != null ? '第 ' + evidence.page_start + ' 页' : '原文位置未说明'}</Typography>
              {evidence.quote && <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{evidence.quote}</Typography>}
              <Typography variant="caption" color="text.secondary">来源信息不完整，需人工核验。</Typography>
            </Box>)}
      </Box>
    })}
    {onEdit && <Button onClick={onEdit}>返回主表单修改</Button>}
    <Typography variant="caption" display="block" color="text.secondary">来源仅供对照。编辑或保存说明不会自动消除这些差异。</Typography>
  </Box>
}
