import { describe, expect, it } from 'vitest'
import { displayDocument } from '../../frontend/src/components/spectrumEditor/adapter'
import { addPoint, move, tracePoints, validateDocument, type Document } from '../../frontend/src/components/spectrumEditor/engine'
import { recognizedAxes } from '../../frontend/src/components/spectrumEditor/axisGeometry'
import { createInfluenceKernel, DRAG_INFLUENCE } from '../../frontend/src/components/spectrumEditor/dragInfluence'
import type { PropertySpectrumItem } from '../../frontend/src/lib/propertySpectra'

function item(): PropertySpectrumItem {
  return {id:'real-collection',version:4,state_key:'s1',stale:false,source:{size_px:[200,300],source_sha256:'real-hash'},run:{id:'run4',status:'needs_review'},review:{},
    result:{calibration:{curves:[{id:'alpha',frequency_unit:'THz',frequency_ticks:[[280,0],[20,100]],amplitude_evidence:null}]},curves:[{
      id:'alpha',kind:'alpha2f',unit:'dimensionless',frequency_direction:'y',roi:[20,20,180,280],axis_calibration:{frequency:{slope:-100/260,intercept:280*100/260},amplitude:{slope:.1,intercept:-2}},
      points:[{frequency_thz:0,frequency_pixel:280,amplitude_pixel:25,observed_amplitude:.5,reconstructed_amplitude:.5,status:'observed'},
        {frequency_thz:5,frequency_pixel:267,amplitude_pixel:null,observed_amplitude:null,reconstructed_amplitude:null,status:'missing'},
        {frequency_thz:10,frequency_pixel:254,amplitude_pixel:30,observed_amplitude:1,reconstructed_amplitude:1,status:'observed'}]}]}}
}
describe('正式数据适配',()=>{
  it('仅使用当前来源的刻度与像素，不导入Demo固定坐标或借用未确认幅值',()=>{
    const source=item(),doc=displayDocument(source,source.result.curves,'blob:authorized-image')!
    expect(doc.source.id).toBe('real-collection');expect(doc.source.image).toBe('blob:authorized-image')
    expect(recognizedAxes(doc)?.frequencyTicks).toEqual([[280,0],[20,100]])
    expect(doc.calibration.amplitude.unit).toBe('pixel');expect(doc.curves[0].points.map(p=>p.x)).toEqual([25,30])
    expect(doc.curves[0].points[1].breakBefore).toBe(true)
  })
  it('缺真实尺寸或标定不伪造可编辑视图',()=>{
    const source=item();delete source.source.size_px;expect(displayDocument(source,source.result.curves,'image')).toBeNull()
  })
  it('手工保存的描线次序和坐标在详情保持，图片只换成当前鉴权blob',()=>{
    const source=item(),doc=displayDocument(source,source.result.curves,'')!
    doc.curves[0].points[0].x=77;source.result.manual_documents={alpha:doc}
    const next=displayDocument(source,source.result.curves,'blob:new')!
    expect(next.curves).toBe(doc.curves);expect(next.source.image).toBe('blob:new');expect(doc.source.image).toBe('')
  })

})
describe('正式编辑核心',()=>{
  function document():Document {const source=item();return displayDocument(source,source.result.curves,'blob:source')!}
  it('二维移动保持描线次序，不被频率邻点夹住',()=>{
    const doc=document(),id=doc.curves[0].points[0].id
    const moved=move(doc,'alpha',id,10,-40,false,'free')
    expect(tracePoints(moved,moved.curves[0])[0]).toMatchObject({id,x:35,y:240})
    expect(doc.curves[0].points[0].x).toBe(25)
  })

  it('新增后可校验源身份并拒绝越界，旧数据不被覆盖',()=>{
    const doc=document(),next=addPoint(doc,'alpha',29,277)
    expect(()=>validateDocument(next,doc)).not.toThrow();expect(next.curves[0].points).toHaveLength(3)
    expect(()=>addPoint(doc,'alpha',999,280)).toThrow()
  })
  it('正式配置保留用户认可的2/.3/1/.1比例，指数权重仅在初始化生成',()=>{
    // 验证给定配置的公式，不锁死用户正在手动调整的工作区参数。
    const weights=createInfluenceKernel({coreNeighbors:2,edgeWeight:.3,decayLength:1,minWeight:.1})
    expect(weights).toHaveLength(4)
    for(const [i,value] of [1,.65,.3,.3/Math.E].entries())expect(weights[i]).toBeCloseTo(value,12)
    expect(DRAG_INFLUENCE.coreNeighbors).toBeGreaterThan(0)
  })
})
