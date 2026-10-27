import type { PropertySpectrumCurve, PropertySpectrumItem } from '../../lib/propertySpectra'
import type { Document, Point } from './engine'
import type { ZeroCheck } from './zeroCheck'
import { spectrumCurveColor, spectrumGeometry } from '../../lib/spectrumGeometry'

/** 详情只读适配；真正编辑必须向服务端取得带版本的文档。 */
export function displayDocument(item: PropertySpectrumItem, curves: PropertySpectrumCurve[], image: string): Document | null {
  const first=curves[0],size=item.source.size_px as number[]|undefined
  if(!first || !size || !first.axis_calibration || !first.frequency_direction)return null
  const saved=item.result.manual_documents?.[first.id]
  if(saved && curves.length===1)return {...saved,source:{...saved.source,image}}
  const geometry=spectrumGeometry(curves,size[0],size[1]);if(!geometry)return null
  const {plot,crop}=geometry,direction=first.frequency_direction
  const spec=item.result.calibration?.curves?.find((c:any)=>c.id===first.id)
  const f=first.axis_calibration.frequency,a=first.axis_calibration.amplitude
  const fp=direction==='y'?[plot[3],plot[1]]:[plot[0],plot[2]],ap=direction==='y'?[plot[0],plot[2]]:[plot[3],plot[1]]
  const relative=first.unit==='pixel'||first.unit==='unknown'||first.kind==='alpha2f'&&!spec?.amplitude_evidence
  const readPoints=(c:PropertySpectrumCurve):Point[]=>{
    const stored=item.result.manual_documents?.[c.id]?.curves[0].points
    if(stored)return stored
    let broken=true,segment=0
    return c.points.flatMap((p,i)=>{
      const axis=c.axis_calibration?.amplitude,fp=p.frequency_pixel
      const ap=p.amplitude_pixel ?? (axis&&p.reconstructed_amplitude!=null?(p.reconstructed_amplitude-axis.intercept)/axis.slope:null)
      if(fp==null||ap==null||!Number.isFinite(fp)||!Number.isFinite(ap)){broken=true;return []}
      if(broken)segment++
      const point={id:p.id||c.id+':p'+i,x:c.frequency_direction==='y'?ap:fp,y:c.frequency_direction==='y'?fp:ap,
        segment:p.segment||String(segment),breakBefore:p.breakBefore??broken,status:p.status,manual:p.manual,connectTo:p.connectTo,joinTo:p.joinTo}
      broken=false;return [point]
    })
  }
  return {schemaVersion:1,id:item.id,title:'谱数据',description:'',
    source:{id:item.id,sha256:String(item.source.source_sha256||''),image,width:size[0],height:size[1],plot,
      viewport:[crop[0],crop[1],crop[2]-crop[0],crop[3]-crop[1]]},
    calibration:saved?.calibration||{direction,frequency:{pixels:fp as [number,number],values:fp.map(p=>f.slope*p+f.intercept) as [number,number],unit:'THz'},
      amplitude:{pixels:ap as [number,number],values:(relative?[0,Math.abs(ap[1]-ap[0])]:ap.map(p=>a.slope*p+a.intercept)) as [number,number],unit:relative?'pixel':first.unit},amplitudeEvidence:spec?.amplitude_evidence||''},
    recognizedAxes:saved?.recognizedAxes||{sourceId:item.id,sourceSha256:String(item.source.source_sha256||''),direction,
      frequencyUnit:spec?.frequency_unit||'THz',frequencyTicks:spec?.frequency_ticks||[],lambdaTicks:[]},
    curves:curves.map((c,i)=>({id:c.id,name:c.projection||'α²F',color:spectrumCurveColor(c,i),points:readPoints(c),pathOrdered:true})),
    zero:saved?.zero||null,operations:[]}
}

export function combinedZeroCheck(item: PropertySpectrumItem, curves: PropertySpectrumCurve[]): ZeroCheck | null {
  const checks=item.result.quality?.manual_zero_checks
  if(!checks)return null
  const values=curves.map(c=>checks[c.id]).filter(Boolean)
  const rows=curves.map(c=>checks[c.id]?.curves?.[0]||{id:c.id,name:c.projection||'α²F',status:'needs_boundary'})
  const completedCount=rows.filter(c=>c.status==='complete').length
  const pixel=values[0]?.zeroPixel
  return {complete:rows.length>0&&completedCount===rows.length,boundary:values.length===curves.length&&values.every(v=>v.boundary==='confirmed')?'confirmed':'missing',
    zeroPixel:Number.isFinite(pixel)&&values.every(v=>v.zeroPixel===pixel)?pixel:NaN,completedCount,curves:rows}
}
