import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import { spectrumInterval, spectrumNames } from '../lib/propertySpectra'

export const spectrumNumber = (value: unknown, digits = 4) => typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(digits)).toString() : '—'
const colors = ['#6155d9', '#d25693', '#38a477', '#c88c35', '#2385bb']
const projectionColors: Record<string, string> = { La: colors[0], Sc: colors[1], H: colors[2] }
const curveColor = (curve: Curve, index: number) => projectionColors[curve.projection || ''] || colors[index % colors.length]
const unitName = (unit: string) => unit === 'dimensionless' || unit === '1' ? '无量纲' : unit === 'pixel' ? '相对幅值（像素）' : unit === 'unknown' ? '单位待核对' : unit
const boxStyle = { p: { xs: 2, md: 2.5 }, mb: 2, borderRadius: 2, minWidth: 0 }

export function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <Paper variant="outlined" sx={boxStyle}><Typography variant="h6" sx={{ fontSize: 17, mb: 2 }}>{title}</Typography>{children}</Paper>
}

function pathFor(curve: Curve, position: (f: number, a: number, pixel?: number) => [number, number] | null) {
  let path = '', open = false
  for (const point of curve.points) {
    const a = point.reconstructed_amplitude
    const xy = a != null && Number.isFinite(a) ? position(point.frequency_thz, a, point.frequency_pixel) : null
    if (!xy || !xy.every(Number.isFinite)) { open = false; continue }
    path += `${open ? 'L' : 'M'}${xy[0]},${xy[1]} `; open = true
  }
  return path
}

