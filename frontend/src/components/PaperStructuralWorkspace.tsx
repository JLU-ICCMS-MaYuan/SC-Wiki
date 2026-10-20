import { useState } from 'react'
import { Alert, Box, Button, Card, MenuItem, TextField, Typography } from '@mui/material'
import type { StructureCandidate } from '../lib/paperProcessing'
import type { LatticeObservation } from '../lib/structuralRecords'
import StructuralRecordView from './StructuralRecordView'

interface Props {
  candidates: StructureCandidate[]; observations: LatticeObservation[]
  onCandidates: (values: StructureCandidate[]) => void; onObservations: (values: LatticeObservation[]) => void
  onReextract?: () => Promise<any>; onApplyPreview?: (value: any) => void
  readOnly?: boolean; issues?: Array<{ reason: string; page?: number }>
}

export default function PaperStructuralWorkspace({ candidates, observations, onCandidates, onObservations, onReextract, onApplyPreview, readOnly = false, issues = [] }: Props) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [preview, setPreview] = useState<any>(null)
  const [cells, setCells] = useState<Record<string, 'primitive' | 'conventional'>>({})
  const download = (value: any, format: string, cell = 'conventional') => {
    const text = format === 'json' ? JSON.stringify(value, null, 2) : value.representations?.[cell]?.[format]?.text
    if (!text) return
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `structure-${value.candidate_id || value.record_key}.${format}`; link.click(); URL.revokeObjectURL(url)
  }
  const reextract = async () => {
    if (!onReextract) return
    setBusy(true); setError(''); setPreview(null)
    try { setPreview(await onReextract()) } catch (e: any) { setError(e.message || '结构资料重提取失败') }
    finally { setBusy(false) }
  }
  return <Box sx={{ mt: 3, minWidth: 0 }} data-testid="paper-structural-workspace">
    <Typography variant="h6">论文结构资料</Typography>
    <Typography variant="body2" color="text.secondary">保留本文提供的结构和几何参数。完整结构即使没有 Tc、尚未关联材料状态，也可以保存、查看和导出。</Typography>
    {!readOnly && <Typography variant="caption" color="text.secondary">“保留”决定随主表单一起保存。待核对资料可在提交后继续内部核对，只有明确保留且论文当前版本审核通过后才进入公开结构检索。</Typography>}
    {!readOnly && onReextract && <Button disabled={busy} onClick={() => void reextract()}>{busy ? '正在读取原始附件…' : '重新读取结构资料'}</Button>}
    {error && <Alert severity="error">{error}</Alert>}
    {preview && <Alert severity="info" sx={{ my: 1 }}>
      原附件重提取预览：{preview.structure_candidates.length} 个模型候选，{preview.structural_observations.length} 条晶格观测；{preview.structural_extraction_issues.length} 项需核对。未调用模型，尚未更改表单。
      <Button onClick={() => { try { onApplyPreview?.(preview); setPreview(null) } catch (e: any) { setError(e.message) } }}>应用预览到表单</Button>
      <Button onClick={() => setPreview(null)}>取消</Button>
    </Alert>}
    {issues.map((issue, index) => <Alert key={index} severity="warning">第 {issue.page ?? '未知'} 页：{issue.reason}</Alert>)}
    {!candidates.length && !observations.length && <Typography variant="body2" sx={{ my: 2 }}>暂无独立结构资料。可读取原始附件，核对完整模型与部分几何参数。</Typography>}
    {candidates.map((candidate, index) => {
      const reported = candidate.reported_structure || {}, retained = candidate.retention || 'pending', cell = cells[candidate.candidate_id] || 'conventional'
      return <Card variant="outlined" key={candidate.candidate_id} sx={{ p: 2, my: 1, minWidth: 0 }}>
        <Typography fontWeight={700}>{String(reported.material || '结构候选')} · {String(reported.space_group_symbol || '空间群待核对')} · {String(reported.pressure_value_gpa ?? '压力待核对')} {reported.pressure_value_gpa != null ? 'GPa' : ''}</Typography>
        <Typography variant="caption">{retained === 'retained' ? '已选择保留' : retained === 'excluded' ? '不保留' : '待核对'} · {String(candidate.material_state_ref || '').startsWith('unassigned:') ? '尚未关联材料状态' : '已有材料状态关联'}</Typography>
        {candidate.status === 'blocked' && <Alert severity="warning">{candidate.validation?.message || '尚不能构造可靠模型'}</Alert>}
        {candidate.status !== 'blocked' && <TextField select size="small" label="晶胞表示" value={cell} onChange={event => setCells({ ...cells, [candidate.candidate_id]: event.target.value as typeof cell })} sx={{ minWidth: 140, my: 1 }}><MenuItem value="conventional">惯用胞</MenuItem><MenuItem value="primitive">原胞</MenuItem></TextField>}
        <StructuralRecordView item={{ id: candidate.candidate_id, kind: 'model', material: String(reported.material || ''), data: candidate }} cell={cell} />
        {candidate.status !== 'blocked' && <Box sx={{ mt: 1 }}>
          {!readOnly && <Button onClick={() => onCandidates(candidates.map((c, i) => i === index ? { ...c, retention: 'retained' } : c))}>保留此结构</Button>}
          <Button onClick={() => download(candidate, 'cif', cell)}>下载 CIF</Button><Button onClick={() => download(candidate, 'poscar', cell)}>下载 POSCAR</Button>
        </Box>}
        {!readOnly && <Button onClick={() => onCandidates(candidates.map((c, i) => i === index ? { ...c, retention: retained === 'excluded' ? 'pending' : 'excluded' } : c))}>{retained === 'excluded' ? '恢复待核对' : '不保留'}</Button>}
      </Card>
    })}
    {!!observations.length && <Typography variant="subtitle1" sx={{ mt: 2 }}>晶格与几何参数 · {observations.length} 条</Typography>}
    {observations.map((value, index) => <Card key={value.record_key} variant="outlined" sx={{ p: 2, my: 1, minWidth: 0 }}>
      <Typography fontWeight={700}>{value.material} · {value.pressure_value_gpa ?? '未知'} GPa · {value.space_group_symbol}</Typography>
      <Typography variant="caption">{value.retention === 'retained' ? '已选择保留' : value.retention === 'excluded' ? '不保留' : '待核对'}</Typography>
      <StructuralRecordView item={{ id: value.record_key, kind: 'lattice', material: value.material, data: value }} />
      {!readOnly && <><Button onClick={() => onObservations(observations.map((r, i) => i === index ? { ...r, retention: 'retained' } : r))}>保留这条参数</Button><Button onClick={() => onObservations(observations.map((r, i) => i === index ? { ...r, retention: r.retention === 'excluded' ? 'pending' : 'excluded' } : r))}>{value.retention === 'excluded' ? '恢复待核对' : '不保留'}</Button></>}
      <Button onClick={() => download(value, 'json')}>下载 JSON</Button>
    </Card>)}
  </Box>
}
