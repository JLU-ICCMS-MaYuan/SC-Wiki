import { Box, Typography } from '@mui/material'

type Location = { point_id: string; x: number; y: number; shift_px: number }
export type FrequencyRepairReportData = { curve_id: string; name: string; point_count: number; new_point_count: number; max_shift_px: number; points: Location[]; skipped: { reason: string }[] }

/** 修正点已成为当前结果；详情只保留尚未处理的问题。 */
export default function FrequencyRepairReport({reports}:{reports: FrequencyRepairReportData[]}){
  const reasons=[...new Set(reports.flatMap(r=>r.skipped.map(s=>r.name+'：'+s.reason)))]
  if(!reasons.length)return null
  return <Box sx={{mt:2}} data-testid="frequency-repair-errors">
    {reasons.map(reason=><Typography key={reason} variant="body2" color="text.secondary" sx={{mt:1}}>未自动修正：{reason}；对应点保持原样。</Typography>)}
  </Box>
}