function SpectrumFigure({ item, curves, image, mode }: { item: Item; curves: Curve[]; image: string; mode: string }) {
  const plotRef = useRef<SVGSVGElement | null>(null), [width, setWidth] = useState(800)
  useEffect(() => {
    const parent = plotRef.current?.parentElement
    if (!parent || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(entries => setWidth(Math.max(240, Math.min(800, entries[0].contentRect.width))))
    observer.observe(parent)
    return () => observer.disconnect()
  }, [mode])
  const curve = curves[0], direction = curve?.frequency_direction
  if (mode !== 'data') {
    if (!image) return <Typography color="text.secondary">原图正在读取或暂不可用；可重试读取。</Typography>
    const size = item.source.size_px
    if (!size || size.length !== 2) return <Box component="img" src={image} alt="论文谱原图" sx={{ maxWidth: '100%', maxHeight: 600 }} />
    const overlayAvailable = curves.every(value => value.axis_calibration?.amplitude && value.frequency_direction && value.points.every(p => p.frequency_pixel != null))
    return <>
      {mode === 'overlay' && !overlayAvailable && <Alert severity="info">缺少原图像素标定，暂不能准确叠加。</Alert>}
      <Box component="svg" role="img" aria-label={mode === 'source' ? '论文谱原图' : '原图与提取数据叠加'} viewBox={`0 0 ${size[0]} ${size[1]}`} sx={{ width: '100%', maxHeight: 600, display: 'block' }}>
        <image href={image} width={size[0]} height={size[1]} />
        {mode === 'overlay' && overlayAvailable && curves.map((value, i) => <path key={value.id} d={pathFor(value, (_f, a, pixel) => {
          const axis = value.axis_calibration!.amplitude
          if (!axis.slope || pixel == null) return null
          const amp = (a - axis.intercept) / axis.slope
          return value.frequency_direction === 'y' ? [amp, pixel] : [pixel, amp]
        })} stroke={curveColor(value, i)} strokeWidth={2} strokeDasharray="6 4" fill="none" />)}
      </Box>
      <Typography variant="caption" color="text.secondary">{mode === 'overlay' ? '虚线为提取数据回绘，原图保持不变。原图中其他分波不会被擦除。' : '来源原图保持原有坐标与图例。'}</Typography>
    </>
  }
  if (!curve || !direction) return <Alert severity="info">缺少来源图轴向，暂不猜测坐标方向。请核对标定。</Alert>
  const frequencies = curves.flatMap(c => c.points.map(p => p.frequency_thz)).filter(Number.isFinite)
  const amplitudes = curves.flatMap(c => c.points.map(p => p.reconstructed_amplitude)).filter((v): v is number => v != null && Number.isFinite(v))
  if (!frequencies.length || !amplitudes.length) return <Alert severity="info">当前选择没有可绘制的有效数据。</Alert>
  if (curves.some(c => c.frequency_direction !== direction || c.unit !== curve.unit)) return <Alert severity="warning">分波轴向或单位不一致，不能共用坐标显示。</Alert>
  const maxF = Math.max(...frequencies), maxA = Math.max(...amplitudes, 0.001)
  // 保留源图坐标正向；竖轴频率和横轴频率都不能仅凭惯例翻转。
  const fSlope = curve.axis_calibration?.frequency.slope ?? (direction === 'y' ? -1 : 1)
  const aSlope = curve.axis_calibration?.amplitude.slope ?? (direction === 'y' ? 1 : -1)
  const axis = (ratio: number, horizontal: boolean, slope: number) => horizontal ? 65 + (width - 90) * (slope > 0 ? ratio : 1 - ratio) : 340 - 300 * (slope < 0 ? ratio : 1 - ratio)
  const position = (f: number, a: number): [number, number] => direction === 'y'
    ? [axis(a / maxA, true, aSlope), axis(f / (maxF || 1), false, fSlope)]
    : [axis(f / (maxF || 1), true, fSlope), axis(a / maxA, false, aSlope)]
  const amplitudeLabel = `${curve.kind === 'alpha2f' ? 'α²F' : curve.kind === 'cumulative_lambda' ? '累计 λ' : 'DOS'} / ${unitName(curve.unit)}`
  return <Box component="svg" ref={plotRef} role="img" aria-label={`提取谱数据，频率沿${direction === 'y' ? '竖轴' : '横轴'}，与来源图一致`} viewBox={`0 0 ${width} 400`} sx={{ width: '100%', display: 'block' }}>
    <path d={`M65 40V340H${width - 25}`} stroke="#94a3b8" fill="none" />
    {Array.from({ length: 6 }, (_, i) => {
      const f = i * maxF / 5, a = i * maxA / 5
      const fp = direction === 'y' ? position(f, 0)[1] : position(f, 0)[0]
      const ap = direction === 'y' ? position(0, a)[0] : position(0, a)[1]
      return <g key={i} fontSize={13} fill="#64748b">
        <text x={direction === 'y' ? 5 : fp - 8} y={direction === 'y' ? fp + 4 : 362}>{spectrumNumber(f, 2)}</text>
        <text x={direction === 'y' ? ap - 10 : 5} y={direction === 'y' ? 362 : ap + 4}>{spectrumNumber(a, 2)}</text>
      </g>
    })}
    {curves.map((value, i) => <path key={value.id} d={pathFor(value, position)} stroke={curveColor(value, i)} strokeWidth={2} fill="none" />)}
    <text x="65" y="20" fontSize={14}>{direction === 'y' ? '频率 / THz' : amplitudeLabel}</text>
    <text x={width / 2} y="391" textAnchor="middle" fontSize={12}>{direction === 'y' ? amplitudeLabel : '频率 / THz'}</text>
  </Box>
}

export function SpectrumResult({ item, curves, image, retryImage }: { item: Item; curves: Curve[]; image: string; retryImage: () => void }) {
  const [mode, setMode] = useState('data'), [projection, setProjection] = useState('all')
  const dos = curves[0]?.kind === 'phonon_dos'
  const selected = projection === 'all' ? curves : curves.filter(c => c.id === projection)
  return <DetailSection title="02 · 原图与提取结果">
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
      {dos ? <TextField select size="small" label="分波态密度" value={projection} onChange={e => setProjection(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="all">全部分波</MenuItem>{curves.map(c => <MenuItem key={c.id} value={c.id}>仅 {c.projection || c.id}</MenuItem>)}
      </TextField> : <Typography variant="body2" color="text.secondary">保持来源图的轴向与幅值尺度。</Typography>}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', ml: 'auto', gap: 0.5 }}>{[['source', '仅原图'], ['data', '仅提取数据'], ['overlay', '原图与数据叠加']].map(([value, label]) => <Button key={value} size="small" variant={mode === value ? 'contained' : 'outlined'} aria-pressed={mode === value} onClick={() => setMode(value)}>{label}</Button>)}</Box>
    </Box>
    <Box sx={{ maxWidth: 900, mx: 'auto', overflowX: 'auto' }}><SpectrumFigure item={item} curves={selected} image={image} mode={mode} /></Box>
    {curves.some(c => c.kind === 'alpha2f' && !item.result.calibration?.curves?.find((value: { id: string; amplitude_evidence?: string }) => value.id === c.id)?.amplitude_evidence) && <Alert severity="info" sx={{ mt: 1 }}>此版本的 α²F 幅值标定尚待核对，显示旧提取记录不代表其刻度已确认。</Alert>}
    {mode !== 'data' && !image && <Button onClick={retryImage}>重新读取原图</Button>}
    {dos && <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>{selected.map((c, i) => <Typography key={c.id} variant="caption" sx={{ color: curveColor(c, i) }}>{c.projection || c.id}</Typography>)}</Box>}
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
        {rows.map(({ curve, point, i }) => <TableRow key={`${curve.id}-${i}`}><TableCell>{curve.projection || spectrumNames[curve.kind]} / {unitName(curve.unit)}</TableCell><TableCell>{spectrumNumber(point.frequency_thz, 7)}</TableCell><TableCell>{spectrumNumber(point.observed_amplitude, 7)}</TableCell><TableCell>{spectrumNumber(point.reconstructed_amplitude, 7)}</TableCell><TableCell>{point.observed_amplitude != null && point.reconstructed_amplitude != null ? spectrumNumber(Math.abs(point.reconstructed_amplitude - point.observed_amplitude), 7) : '—'}</TableCell><TableCell>{point.status === 'observed' ? '原图提取' : spectrumNames[point.status] || point.status}</TableCell></TableRow>)}
      </TableBody></Table>{!rows.length && <Typography sx={{ p: 2 }}>没有匹配的数据点</Typography>}
    </Box><Typography variant="caption" color="text.secondary">{rows.length} 点 · 数据状态说明点的来源，不表示已审核通过。</Typography>
  </DetailSection>
}
