import { useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import SpectrumFigure from './SpectrumFigure'
import SourceCanvas from './spectrumEditor/SourceCanvas'
import ImageOpacityControl from './spectrumEditor/ImageOpacityControl'
import ZeroFrequencyCheck from './spectrumEditor/ZeroFrequencyCheck'
import TraceDiagnostics from './spectrumEditor/TraceDiagnostics'
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

export function SpectrumResult({ item, curves, image, retryImage, onEdit, editingDisabled = false, editingDisabledReason, imageOpacity, onOpacityChange }: { item: Item; curves: Curve[]; image: string; retryImage: () => void; onEdit?: (curveId?: string) => void; editingDisabled?: boolean; editingDisabledReason?:string; imageOpacity?:number; onOpacityChange?:(value:number)=>void }) {
  const [mode, setMode] = useState('overlay'), [projection, setProjection] = useState('all'), [localOpacity, setLocalOpacity] = useState(100)
  const opacity=imageOpacity??localOpacity, setOpacity=onOpacityChange||setLocalOpacity
  const dos = curves[0]?.kind === 'phonon_dos'
  const selected = projection === 'all' ? curves : curves.filter(c => c.id === projection)
  const document=displayDocument(item,selected,image)
  return <DetailSection title="02 · 原图与提取结果">
    {onEdit && <Box sx={{textAlign:'right',mb:1}}><Button variant="contained" disabled={editingDisabled} onClick={()=>onEdit(selected[0]?.id)}>编辑</Button></Box>}
    {editingDisabled && editingDisabledReason && <Typography role="status" variant="body2" color="text.secondary" sx={{mb:1}}>{editingDisabledReason}</Typography>}
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', mb: 2 }}>
      {dos ? <TextField select size="small" label="分波态密度" value={projection} onChange={e => setProjection(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="all">全部分波</MenuItem>{curves.map(c => <MenuItem key={c.id} value={c.id}>仅 {c.projection || c.id}</MenuItem>)}
      </TextField> : <Typography variant="body2" color="text.secondary">保持来源图的轴向与幅值尺度。</Typography>}
      <SpectrumViewSwitch value={mode} onChange={setMode} />
    </Box>
    {document ? <div className="spectrum-manual-editor"><div className="detail-plot-body"><ImageOpacityControl value={opacity} onChange={setOpacity} disabled={mode==='data'}/><div className="detail-plot-content"><SourceCanvas doc={document} active={selected[0].id} selected={[]} display={mode} imageOpacity={opacity}/></div></div></div>
      : <SpectrumFigure item={item} curves={selected} allCurves={curves} image={image} mode={mode} opacity={.85} />}
    {curves[0]?.kind === 'alpha2f' && mode !== 'source' && <Typography variant="caption" sx={{ color: spectrumCurveColor(curves[0], 0) }}>红线：α²F 提取数据</Typography>}

    {curves.some(c => c.kind === 'alpha2f' && !item.result.manual_documents?.[c.id]?.calibration.amplitudeEvidence && !item.result.calibration?.curves?.find((value: { id: string; amplitude_evidence?: string }) => value.id === c.id)?.amplitude_evidence) && <Alert severity="info" sx={{ mt: 1 }}>α²F 幅值标定待核对，可在编辑器中补充刻度与依据；不影响编辑和保存。</Alert>}
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
  const alphaCal = item.result.calibration?.curves?.find((c: { id: string }) => c.id === alpha?.id)
  const evidence=alpha && (item.result.manual_documents?.[alpha.id] ? item.result.manual_documents[alpha.id].calibration.amplitudeEvidence : alphaCal?.amplitude_evidence)
  const limited=alpha && item.review[alpha.id]?.status === 'accepted_limited'
  const legacyReason = !alpha ? '当前没有 α²F 数据' : !evidence ? 'α²F 独立幅值刻度依据尚待核对' : raw.status === 'unavailable' ? raw.reason : !zeroCovered ? '当前结果未覆盖真实零频边界' : raw.positive_frequency_complete === false ? '存在缺口，无法计算完整积分' : ''
  const parameters = raw.parameters || Object.fromEntries([['lambda','lambda_integral'],['omega_log','omega_log_k']].map(([key,field])=>[key,{status:legacyReason?'unavailable':'available',value:raw[field],reason:legacyReason}]))
  const restricted=item.stale || history || limited
  const mode = q.dos_mode_integral || { status: 'unavailable', reason: '尚无计算结果，请点击重新计算。' }
  const modeAvailable = mode.status === 'available' && !restricted
  const modeComparable=modeAvailable && (mode.comparison_status ? mode.comparison_status==='available' : mode.target_modes != null)
  const anyAlphaAvailable=!restricted && Object.values(parameters).some((v:any)=>v.status==='available')
  const diagnostics=q.trace_diagnostics?.[dos?'phonon_dos':'alpha2f']
  const repairs=q.automatic_repairs?.[dos?'phonon_dos':'alpha2f']||[]
  const reasonGroups=new Map<string,string[]>()
  for(const [key,value] of Object.entries(parameters) as [string,any][]){
    if(value.status!=='available'){
      const reason=value.reason||'尚无可用结果'
      reasonGroups.set(reason,[...(reasonGroups.get(reason)||[]),key==='lambda'?'λ':'ωlog'])
    }
  }
  const displayReason=(reason:string)=>/高频末端尚待核对|曲线未覆盖当前图框的完整高频端|DOS分波截止不同且未全部核对|DOS各分波覆盖的频率范围不一致/.test(reason)?'请点击重新计算，按当前保存曲线的数据范围计算。':reason
  const reasons=restricted ? [calculationDisabledReason||'当前为历史、失效或限定频段版本，不展示完整谱计算结果。'] : dos ? [mode.reason&&displayReason(mode.reason)].filter(Boolean)
    : [...reasonGroups].map(([reason,labels])=>labels.join('、')+'：'+displayReason(reason))
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
    {!restricted && calculationDisabled && calculationDisabledReason && <Typography variant="body2" color="text.secondary" sx={{mt:1}}>{calculationDisabledReason}</Typography>}
    {reasons.map(reason=><Typography key={String(reason)} variant="body2" color="text.secondary" sx={{mt:1}}>{String(reason)}</Typography>)}
    {!restricted && repairs.length>0 && <Alert severity="success" sx={{mt:2}} data-testid="automatic-repairs">
      已自动处理 {repairs.length} 处像素和数值完全重合的唯一断端，全部点与坐标保留。
      {repairs.map((repair:any,i:number)=><Box key={i}>{repair.points?.slice(0,1).map((point:any)=><Button key={point.point_id} size="small" disabled={!onLocate} onClick={()=>onLocate?.(repair.curve_id,point.point_id)}>查看自动连接 ({spectrumNumber(point.x,6)}, {spectrumNumber(point.y,6)})</Button>)}</Box>)}
    </Alert>}
    {!restricted && diagnostics && <TraceDiagnostics key={item.run.id} report={diagnostics} onLocate={onLocate} disabled={recalculating||calculationDisabled}/> }
  </DetailSection>
}
