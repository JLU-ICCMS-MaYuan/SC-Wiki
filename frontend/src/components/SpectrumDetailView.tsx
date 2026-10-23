import { useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Slider, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import SpectrumFigure from './SpectrumFigure'
import SpectrumViewSwitch from './SpectrumViewSwitch'
import { spectrumCurveColor } from '../lib/spectrumGeometry'
import { spectrumInterval, spectrumNames } from '../lib/propertySpectra'

export const spectrumNumber = (value: unknown, digits = 4) => typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(digits)).toString() : '—'
const pointStatus = (status: string, detection?: string) => detection === 'ambiguous_components' ? '多条轨迹，待核对' : detection === 'unsupported_chromatic' ? '彩边证据不足，待核对' : status === 'observed' ? '原图提取' : spectrumNames[status] || status
const unitName = (unit: string) => unit === 'dimensionless' || unit === '1' ? '无量纲' : unit === 'pixel' ? '相对幅值（像素）' : unit === 'unknown' ? '单位待核对' : unit
const boxStyle = { p: { xs: 2, md: 2.5 }, mb: 2, borderRadius: 2, minWidth: 0 }

export function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <Paper variant="outlined" sx={boxStyle}><Typography variant="h6" sx={{ fontSize: 17, mb: 2 }}>{title}</Typography>{children}</Paper>
}

export function SpectrumResult({ item, curves, image, retryImage }: { item: Item; curves: Curve[]; image: string; retryImage: () => void }) {
  const [mode, setMode] = useState('data'), [projection, setProjection] = useState('all'), [opacity, setOpacity] = useState(.85)
  const dos = curves[0]?.kind === 'phonon_dos'
  const selected = projection === 'all' ? curves : curves.filter(c => c.id === projection)
  return <DetailSection title="02 · 原图与提取结果">
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
      {dos ? <TextField select size="small" label="分波态密度" value={projection} onChange={e => setProjection(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="all">全部分波</MenuItem>{curves.map(c => <MenuItem key={c.id} value={c.id}>仅 {c.projection || c.id}</MenuItem>)}
      </TextField> : <Typography variant="body2" color="text.secondary">保持来源图的轴向与幅值尺度。</Typography>}
      <SpectrumViewSwitch value={mode} onChange={setMode} />
    </Box>
    <SpectrumFigure item={item} curves={selected} allCurves={curves} image={image} mode={mode} opacity={opacity} />
    {curves[0]?.kind === 'alpha2f' && mode !== 'source' && <Typography variant="caption" sx={{ color: spectrumCurveColor(curves[0], 0) }}>红线：α²F 提取数据</Typography>}
    {mode === 'overlay' && <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}><Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>叠加强度</Typography><Slider aria-label="叠加强度" min={0} max={1} step={.05} value={opacity} onChange={(_, value) => setOpacity(value as number)} sx={{ maxWidth: 220 }} /><Typography variant="caption">{Math.round(opacity * 100)}%</Typography></Box>}
    {curves.some(c => c.kind === 'alpha2f' && !item.result.calibration?.curves?.find((value: { id: string; amplitude_evidence?: string }) => value.id === c.id)?.amplitude_evidence) && <Alert severity="info" sx={{ mt: 1 }}>此版本的 α²F 幅值标定尚待核对，显示旧提取记录不代表其刻度已确认。</Alert>}
    {mode !== 'data' && !image && <Button onClick={retryImage}>重新读取原图</Button>}
    {dos && <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>{selected.map((c, i) => <Typography key={c.id} variant="caption" sx={{ color: spectrumCurveColor(c, i) }}>{c.projection || c.id}</Typography>)}</Box>}
  </DetailSection>
}

export function SpectrumMetrics({ item, curves, history }: { item: Item; curves: Curve[]; history: boolean }) {
  const dos = curves[0]?.kind === 'phonon_dos', q = item.result.quality || {}, raw = q.integrals?.raw || {}, comparisons = q.comparisons?.raw || {}
  const alpha = curves.find(c => c.kind === 'alpha2f')
  const zeroCovered = curves.length > 0 && curves.every(c => c.points[0]?.frequency_thz === 0 && c.points[0]?.observed_amplitude != null)
  const alphaCal = item.result.calibration?.curves?.find((c: { id: string }) => c.id === alpha?.id)
  const alphaReason = !alpha ? '当前没有 α²F 数据' : item.review[alpha.id]?.status === 'accepted_limited' ? '当前只采纳限定频段，不能用整次运行积分代替该频段结果' : !alphaCal?.amplitude_evidence ? 'α²F 独立幅值刻度依据尚待核对，旧 λ 刻度不能代用' : raw.status === 'unavailable' ? raw.reason : !zeroCovered ? '当前结果未覆盖真实零频边界，请核对后重新提取' : raw.positive_frequency_complete === false ? '存在缺口，无法计算完整积分' : ''
  const mode = q.dos_mode_integral || { status: 'unavailable', reason: '此版本没有原始绝对 DOS 模式数核验；请核对单位、原胞及完整投影' }
  const modeAvailable = mode.status === 'available' && !item.stale && !history
  return <DetailSection title={dos ? '03 · 频段与数据完整性' : '03 · 积分结果与参考值对比'}>
    <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 2 }}><Box><Typography variant="caption" color="text.secondary">实际提取频率范围</Typography><Typography fontWeight={600}>{spectrumInterval(curves)}</Typography></Box>
      <Box><Typography variant="caption" color="text.secondary">{dos ? '原胞原子数 N / 目标 3N' : '实际积分范围'}</Typography><Typography fontWeight={600}>{dos ? `${spectrumNumber(mode.primitive_atoms, 0)} / ${spectrumNumber(mode.target_modes, 0)}` : !alphaReason && raw.minimum_integrated_thz != null ? `${spectrumNumber(raw.minimum_integrated_thz)}–${spectrumNumber(alpha?.points.at(-1)?.frequency_thz)} THz` : '暂不可计算'}</Typography></Box></Box>
    {!zeroCovered && <Alert severity="warning" sx={{ mb: 2 }}>零频提取不完整：必须从原图的真实 0 频率边界提取，不能改标签或补造零点。</Alert>}
    <Box sx={{ overflowX: 'auto' }}><Table size="small" sx={{ minWidth: 540 }}><TableHead><TableRow>{(dos ? ['全部分波积分', '目标 3N', '绝对偏差', '相对偏差（%）'] : ['参数', '提取谱积分值', '论文参考值', '绝对偏差']).map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
      {dos ? <TableRow><TableCell>{modeAvailable ? spectrumNumber(mode.integral) : '—'}</TableCell><TableCell>{item.stale || history ? '—' : spectrumNumber(mode.target_modes)}</TableCell><TableCell>{modeAvailable ? spectrumNumber(mode.absolute_difference) : '—'}</TableCell><TableCell>{modeAvailable && mode.relative_difference_pct != null ? spectrumNumber(mode.relative_difference_pct, 2) + '%' : '—'}</TableCell></TableRow>
        : [['λ', 'lambda', 'lambda_integral'], ['ωlog（K）', 'omega_log', 'omega_log_k']].map(([label, key, field]) => {
          const c = comparisons[key] || {}, comparable = !alphaReason && !item.stale && !history && c.status === 'available'
          return <TableRow key={key}><TableCell>{label}</TableCell><TableCell>{alphaReason ? '—' : spectrumNumber(raw[field])}</TableCell><TableCell>{comparable ? spectrumNumber(c.reference) : '—'}</TableCell><TableCell>{comparable ? spectrumNumber(c.absolute_difference) : '—'}</TableCell></TableRow>
        })}
    </TableBody></Table></Box>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>{dos ? item.stale || history ? '材料条件已变化或正在查看历史，当前 3N 对比不可用。' : mode.reason || '绝对偏差 = |全部分波积分 − 3N|；相对偏差 = 绝对偏差 / |3N| × 100%。只核验原始绝对密度，不用归一化候选自证。' : alphaReason || (item.stale || history ? '材料条件已变化或正在查看历史，论文参考对比不可用。' : '绝对偏差 = |积分值 − 同条件论文报告值|。缺少同条件参考时显示“—”。')}</Typography>
    {!dos && !alphaReason && !item.stale && !history && ['lambda', 'omega_log'].map(key => comparisons[key]?.source && <Typography variant="caption" display="block" key={key}>参考来源：{typeof comparisons[key].source === 'string' ? comparisons[key].source : JSON.stringify(comparisons[key].source)}</Typography>)}
  </DetailSection>
}

