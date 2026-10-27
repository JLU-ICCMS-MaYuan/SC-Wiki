import { useState } from 'react'
import { Box, Button, Typography } from '@mui/material'

type Location = { point_id: string; frequency_thz: number | null; amplitude: number | null; x: number | null; y: number | null }
type Issue = { kind: string; message: string; points: Location[] }
export type TraceReport = { curves: { curve_id: string; name: string; amplitude_unit: string; component_count: number; point_count: number; issues: Issue[] }[] }
const number = (value: number | null) => value != null && Number.isFinite(value) ? Number(value.toFixed(6)).toString() : '未知'
const names: Record<string, string> = { disconnected:'未连接片段', isolated:'孤立点', cycle:'闭环', branch:'分叉', invalid:'连接无效',negative_amplitude:'负幅值',negative_frequency:'负频率',nonfinite_sample:'缺少有效数值',duplicate_frequency:'频率重复',frequency_backtrack:'频率回折' }

export default function TraceDiagnostics({report, onLocate, disabled=false}: {
  report: TraceReport; onLocate?: (curveId:string,pointId:string)=>void; disabled?:boolean
}) {
  const [page,setPage]=useState(0)
  const issues=report.curves.flatMap(curve=>curve.issues.filter(issue=>!['high_endpoint','projection_range','low_endpoint','zero_confirmation','nonzero_zero'].includes(issue.kind)).map(issue=>({curve,issue})))
  if(!issues.length)return null
  const count=Math.ceil(issues.length/12),current=Math.min(page,count-1)
  return <Box sx={{mt:2}} data-testid="trace-diagnostics">
    <Typography fontWeight={600}>需要检查的位置（{issues.length}项）</Typography>
    <Typography variant="caption" color="text.secondary">点击坐标定位并选中原图中的点；由你决定删除或重新描线。</Typography>
    {issues.slice(current*12,(current+1)*12).map(({curve,issue},i)=><Box key={current*12+i} sx={{mt:1,p:1,border:1,borderColor:'divider',borderRadius:1}} data-issue-kind={issue.kind}>
      <Typography variant="body2" fontWeight={600}>{curve.name} · {names[issue.kind]||issue.kind}</Typography>
      <Typography variant="body2" color="text.secondary">{issue.message}</Typography>
      {issue.points.map(point=>{
        const located=point.x!=null && point.y!=null
        const label=`原图 (x=${number(point.x)}, y=${number(point.y)}) px`
        return <Box key={point.point_id} sx={{mt:.5}}>
          <Button size="small" sx={{textTransform:'none',textAlign:'left',overflowWrap:'anywhere',maxWidth:'100%'}}
            data-diagnostic-point={point.point_id} data-diagnostic-curve={curve.curve_id}
            disabled={disabled||!onLocate||!located} onClick={()=>onLocate?.(curve.curve_id,point.point_id)}>{label}</Button>
          <Typography variant="caption" display="block">频率 {number(point.frequency_thz)} THz · 幅值 {number(point.amplitude)} {curve.amplitude_unit==='pixel'?'相对像素':curve.amplitude_unit}</Typography>
          {!located && <Typography variant="caption">缺少原图坐标，暂不能定位该点。</Typography>}
        </Box>
      })}
    </Box>)}
    {count>1 && <Box sx={{display:'flex',alignItems:'center',gap:1,mt:1}}>
      <Button disabled={current===0} onClick={()=>setPage(current-1)}>上一页</Button>
      <Typography variant="caption">{current+1} / {count}</Typography>
      <Button disabled={current+1===count} onClick={()=>setPage(current+1)}>下一页</Button>
    </Box>}
  </Box>
}
