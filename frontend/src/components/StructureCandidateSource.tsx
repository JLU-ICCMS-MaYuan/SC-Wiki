import { Alert, Box, Typography } from '@mui/material'
import type { StructureCandidate } from '../lib/paperProcessing'

export function StructureRoundingNotice({ candidate }: { candidate: StructureCandidate }) {
  const adjustments = candidate.derivation?.rounding_adjustments
  if (!Array.isArray(adjustments) || !adjustments.length) return null
  const vector = (values: unknown[]) => values.map(value => typeof value === 'number' ? Number(value.toPrecision(8)) : String(value)).join(', ')
  return <Alert severity="info" sx={{ mt: 1, overflowWrap: 'anywhere' }}>
    此模型包含按原文小数精度恢复对称约束的派生坐标；原始坐标和改变量已保留，请结合来源核对。
    <Box component="details" sx={{ mt: 1 }}>
      <Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>查看坐标舍入处理</Typography>
      {adjustments.filter(item => item && Array.isArray(item.reported_coordinates) && Array.isArray(item.derived_coordinates) && Array.isArray(item.rounding_half_width)).map((item, index) =>
        <Typography key={index} variant="caption" component="div">{String(item.site)}：({vector(item.reported_coordinates)}) → ({vector(item.derived_coordinates)})；原文舍入半宽 ({vector(item.rounding_half_width)})</Typography>)}
    </Box>
  </Alert>
}

/** 失败候选也能核对已提取参数和逐页引句，不把空模型当作空数据。 */
export default function StructureCandidateSource({ candidate, showModelStatus = true }: { candidate: StructureCandidate; showModelStatus?: boolean }) {
  const reported = candidate.reported_structure
  const identity = [reported?.material, reported?.space_group_symbol,
    reported?.pressure_value_gpa != null ? `${reported.pressure_value_gpa} GPa` : null].filter(Boolean).map(String).join(' · ')
  const cells = reported?.cell_parameters || candidate.validation?.cell_parameters || {}
  return <Box sx={{ mt: 1, minWidth: 0 }}>
    {identity && <Typography variant="body2">{identity}</Typography>}
    <StructureRoundingNotice candidate={candidate} />
    <Box component="details">
      <Typography component="summary" variant="caption" sx={{ cursor: 'pointer' }}>查看结构来源与已提取参数</Typography>
      {!!Object.keys(cells).length && <Typography variant="caption" display="block" sx={{ my: 1 }}>
        {Object.entries(cells).map(([key, value]) => `${key} = ${value}`).join('，')}
      </Typography>}
      {showModelStatus && !candidate.representations?.conventional?.cif?.text && <Typography variant="caption" display="block">尚未生成通过校验的三维结构；以下为原文依据。</Typography>}
      {(candidate.sources || []).map((source, index) => <Box key={index} sx={{ my: 1 }}>
        <Typography variant="caption" color="text.secondary">{String(source.filename || '来源文件')} · 第 {String(source.page ?? '未知')} 页</Typography>
        {typeof source.quote === 'string' && <Typography component="blockquote" variant="caption" sx={{ m: 0, mt: .5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 300, overflowY: 'auto' }}>{source.quote}</Typography>}
      </Box>)}
    </Box>
  </Box>
}
