import { Box, Chip, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'

const number=(value:unknown,digits=6)=>typeof value==='number'&&Number.isFinite(value)?Number(value.toPrecision(digits)).toString():'—'
export default function AlphaRelativeMetrics({raw,comparison,restricted}: {raw:any;comparison:any;restricted:boolean}) {
  const current=raw.method==='alpha2f-relative-v2'
  const omega=current?raw.parameters?.omega_log:undefined
  const normalization=current?raw.normalization||{}:{}
  const available=!restricted&&omega?.status==='available'
  const paper=!restricted?comparison?.reference:undefined
  const comparable=available&&comparison?.status==='available'
  return <Box data-testid="alpha-relative-metrics">
    <Box sx={{overflowX:'auto'}}>
      <Table size="small" sx={{minWidth:560}}><TableHead><TableRow>
        {['参数','提取谱计算值','论文参考值','绝对偏差','相对偏差（%）'].map(v=><TableCell key={v}>{v}</TableCell>)}
      </TableRow></TableHead><TableBody><TableRow>
        <TableCell>ωlog（K）</TableCell><TableCell>{available?number(omega.value):'—'}</TableCell>
        <TableCell>{number(paper)}</TableCell><TableCell>{comparable?number(comparison.absolute_difference):'—'}</TableCell>
        <TableCell>{comparable?comparison.relative_difference_pct==null?'不适用（参考为0）':number(comparison.relative_difference_pct):'—'}</TableCell>
      </TableRow></TableBody></Table>
    </Box>
    <Box sx={{mt:2,p:1.5,border:1,borderColor:'divider',borderRadius:1}} data-testid="alpha-normalization">
      <Typography fontWeight={600} variant="body2">幅值归一化</Typography>
      <Box sx={{display:'grid',gridTemplateColumns:{xs:'1fr',sm:'repeat(3,minmax(0,1fr))'},gap:2,mt:1}}>
        {[
          ['论文 λ（归一化输入）',restricted?'—':number(normalization.lambda_reference)],
          ['像素加权积分',restricted?'—':number(raw.pixel_integral)],
          ['幅值系数 C',restricted?'—':number(normalization.coefficient)],
        ].map(([label,value])=><Box key={label}><Typography color="text.secondary" variant="caption">{label}</Typography><Typography fontWeight={600}>{value}</Typography></Box>)}
      </Box>
      {!restricted&&normalization.source&&<Typography variant="caption" color="text.secondary" display="block" sx={{mt:1}}>λ参考：{normalization.source.source_name||'当前论文'}{normalization.source.page_start||normalization.source.page?' · 第 '+(normalization.source.page_start||normalization.source.page)+' 页':''}</Typography>}
      {!restricted&&normalization.status==='available'&&<Chip size="small" label="依据论文 λ 归一化" sx={{mt:1}}/>}
      {!restricted&&current&&!raw.reason&&normalization.status!=='available'&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>{normalization.reason||'暂不能确定C'}</Typography>}
    </Box>
    {!restricted&&current&&<Typography variant="caption" color="text.secondary" display="block" sx={{mt:1}}>ωlog偏差只作谱形参考；λ用于归一化，不作独立准确度校验。</Typography>}
    {!restricted&&!current&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>请点击重新计算，独立计算ωlog并按论文λ生成幅值倍率。</Typography>}
    {!restricted&&current&&(raw.reason||omega?.status!=='available')&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>{raw.reason||omega?.reason}</Typography>}
    {!restricted&&current&&available&&!comparable&&<Typography variant="body2" color="text.secondary" sx={{mt:1}}>{comparison?.reason||'未提供同条件论文ωlog，计算值仍可查看。'}</Typography>}
  </Box>
}