export function SpectrumPoints({ curves }: { curves: Curve[] }) {
  const [search, setSearch] = useState('')
  const rows = curves.flatMap(curve => curve.points.map((point, i) => ({ curve, point, i }))).filter(row => !search || String(row.point.frequency_thz).includes(search))
  return <DetailSection title="04 · 逐点数据核对">
    <TextField size="small" label="查找频率" value={search} onChange={event => setSearch(event.target.value)} sx={{ mb: 2 }} />
    <Box role="region" aria-label="可滚动的逐点数据表" tabIndex={0} sx={{ maxWidth: 1180, height: { xs: 300, md: 330 }, overflow: 'auto', border: 1, borderColor: 'divider', borderRadius: 1 }}>
      <Table stickyHeader size="small" sx={{ minWidth: 760 }}><TableHead><TableRow>{['曲线 / 单位', '频率 / THz', '原图提取', '提取数据（含重建）', '幅值绝对差', '数据状态'].map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
        {rows.map(({ curve, point, i }) => <TableRow key={`${curve.id}-${i}`}><TableCell>{curve.projection || spectrumNames[curve.kind]} / {unitName(curve.unit)}</TableCell><TableCell>{spectrumNumber(point.frequency_thz, 7)}</TableCell><TableCell>{spectrumNumber(point.observed_amplitude, 7)}</TableCell><TableCell>{spectrumNumber(point.reconstructed_amplitude, 7)}</TableCell><TableCell>{point.observed_amplitude != null && point.reconstructed_amplitude != null ? spectrumNumber(Math.abs(point.reconstructed_amplitude - point.observed_amplitude), 7) : '—'}</TableCell><TableCell>{pointStatus(point.status, point.detection_mode)}</TableCell></TableRow>)}
      </TableBody></Table>{!rows.length && <Typography sx={{ p: 2 }}>没有匹配的数据点</Typography>}
    </Box><Typography variant="caption" color="text.secondary">{rows.length} 点 · 数据状态说明点的来源，不表示已审核通过。</Typography>
  </DetailSection>
}
