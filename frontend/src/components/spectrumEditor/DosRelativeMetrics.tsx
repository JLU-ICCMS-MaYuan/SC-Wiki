import { Box, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'

type Status = { status: string; reason?: string }
type Component = Status & { curve_id: string; projection: string; area?: number; frequency_interval_thz?: number[] }
type ElementRatio = Status & { elements?: string[]; estimated_ratio?: number[]; expected_ratio?: number[]; reference_element?: string; reference_label?: string; formula?: string; max_share_difference_pp?: number }
export type DosRelativeReport = {
  method: string
  components: Component[]
  shares: Status & { total_area?: number; fractions?: Record<string, number>; expected_fractions?: Record<string, number>; expected_reason?: string; coverage_note?: string; element_ratio?: ElementRatio }
  normalization: Status & {
    coefficient?: number; primitive_atoms?: number; target_modes?: number; total_mode_integral?: number
    component_mode_integrals?: Record<string, number>; expected_modes?: Record<string, number>
    deviations?: Record<string, { absolute_difference: number; relative_difference_pct: number }>
  }
}
const number = (v: unknown, digits = 5) => typeof v === 'number' && Number.isFinite(v) ? Number(v.toPrecision(digits)).toString() : '—'
const percent = (v: number | undefined) => v == null ? '—' : number(v * 100, 4)+'%'

export default function DosRelativeMetrics({ report, restricted }: { report?: DosRelativeReport; restricted: boolean }) {
  if (restricted) return <Typography color="text.secondary" sx={{my:1}}>当前为历史、失效或限定频段版本，不展示完整谱计算结果。</Typography>
  if (report?.method !== 'dos-relative-v1') return <Typography color="text.secondary" sx={{my:1}}>请点击重新计算，查看相对面积与按 3N 归一化结果。</Typography>
  const { components, shares, normalization: norm } = report
  const comparable = shares.status === 'available', normalized = norm.status === 'available'
  const ratio = shares.element_ratio
  return <Box data-testid="dos-relative-metrics" sx={{mt:2}}>
    <Typography fontWeight={600}>相对面积与元素占比</Typography>
    <Typography variant="caption" color="text.secondary">面积单位：像素·THz；表示相对面积，不是振动模式数。</Typography>
    <Box sx={{overflowX:'auto',maxWidth:'100%'}}>
      <Table size="small" aria-label="DOS 相对面积" sx={{minWidth:430}}>
        <TableHead><TableRow>{['元素 / 积分范围','相对面积','面积占比','原子数占比'].map(s=><TableCell key={s}>{s}</TableCell>)}</TableRow></TableHead>
        <TableBody>{components.map(c=><TableRow key={c.curve_id}>
          <TableCell>{c.projection}{c.frequency_interval_thz&&<Typography variant="caption" display="block">{c.frequency_interval_thz.map(v=>number(v)).join('–')} THz</Typography>}</TableCell>
          <TableCell>{c.status==='available'?number(c.area):'—'}{c.reason&&<Typography variant="caption" display="block" color="text.secondary">{c.reason}</Typography>}</TableCell>
          <TableCell>{comparable?percent(shares.fractions?.[c.curve_id]):'—'}</TableCell>
          <TableCell>{comparable?percent(shares.expected_fractions?.[c.curve_id]):'—'}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </Box>
    {comparable&&<Typography variant="body2" sx={{mt:1}}>全部分波相对面积：{number(shares.total_area)} 像素·THz</Typography>}
    {comparable&&ratio?.status==='available'&&<Box data-testid="dos-element-ratio" sx={{mt:2}}>
      <Typography fontWeight={600}>面积推算的近似元素比</Typography>
      <Typography variant="body2">元素顺序：{ratio.elements?.join(' : ')}（以 {ratio.reference_element} = 1）</Typography>
      <Typography variant="body2">面积估计：{ratio.estimated_ratio?.map(v=>number(v,4)).join(' : ')}</Typography>
      <Typography variant="body2">{ratio.reference_label}{ratio.formula?'（'+ratio.formula+'）':''}：{ratio.expected_ratio?.map(v=>number(v,4)).join(' : ')}</Typography>
      <Typography variant="body2">最大原子占比差：{number(ratio.max_share_difference_pp,4)} 个百分点</Typography>
      <Typography variant="caption" color="text.secondary">占比差越小，比例越接近；不设自动通过阈值，也不把小数强行凑成整数。</Typography>
    </Box>}
    {comparable&&ratio?.reason&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>{ratio.reason}</Typography>}
    {shares.coverage_note&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>{shares.coverage_note}</Typography>}
    {[shares.reason,shares.expected_reason].filter(Boolean).map(reason=><Typography key={reason} variant="body2" color="text.secondary" sx={{mt:1}}>{reason}</Typography>)}
    <Box data-testid="dos-normalization" sx={{mt:2}}>
      <Typography fontWeight={600}>按 3N 归一化</Typography>
      {normalized ? <>
        <Typography variant="body2" sx={{my:1}}>共同系数 C：{number(norm.coefficient,7)} · 总模式数：{number(norm.total_mode_integral)}（目标 3N：{number(norm.target_modes)}）</Typography>
        <Typography variant="caption" color="text.secondary">所有元素共用一个系数；总和等于 3N 是归一化条件，不代表提取准确性已验证。密度单位：模式数 / THz / 原胞。</Typography>
        <Box sx={{overflowX:'auto',maxWidth:'100%'}}>
          <Table size="small" aria-label="DOS 归一化模式积分" sx={{minWidth:450}}>
            <TableHead><TableRow>{['元素','模式积分','预期 3Nₛ','绝对偏差','相对偏差'].map(s=><TableCell key={s}>{s}</TableCell>)}</TableRow></TableHead>
            <TableBody>{components.map(c=><TableRow key={c.curve_id}>
              <TableCell>{c.projection}</TableCell>
              <TableCell>{number(norm.component_mode_integrals?.[c.curve_id])}</TableCell>
              <TableCell>{number(norm.expected_modes?.[c.curve_id])}</TableCell>
              <TableCell>{number(norm.deviations?.[c.curve_id]?.absolute_difference)}</TableCell>
              <TableCell>{norm.deviations?.[c.curve_id]?number(norm.deviations[c.curve_id].relative_difference_pct,4)+'%':'—'}</TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </Box>
      </> : <Typography variant="body2" color="text.secondary" sx={{mt:1}}>{norm.reason || '归一化条件尚待核对'}</Typography>}
    </Box>
  </Box>
}
