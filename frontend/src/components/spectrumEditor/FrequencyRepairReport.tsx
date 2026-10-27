import { useState } from 'react'
import { Alert, Box, Button, Typography } from '@mui/material'

type Location = { point_id: string; x: number; y: number; shift_px: number }
export type FrequencyRepairReportData = { curve_id: string; name: string; point_count: number; new_point_count: number; max_shift_px: number; points: Location[]; skipped: { reason: string }[] }
export default function FrequencyRepairReport({reports,onLocate,disabled=false}:{
  reports: FrequencyRepairReportData[];onLocate?:(curve:string,point:string)=>void;disabled?:boolean
}){
  const [page,setPage]=useState(0)
  const active=reports.filter(r=>r.point_count||r.skipped.length)
  if(!active.length)return null
  const points=active.flatMap(r=>r.points.map(p=>({...p,curve_id:r.curve_id,name:r.name})))
  const count=Math.ceil(points.length/12),current=Math.min(page,Math.max(0,count-1))
  const reasons=[...new Set(active.flatMap(r=>r.skipped.map(s=>r.name+'：'+s.reason)))]
  const maxShift=active.reduce((m,r)=>Math.max(m,r.max_shift_px),0)
  return <Box sx={{mt:2}} data-testid="frequency-repair-report">
    {points.length>0&&<Alert severity="info">
      自动频率微调：当前 {points.length} 个点，最大移动 {Number(maxShift.toFixed(8))} 原图像素（每点上限 0.5）。
      <Typography variant="caption" display="block">青色点为自动修正，幅值和连线保持；本次新增修正 {active.reduce((n,r)=>n+r.new_point_count,0)} 个点。点击定位后可在编辑器撤销，保存后生效；这不代表科学准确性已验证。</Typography>
    </Alert>}
    {points.slice(current*12,(current+1)*12).map(p=><Button key={p.curve_id+':'+p.point_id} size="small" disabled={!onLocate||disabled} onClick={()=>onLocate?.(p.curve_id,p.point_id)}>
      {p.name} · ({Number(p.x.toFixed(8))}, {Number(p.y.toFixed(8))}) · 移动 {Number(p.shift_px.toFixed(8))} px
    </Button>)}
    {count>1&&<Box><Button disabled={current===0} onClick={()=>setPage(current-1)}>上一页</Button>{current+1} / {count}<Button disabled={current+1>=count} onClick={()=>setPage(current+1)}>下一页</Button></Box>}
    {reasons.map(reason=><Typography key={reason} variant="body2" color="text.secondary" sx={{mt:1}}>未自动修正：{reason}；对应点保持原样。</Typography>)}
  </Box>
}
