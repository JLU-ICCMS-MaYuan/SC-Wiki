import { useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import SpectrumFigure from './SpectrumFigure'
import SourceCanvas from './spectrumEditor/SourceCanvas'
import ImageOpacityControl from './spectrumEditor/ImageOpacityControl'
import ZeroFrequencyCheck from './spectrumEditor/ZeroFrequencyCheck'
import TraceDiagnostics from './spectrumEditor/TraceDiagnostics'
import AlphaRelativeMetrics from './spectrumEditor/AlphaRelativeMetrics'
import DosRelativeMetrics from './spectrumEditor/DosRelativeMetrics'
import { displayDocument, combinedZeroCheck } from './spectrumEditor/adapter'
import './spectrumEditor/styles.css'
import SpectrumViewSwitch from './SpectrumViewSwitch'
import { spectrumCurveColor } from '../lib/spectrumGeometry'
import { spectrumInterval } from '../lib/propertySpectra'

export const spectrumNumber = (value: unknown, digits = 4) => typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(digits)).toString() : '—'
const boxStyle = { p: { xs: 2, md: 2.5 }, mb: 2, borderRadius: 2, minWidth: 0 }

export function DetailSection({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <Paper variant="outlined" sx={boxStyle}><Box sx={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:1,flexWrap:'wrap',mb:2}}><Typography variant="h6" sx={{ fontSize: 17 }}>{title}</Typography>{action}</Box>{children}</Paper>
}

