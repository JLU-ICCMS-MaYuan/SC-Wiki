import { Alert, Box, Typography } from '@mui/material'

export default function AlphaIntegralHelp({ unit, evidence, manual }: {unit:string;evidence?:string;manual:boolean}) {
  const relative=unit==='pixel'||unit==='unknown'
  return <Box sx={{mt:2}} data-testid="alpha-integral-help">
    <Alert severity="info">
      <Typography fontWeight={600} variant="body2">为什么零频完成了，λ 和 ωlog 还是空的？</Typography>
      <Typography variant="body2">零频核对确认的是频率轴的 0 位置，以及曲线上对应的点；不要求该点的幅值也为 0。</Typography>
      <Typography variant="body2">{relative?'当前幅值仍是相对像素：它表示曲线离边线多少像素，还没有对应到 α²F 的真实数值。':'当前已填写幅值数值标定，仍需核对它确实属于 α²F，以及基线、频率顺序和曲线完整性。'}</Typography>
      {manual && <Typography variant="body2" data-testid="manual-integral-boundary">当前软件在人工修订后会停用旧积分，尚未自动重算人工谱。因此，即使补齐依据，保存也不会直接出现新的 λ / ωlog。</Typography>}
    </Alert>
    <details style={{marginTop:12}}>
      <summary style={{cursor:'pointer',fontSize:13}}>α²F 幅值怎么核对？查看操作步骤</summary>
      <ol style={{fontSize:13,lineHeight:1.9,paddingLeft:22}}>
        <li>查论文原图、图注或补充材料，找到明确标为 α²F 的刻度、单位或缩放系数。λ(ω) 的刻度或总值不能直接代用。</li>
        <li>若有明确依据，进入编辑器 → 右侧“坐标标定” → “幅值轴”，点选两个刻度位置并填入真实数值。例如论文明确给出 0 和 0.5，就填 0、0.5，不能照抄图中的 λ 刻度。</li>
        <li>在“幅值标定依据”写清图号/图注及对应刻度或倍率，核对单位后应用标定。只有填写说明并不代表科学审核通过。</li>
        <li>若论文没有提供独立刻度或倍率，就保留相对像素/未知；需要找到补充说明、作者原始数据或另做有依据的标定，不能为消除提示猜数字。</li>
      </ol>
      <Typography variant="body2" color="text.secondary">λ 需要绝对幅值。ωlog 是归一化的对数平均：若仅缺一个统一正倍率，且频率、零基线和完整曲线可靠，倍率可以抵消；但这不等于任意相对像素曲线都可直接计算。</Typography>
      <Typography variant="body2" color="text.secondary" sx={{mt:1}}>当前幅值依据：{evidence?.trim() || '未提供'}</Typography>
    </details>
  </Box>
}
