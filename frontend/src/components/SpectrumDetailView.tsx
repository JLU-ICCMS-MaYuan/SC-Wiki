import { useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import SpectrumFigure from './SpectrumFigure'
import SourceCanvas from './spectrumEditor/SourceCanvas'
import ImageOpacityControl from './spectrumEditor/ImageOpacityControl'
import ZeroFrequencyCheck from './spectrumEditor/ZeroFrequencyCheck'
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

export function SpectrumResult({ item, curves, image, retryImage, onEdit, editingDisabled = false, imageOpacity, onOpacityChange }: { item: Item; curves: Curve[]; image: string; retryImage: () => void; onEdit?: (curveId?: string) => void; editingDisabled?: boolean; imageOpacity?:number; onOpacityChange?:(value:number)=>void }) {
  const [mode, setMode] = useState('overlay'), [projection, setProjection] = useState('all'), [localOpacity, setLocalOpacity] = useState(100)
  const opacity=imageOpacity??localOpacity, setOpacity=onOpacityChange||setLocalOpacity
  const dos = curves[0]?.kind === 'phonon_dos'
  const selected = projection === 'all' ? curves : curves.filter(c => c.id === projection)
  const document=displayDocument(item,selected,image)
  return <DetailSection title="02 · 原图与提取结果">
    {onEdit && <Box sx={{textAlign:'right',mb:1}}><Button variant="contained" disabled={editingDisabled} onClick={()=>onEdit(selected[0]?.id)}>编辑</Button></Box>}
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
      {dos ? <TextField select size="small" label="分波态密度" value={projection} onChange={e => setProjection(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="all">全部分波</MenuItem>{curves.map(c => <MenuItem key={c.id} value={c.id}>仅 {c.projection || c.id}</MenuItem>)}
      </TextField> : <Typography variant="body2" color="text.secondary">保持来源图的轴向与幅值尺度。</Typography>}
      <SpectrumViewSwitch value={mode} onChange={setMode} />
    </Box>
    {document ? <div className="spectrum-manual-editor"><div className="detail-plot-body"><ImageOpacityControl value={opacity} onChange={setOpacity} disabled={mode==='data'}/><div className="detail-plot-content"><SourceCanvas doc={document} active={selected[0].id} selected={[]} display={mode} imageOpacity={opacity}/></div></div></div>
      : <SpectrumFigure item={item} curves={selected} allCurves={curves} image={image} mode={mode} opacity={.85} />}
    {curves[0]?.kind === 'alpha2f' && mode !== 'source' && <Typography variant="caption" sx={{ color: spectrumCurveColor(curves[0], 0) }}>红线：α²F 提取数据</Typography>}

    {curves.some(c => c.kind === 'alpha2f' && !item.result.manual_documents?.[c.id]?.calibration.amplitudeEvidence && !item.result.calibration?.curves?.find((value: { id: string; amplitude_evidence?: string }) => value.id === c.id)?.amplitude_evidence) && <Alert severity="info" sx={{ mt: 1 }}>此版本的 α²F 幅值标定尚待核对，显示旧提取记录不代表其刻度已确认。</Alert>}
    {mode !== 'data' && !image && <Button onClick={retryImage}>重新读取原图</Button>}
    {dos && <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>{selected.map((c, i) => <Typography key={c.id} variant="caption" sx={{ color: spectrumCurveColor(c, i) }}>{c.projection || c.id}</Typography>)}</Box>}
  </DetailSection>
}

export function SpectrumMetrics({ item, curves, history, onContinue, onRecalculate, recalculating=false, calculationDisabled=false }: {
  item: Item; curves: Curve[]; history: boolean; onContinue?: (curveId?: string) => void;
  onRecalculate?: () => void; recalculating?: boolean; calculationDisabled?: boolean
}) {
  const dos = curves[0]?.kind === 'phonon_dos', q = item.result.quality || {}, raw = q.integrals?.raw || {}, comparisons = q.comparisons?.raw || {}
  const manualZero=combinedZeroCheck(item,curves)
  const alpha = curves.find(c => c.kind === 'alpha2f')
  const zeroCovered = curves.length > 0 && curves.every(c => c.points[0]?.frequency_thz === 0 && c.points[0]?.observed_amplitude != null)
  const alphaCal = item.result.calibration?.curves?.find((c: { id: string }) => c.id === alpha?.id)
  const evidence=alpha && (item.result.manual_documents?.[alpha.id] ? item.result.manual_documents[alpha.id].calibration.amplitudeEvidence : alphaCal?.amplitude_evidence)
  const limited=alpha && item.review[alpha.id]?.status === 'accepted_limited'
  const legacyReason = !alpha ? '当前没有 α²F 数据' : !evidence ? 'α²F 独立幅值刻度依据尚待核对' : raw.status === 'unavailable' ? raw.reason : !zeroCovered ? '当前结果未覆盖真实零频边界' : raw.positive_frequency_complete === false ? '存在缺口，无法计算完整积分' : ''
  const parameters = raw.parameters || Object.fromEntries([['lambda','lambda_integral'],['omega_log','omega_log_k']].map(([key,field])=>[key,{status:legacyReason?'unavailable':'available',value:raw[field],reason:legacyReason}]))
  const restricted=item.stale || history || limited
  const mode = q.dos_mode_integral || { status: 'unavailable', reason: '尚无计算结果，请点击重新计算。' }
  const modeAvailable = mode.status === 'available' && !restricted
  const modeComparable=modeAvailable && (mode.comparison_status ? mode.comparison_status==='available' : mode.target_modes != null)
  const calculation=q.recalculations?.[dos?'phonon_dos':'alpha2f']
  const anyAlphaAvailable=!restricted && Object.values(parameters).some((v:any)=>v.status==='available')
  const reasons=restricted ? ['当前为历史、失效或限定频段版本，不展示完整谱计算结果。'] : dos ? [mode.reason].filter(Boolean)
    : [...new Set(Object.entries(parameters).filter(([,v]:any)=>v.status!=='available').map(([key,v]:any)=>(key==='lambda'?'λ':'ωlog')+'：'+(v.reason||'尚无可用结果')))]
  return <DetailSection title={dos ? '03 · 频段与数据完整性' : '03 · 积分结果与参考值对比'} action={onRecalculate && <Button variant="outlined" onClick={onRecalculate} disabled={calculationDisabled||recalculating} aria-busy={recalculating}>{recalculating?'计算中…':'重新计算'}</Button>}>
    <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 2 }}><Box><Typography variant="caption" color="text.secondary">实际提取频率范围</Typography><Typography fontWeight={600}>{spectrumInterval(curves)}</Typography></Box>
      <Box><Typography variant="caption" color="text.secondary">{dos ? '原胞原子数 N / 目标 3N' : '实际积分范围'}</Typography><Typography fontWeight={600}>{dos ? `${spectrumNumber(mode.primitive_atoms, 0)} / ${spectrumNumber(mode.target_modes, 0)}` : anyAlphaAvailable && raw.minimum_integrated_thz != null ? `${spectrumNumber(raw.minimum_integrated_thz)}–${spectrumNumber(raw.maximum_integrated_thz ?? Math.max(...(alpha?.points.map(p=>p.frequency_thz)||[])))} THz` : '暂不可计算'}</Typography></Box></Box>
    {manualZero && <div className="spectrum-manual-editor"><ZeroFrequencyCheck compact result={manualZero} unit="THz" afterSave={false} onContinue={value=>onContinue?.(value.id)} readOnly={!onContinue}/></div>}
    {!manualZero && !zeroCovered && <Alert severity="warning" sx={{ mb: 2 }}>零频提取不完整，请在编辑器中核对真实零频边界与曲线点。</Alert>}
    <Box sx={{ overflowX: 'auto' }}><Table size="small" sx={{ minWidth: 540 }}><TableHead><TableRow>{(dos ? ['全部分波积分', '目标 3N', '绝对偏差', '相对偏差（%）'] : ['参数', '提取谱积分值', '论文参考值', '绝对偏差']).map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead><TableBody>
      {dos ? <TableRow><TableCell>{modeAvailable ? spectrumNumber(mode.integral) : '—'}</TableCell><TableCell>{restricted ? '—' : spectrumNumber(mode.target_modes)}</TableCell><TableCell>{modeComparable ? spectrumNumber(mode.absolute_difference) : '—'}</TableCell><TableCell>{modeComparable && mode.relative_difference_pct != null ? spectrumNumber(mode.relative_difference_pct, 2) + '%' : '—'}</TableCell></TableRow>
        : [['λ', 'lambda'], ['ωlog（K）', 'omega_log']].map(([label, key]) => {
          const c = comparisons[key] || {}, available=!restricted && parameters[key]?.status==='available', comparable = available && c.status === 'available'
          return <TableRow key={key}><TableCell>{label}</TableCell><TableCell>{available ? spectrumNumber(parameters[key].value) : '—'}</TableCell><TableCell>{comparable ? spectrumNumber(c.reference) : '—'}</TableCell><TableCell>{comparable ? spectrumNumber(c.absolute_difference) : '—'}</TableCell></TableRow>
        })}
    </TableBody></Table></Box>
    {reasons.map(reason=><Typography key={String(reason)} variant="body2" color="text.secondary" sx={{mt:1}}>{String(reason)}</Typography>)}
    {calculation && <Typography variant="caption" display="block" sx={{mt:1}}>本版本计算时间：{new Date(calculation.calculated_at).toLocaleString()}</Typography>}
    {!dos && !restricted && ['lambda','omega_log'].map(key=>comparisons[key]?.source && <Typography variant="caption" display="block" key={key}>参考来源：{typeof comparisons[key].source==='string'?comparisons[key].source:JSON.stringify(comparisons[key].source)}</Typography>)}
  </DetailSection>
}