export function SpectrumResult({ item, curves, image, retryImage, onEdit, editingDisabled = false, editingDisabledReason, imageOpacity, onOpacityChange, history=false }: { history?: boolean; item: Item; curves: Curve[]; image: string; retryImage: () => void; onEdit?: (curveId?: string) => void; editingDisabled?: boolean; editingDisabledReason?:string; imageOpacity?:number; onOpacityChange?:(value:number)=>void }) {
  const [mode, setMode] = useState('overlay'), [projection, setProjection] = useState('all'), [localOpacity, setLocalOpacity] = useState(100)
  const opacity=imageOpacity??localOpacity, setOpacity=onOpacityChange||setLocalOpacity
  const dos = curves[0]?.kind === 'phonon_dos'
  const selected = projection === 'all' ? curves : curves.filter(c => c.id === projection)
  const [amplitudeView,setAmplitudeView]=useState('normalized')
  const normalization=dos?item.result.candidates?.dos_relative_normalized:item.result.candidates?.alpha2f_lambda_normalized
  const relative=item.result.quality?.integrals?.raw?.relative_basis
  const dosBases=selected.map(c=>normalization?.curves?.[c.id]?.amplitude_basis)
  const basis=dos?dosBases[0]:normalization?.amplitude_basis||relative
  const dosAllowed=!history&&!item.stale&&!selected.some(c=>item.review[c.id]?.status==='accepted_limited')
  const commonBasis=!dos||dosBases.every(b=>b&&b.baseline_pixel===basis?.baseline_pixel&&b.direction===basis?.direction)
  const canShowNormalized=Boolean((!dos||dosAllowed)&&commonBasis&&normalization?.status==='available'&&normalization.coefficient>0&&Number.isFinite(basis?.baseline_pixel))
  const originalDocument=displayDocument(item,selected,image)
  const useNormalized=canShowNormalized&&amplitudeView==='normalized'
  const multiplier=useNormalized?normalization.coefficient:1
  const transform=(!dos||canShowNormalized)&&originalDocument&&Number.isFinite(basis?.baseline_pixel)
  const document=transform?{...originalDocument,calibration:{...originalDocument.calibration,
    amplitude:{...originalDocument.calibration.amplitude,unit:useNormalized?(dos?'modes/THz/primitive_cell':'dimensionless'):'pixel',
      values:originalDocument.calibration.amplitude.pixels.map(p=>multiplier*basis.direction*(p-basis.baseline_pixel)) as [number,number]}}}:originalDocument
  return <DetailSection title="02 · 原图与提取结果">
    {onEdit && <Box sx={{textAlign:'right',mb:1}}><Button variant="contained" disabled={editingDisabled} onClick={()=>onEdit(selected[0]?.id)}>编辑</Button></Box>}
    {editingDisabled && editingDisabledReason && <Typography role="status" variant="body2" color="text.secondary" sx={{mb:1}}>{editingDisabledReason}</Typography>}
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
      {dos ? <TextField select size="small" label="分波态密度" value={projection} onChange={e => setProjection(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="all">全部分波</MenuItem>{curves.map(c => <MenuItem key={c.id} value={c.id}>仅 {c.projection || c.id}</MenuItem>)}
      </TextField> : <Typography variant="body2" color="text.secondary">保持来源图的轴向与幅值尺度。</Typography>}
      <SpectrumViewSwitch value={mode} onChange={setMode} />
    </Box>
    {canShowNormalized&&<Box sx={{display:'flex',gap:1,mb:1,flexWrap:'wrap'}} data-testid="amplitude-display">
      <Button size="small" variant={amplitudeView==='relative'?'contained':'outlined'} onClick={()=>setAmplitudeView('relative')}>相对像素幅值</Button>
      <Button size="small" variant={amplitudeView==='normalized'?'contained':'outlined'} onClick={()=>setAmplitudeView('normalized')}>{dos?'按 3N 归一化':'依据论文 λ 归一化'}</Button>
    </Box>}
    {document ? <div className="spectrum-manual-editor"><div className="detail-plot-body"><ImageOpacityControl value={opacity} onChange={setOpacity} disabled={mode==='data'}/><div className="detail-plot-content"><SourceCanvas doc={document} active={selected[0].id} selected={[]} display={mode} imageOpacity={opacity}/></div></div></div>
      : <SpectrumFigure item={item} curves={selected} allCurves={curves} image={image} mode={mode} opacity={.85} />}
    {curves[0]?.kind === 'alpha2f' && mode !== 'source' && <Typography variant="caption" sx={{ color: spectrumCurveColor(curves[0], 0) }}>红线：α²F 提取数据</Typography>}

    {mode !== 'data' && !image && <Button onClick={retryImage}>重新读取原图</Button>}
    {dos && <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>{selected.map((c, i) => <Typography key={c.id} variant="caption" sx={{ color: spectrumCurveColor(c, i) }}>{c.projection || c.id}</Typography>)}</Box>}
  </DetailSection>
}

export function SpectrumMetrics({ item, curves, history, onContinue, onRecalculate, onLocate, recalculating=false, calculationDisabled=false, calculationDisabledReason }: {
  item: Item; curves: Curve[]; history: boolean; onContinue?: (curveId?: string) => void;
  onLocate?: (curveId:string,pointId:string)=>void; onRecalculate?: () => void; recalculating?: boolean; calculationDisabled?: boolean; calculationDisabledReason?:string
}) {
  const dos = curves[0]?.kind === 'phonon_dos', q = item.result.quality || {}, raw = q.integrals?.raw || {}, comparisons = q.comparisons?.raw || {}
  const manualZero=combinedZeroCheck(item,curves)
  const alpha = curves.find(c => c.kind === 'alpha2f')
  const zeroCovered = curves.length > 0 && curves.every(c => c.points[0]?.frequency_thz === 0 && c.points[0]?.observed_amplitude != null)
  const limited=dos ? curves.some(c=>item.review[c.id]?.status==='accepted_limited') : alpha && item.review[alpha.id]?.status === 'accepted_limited'
  const restricted=item.stale || history || limited
  const mode = q.dos_mode_integral || { status: 'unavailable', reason: '尚无计算结果，请点击重新计算。' }
  const dosRelative=q.dos_relative
  const displayedAtoms=dosRelative?.normalization?.primitive_atoms??mode.primitive_atoms
  const displayedTarget=dosRelative?.normalization?.target_modes??mode.target_modes
  const modeAvailable = mode.status === 'available' && !restricted
  const modeComparable=modeAvailable && (mode.comparison_status ? mode.comparison_status==='available' : mode.target_modes != null)
  const anyAlphaAvailable=!restricted&&raw.method==='alpha2f-relative-v1'&&(raw.parameters?.omega_log?.status==='available'||raw.pixel_integral_status==='available')
  const diagnostics=q.trace_diagnostics?.[dos?'phonon_dos':'alpha2f']
  const repairs=q.automatic_repairs?.[dos?'phonon_dos':'alpha2f']||[]
  const reasons=restricted?[calculationDisabledReason||'当前为历史、失效或限定频段版本，不展示完整谱计算结果。']:dos?[mode.reason].filter(Boolean):[]
  return <DetailSection title={dos ? '03 · 频段与数据完整性' : '03 · 积分结果与参考值对比'} action={onRecalculate && <Button variant="outlined" onClick={onRecalculate} disabled={calculationDisabled||recalculating} aria-busy={recalculating}>{recalculating?'计算中…':'重新计算'}</Button>}>
    <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 2 }}><Box><Typography variant="caption" color="text.secondary">实际提取频率范围</Typography><Typography fontWeight={600}>{spectrumInterval(curves)}</Typography></Box>
      <Box><Typography variant="caption" color="text.secondary">{dos ? '原胞原子数 N / 目标 3N' : '实际积分范围'}</Typography><Typography fontWeight={600}>{dos ? `${restricted?'—':spectrumNumber(displayedAtoms, 0)} / ${restricted?'—':spectrumNumber(displayedTarget, 0)}` : anyAlphaAvailable && raw.minimum_integrated_thz != null ? `${spectrumNumber(raw.minimum_integrated_thz)}–${spectrumNumber(raw.maximum_integrated_thz ?? Math.max(...(alpha?.points.map(p=>p.frequency_thz)||[])))} THz` : '暂不可计算'}</Typography></Box></Box>
    {manualZero && <div className="spectrum-manual-editor"><ZeroFrequencyCheck compact result={manualZero} unit="THz" afterSave={false} onContinue={value=>onContinue?.(value.id)} readOnly={!onContinue}/></div>}
    {!manualZero && !zeroCovered && <Alert severity="warning" sx={{ mb: 2 }}>零频提取不完整，请在编辑器中核对真实零频边界与曲线点。</Alert>}
    {dos&&<DosRelativeMetrics report={dosRelative} restricted={Boolean(restricted)}/>}
    {dos&&<Typography fontWeight={600} sx={{mt:2}}>原始绝对密度积分（独立检查）</Typography>}
    {dos?<Box sx={{overflowX:'auto'}}><Table size="small" sx={{minWidth:540}}><TableHead><TableRow>{['全部分波积分','目标 3N','绝对偏差','相对偏差（%）'].map(label=><TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
      <TableRow><TableCell>{modeAvailable?spectrumNumber(mode.integral):'—'}</TableCell><TableCell>{restricted?'—':spectrumNumber(mode.target_modes)}</TableCell><TableCell>{modeComparable?spectrumNumber(mode.absolute_difference):'—'}</TableCell><TableCell>{modeComparable&&mode.relative_difference_pct!=null?spectrumNumber(mode.relative_difference_pct,2)+'%':'—'}</TableCell></TableRow>
    </TableBody></Table></Box>:<AlphaRelativeMetrics raw={raw} comparison={comparisons.omega_log} restricted={Boolean(restricted)}/>}
    {!restricted && calculationDisabled && calculationDisabledReason && <Typography variant="body2" color="text.secondary" sx={{mt:1}}>{calculationDisabledReason}</Typography>}
    {reasons.map(reason=><Typography key={String(reason)} variant="body2" color="text.secondary" sx={{mt:1}}>{String(reason)}</Typography>)}
    {!restricted && repairs.length>0 && <Alert severity="success" sx={{mt:2}} data-testid="automatic-repairs">
      已自动处理 {repairs.length} 处像素和数值完全重合的唯一断端，全部点与坐标保留。
      {repairs.map((repair:any,i:number)=><Box key={i}>{repair.points?.slice(0,1).map((point:any)=><Button key={point.point_id} size="small" disabled={!onLocate} onClick={()=>onLocate?.(repair.curve_id,point.point_id)}>查看自动连接 ({spectrumNumber(point.x,6)}, {spectrumNumber(point.y,6)})</Button>)}</Box>)}
    </Alert>}
    {!restricted && diagnostics && <TraceDiagnostics key={item.run.id} report={diagnostics} onLocate={onLocate} disabled={recalculating||calculationDisabled}/> }
  </DetailSection>
}
