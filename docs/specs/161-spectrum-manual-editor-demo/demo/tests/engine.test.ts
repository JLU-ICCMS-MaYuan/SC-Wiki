import { describe, expect, it } from 'vitest'
import { addPoint, amplitude, axisValid, clone, commit, curvePath, frequency, markZero, move, pixelAt, record, redo, removePoints, undo, validateDocument, valueAt, neighborWeight, prepareMove, movePrepared, connected, restoreManualMarkers, tracePoints, reconnectManualPoints, zeroCovered, type Document, type History } from '../src/engine'
import fixtures from '../src/fixtures.json'
import { DRAG_INFLUENCE } from '../src/dragInfluence'
const expectedWeight = (d: number) => {
  const c = DRAG_INFLUENCE
  const weight = d <= c.coreNeighbors ? 1-(1-c.edgeWeight)*d/c.coreNeighbors : c.edgeWeight*Math.exp(-(d-c.coreNeighbors)/c.decayLength)
  return weight < c.minWeight ? 0 : weight
}
const support = Array.from({length:1001},(_,i)=>expectedWeight(i)).filter(w=>w>0).length
const base: Document = {
  schemaVersion: 1, id: 'test', title: '测试谱', description: '',
  source: { id: 'source', sha256: 'hash', width: 101, height: 101, image: '', plot: [0,0,100,100], viewport: [0,0,100,100] },
  calibration: { direction: 'x', frequency: {pixels:[0,100],values:[0,10],unit:'THz'}, amplitude:{pixels:[100,0],values:[0,10],unit:'pixel'},amplitudeEvidence:'' },
  curves: [{id:'a',name:'A',color:'#abc',points:[10,20,30,40,50,60].map((x,i)=>({id:'p'+i,x,y:50,segment:i<5?'s':'gap',status:'原始'}))}, {id:'b',name:'B',color:'#def',points:[{id:'other',x:20,y:30,segment:'s',status:'原始'}]}],
  zero:null,operations:[],
}
describe('坐标与示例契约', () => {
  it('实际两个固定样本满足草稿校验，保留未知幅值', () => {
    for(const value of fixtures) {const d=value as unknown as Document; expect(()=>validateDocument(d,d)).not.toThrow(); expect(d.calibration.amplitude.unit).toBe('pixel')}
  })
  it('正向/反向轴均可往返换算', () => {
    for(const axis of [base.calibration.frequency,base.calibration.amplitude]) for(const pixel of [0,13.73,100]) expect(pixelAt(axis,valueAt(axis,pixel))).toBeCloseTo(pixel,10)
  })
  it('标定变化不改变像素；支持竖直频率', () => {
    const next=clone(base); next.calibration.direction='y'; next.calibration.frequency.values=[10,0]
    expect(next.curves).toEqual(base.curves); expect(frequency(next,next.curves[0].points[0])).toBe(5)
  })
  it('拒绝退化标定', () => {expect(axisValid({...base.calibration.frequency,pixels:[1,1]})).toBe(false);expect(axisValid({...base.calibration.frequency,values:[NaN,2]})).toBe(false)})
  it('拒绝损坏和错误来源草稿', () => {
    const wrong=clone(base);wrong.source.sha256='wrong';expect(()=>validateDocument(wrong,base)).toThrow()
    const bad=clone(base);bad.curves[0].points[0].x=NaN;expect(()=>validateDocument(bad,base)).toThrow()
    expect(()=>validateDocument({},base)).toThrow()
  })
})
describe('局部形状与限位', () => {
  it('中心完全跟随、邻点平滑衰减、范围外不动', () => {
    expect(neighborWeight(0)).toBe(1); expect(neighborWeight(DRAG_INFLUENCE.coreNeighbors)).toBeCloseTo(DRAG_INFLUENCE.edgeWeight); expect(neighborWeight(support)).toBe(0)
    const d=move(base,'a','p1',20,-10,true,'amplitude')
    expect(d.curves[0].points[1].y).toBe(40);expect(d.curves[0].points[1].x).toBe(20)
    expect(d.curves[0].points[2].y).toBeCloseTo(50-10*expectedWeight(1));expect(d.curves[0].points[3].y).toBeCloseTo(50-10*expectedWeight(2))
    expect(d.curves[1]).toEqual(base.curves[1]);expect(base.curves[0].points[1].y).toBe(50)
  })
  it('不跨片段，单点模式不联动', () => {
    expect(move(base,'a','p4',0,-10,true,'amplitude').curves[0].points[5]).toMatchObject(base.curves[0].points[5])
    const d=move(base,'a','p1',0,-10,false,'amplitude');expect(d.curves[0].points[0]).toMatchObject(base.curves[0].points[0])
  })
  it('竖直频率时只左右改幅值', () => {
    const d=clone(base);d.calibration.direction='y';d.curves[0].points.forEach((p,i)=>{p.y=10+i*10;p.x=40})
    const next=move(d,'a','p1',8,50,true,'amplitude');expect(next.curves[0].points[1].x).toBe(48);expect(next.curves[0].points[1].y).toBe(20)
  })
  it('二维移动可跨原邻点频率，描线顺序不变', () => {
    const d=move(base,'a','p1',50,-20,false,'free'), p=d.curves[0].points[1]
    expect(p.x).toBe(70);expect(p.y).toBe(30);expect(tracePoints(d,d.curves[0]).map(p=>p.id)).toEqual(base.curves[0].points.map(p=>p.id))
    expect(()=>validateDocument(d,base)).not.toThrow()
  })
  it('图框限位不改变范围外点', () => {
    const d=move(base,'a','p1',0,-200,true,'amplitude');expect(d.curves[0].points[1].y).toBe(0);expect(d.curves[0].points[5].y).toBe(50)
  })
  it('零位移不制造人工修改', () => {expect(move(base,'a','p1',0,0,true,'free')).toBe(base)})
})
describe('片段与真实零频选点', () => {
  it('删除中间点断开绘图与联动', () => {
    const d=removePoints(base,'a',['p2']);expect(d.curves[0].points).toHaveLength(5)
    expect(connected(d.curves[0].points[1],d.curves[0].points[2])).toBe(false)
    expect((curvePath(d,d.curves[0]).match(/M/g)||[]).length).toBe(3)
    const moved=move(d,'a','p1',0,-10,true,'amplitude');expect(moved.curves[0].points[2].y).toBe(50)
  })
  it('缺口补点自动连接两侧，片段内部插入保持连接', () => {
    const d=removePoints(base,'a',['p2']);const filled=addPoint(d,'a',30,20)
    expect((curvePath(filled,filled.curves[0]).match(/M/g)||[]).length).toBe(2);expect(filled.curves[0].points.find(p=>p.x===30)!.manual).toBe(true)
    const inside=addPoint(base,'a',15,20);expect((curvePath(inside,inside.curves[0]).match(/M/g)||[]).length).toBe(2)
  })
  it('删空仍可增加，相同频率描线可编辑但重复位置拒绝', () => {
    const d=removePoints(base,'a',base.curves[0].points.map(p=>p.id));expect(addPoint(d,'a',15,20).curves[0].points).toHaveLength(1)
    expect(()=>addPoint(base,'a',20,50)).toThrow('已有点');expect(()=>validateDocument(addPoint(base,'a',20,20),base)).not.toThrow()
  })
  it('标零不自动补点；零幅值来自用户点选', () => {
    const d=markZero(base,0,50);expect(d.curves).toEqual(base.curves);expect(zeroCovered(d,'a')).toBe(false)
    const withPoint=addPoint(d,'a',.2,37,true);expect(zeroCovered(withPoint,'a')).toBe(true)
    const p=withPoint.curves[0].points.find(p=>p.status==='人工零频选点')!
    expect(p.x).toBe(0);expect(p.y).toBe(37);expect(amplitude(withPoint,p)).toBeCloseTo(6.3)
    expect(zeroCovered(withPoint,'b')).toBe(false)
  })
  it('零频补点必须在已标记位置附近', () => {
    expect(()=>addPoint(base,'a',0,40,true)).toThrow('先标记')
    expect(()=>addPoint(markZero(base,0,50),'a',40,30,true)).toThrow('零频线上')
  })
  it('删除或移走零频点会恢复不完整提示', () => {
    const d=addPoint(markZero(base,0,50),'a',0,35,true), id=d.zero!.pointIds[0]
    expect(zeroCovered(removePoints(d,'a',[id]),'a')).toBe(false)
    expect(zeroCovered(move(d,'a',id,2,0,false,'free'),'a')).toBe(false)
  })
})
describe('历史', () => {
  it('一次拖动一次提交，撤销重做精确恢复', () => {
    const h: History={past:[],present:base,future:[]}
    const first=move(base,'a','p1',0,-2,true,'amplitude');const final=move(base,'a','p1',0,-8,true,'amplitude')
    expect(first.curves[0].points[1].y).toBe(48)
    const saved=commit(h,record(final,'move','drag'));expect(saved.past).toHaveLength(1)
    expect(undo(saved).present).toEqual(base);expect(redo(undo(saved)).present).toEqual(saved.present)
  })
  it('新操作清除重做；恢复原始也可撤销', () => {
    let h: History={past:[],present:base,future:[]};h=commit(h,removePoints(base,'a',['p1']))
    const restored=commit(h,record(clone(base),'restore','reset'));expect(undo(restored).present).toEqual(h.present)
    const next=commit(undo(h),addPoint(base,'a',15,12));expect(next.future).toHaveLength(0)
  })
})


describe('补点连接及固定邻点微调回归', () => {
  it('连续补点、端点延长均连接相邻点，不增加额外数值点', () => {
    let d=addPoint(base,'a',5,35); d=addPoint(d,'a',2,38)
    expect(d.curves[0].points).toHaveLength(8)
    expect((curvePath(d,d.curves[0]).match(/M/g)||[]).length).toBe(2)
    expect(connected(d.curves[0].points[0],d.curves[0].points[1])).toBe(true)
    const removed=removePoints(d,'a',[d.curves[0].points[1].id])
    expect(connected(removed.curves[0].points[0],removed.curves[0].points[1])).toBe(false)
    expect(d.curves[1]).toEqual(base.curves[1])
  })
  it('旧草稿中移动过的人工点按稳定 ID 识别，坐标和原对象不变', () => {
    const old=clone(base); old.curves[0].points.unshift({id:'old-manual',x:5,y:39,segment:'isolated',status:'人工调整'})
    const restored=restoreManualMarkers(old,base)
    expect(restored.curves[0].points[0]).toMatchObject({...old.curves[0].points[0],manual:true})
    expect(old.curves[0].points[0].manual).toBeUndefined()
    expect((curvePath(restored,restored.curves[0]).match(/M/g)||[]).length).toBe(2)
    expect(restoreManualMarkers(restored,base)).toEqual(restored)
  })
  it('当前用户配置的邻点权重和截断生效，不随采样间隔改变', () => {
    const d=clone(base);d.curves[0].points=Array.from({length:61},(_,i)=>({id:'n'+i,x:i+10,y:50,segment:'s',status:'原始'}))
    const prepared=prepareMove(d,'a','n30',true)!, result=movePrepared(prepared,0,-10,'amplitude')
    expect(prepared.byId.size).toBe(1+2*Math.min(30,support-1))
    for(const step of [-1,1]) for(let distance=1;distance<=20;distance++) {
      const i=30+step*distance
      expect(50-result.curves[0].points[i].y).toBeCloseTo(10*neighborWeight(distance),10)
    }
    const uneven=clone(d);uneven.curves[0].points.forEach((p,i)=>{p.x=10+(i/60)**2*80})
    expect(prepareMove(uneven,'a','n30',true)!.weights).toEqual(prepared.weights)
    expect(movePrepared(prepared,0,-10,'amplitude')).toEqual(result)
    expect(d.curves[0].points[30].y).toBe(50)
  })
  it('人工连线后的两侧参与联动，删点后断口阻止联动', () => {
    let d=removePoints(base,'a',['p2']);d=addPoint(d,'a',30,50)
    const id=d.curves[0].points.find(p=>p.x===30)!.id
    const linked=move(d,'a',id,0,-5,true,'amplitude')
    expect(linked.curves[0].points.find(p=>p.id==='p1')!.y).toBeLessThan(50)
    expect(linked.curves[0].points.find(p=>p.id==='p3')!.y).toBeLessThan(50)
    const deleted=removePoints(d,'a',[id]);expect(move(deleted,'a','p1',0,-5,true,'amplitude').curves[0].points.find(p=>p.id==='p3')!.y).toBe(50)
  })
})


describe('用户截图坐标与二维描线回归', () => {
  it('右侧新点的 y 略大时延长端点，不再先到新点再折回旧点', () => {
    const d=clone(base);d.source.plot=[630,280,710,320];d.calibration.direction='y'
    d.calibration.frequency={pixels:[320,280],values:[0,40],unit:'THz'}
    d.curves[0].points=[{id:'before',x:679.7,y:302.51,segment:'s',status:'原始'},{id:'old-end',x:685.13,y:302.24,segment:'s',status:'原始'}]
    const next=addPoint(d,'a',687.8,302.30), points=tracePoints(next,next.curves[0])
    expect(points.map(p=>p.id).slice(0,2)).toEqual(['before','old-end'])
    expect(points[2].x).toBe(687.8);expect(points[2].y).toBe(302.30)
    expect(curvePath(next,next.curves[0])).toBe('M679.7,302.51 L685.13,302.24 L687.8,302.3')
  })
  it('在线段内部插点保持前后连线，不投影或修改点击位置', () => {
    const next=addPoint(base,'a',15,49.9), pts=tracePoints(next,next.curves[0])
    expect(pts[0].id).toBe('p0');expect(pts[1].x).toBe(15);expect(pts[1].y).toBe(49.9);expect(pts[2].id).toBe('p1')
  })
  it('二维移动保持重复频率描线的顺序与全部非目标点', () => {
    const d=move(base,'a','p1',10,-8,false,'free')
    expect(d.curves[0].points[1]).toMatchObject({id:'p1',x:30,y:42})
    expect(d.curves[0].points[2]).toMatchObject({id:'p2',x:30,y:50})
    expect(()=>validateDocument(d,base)).not.toThrow()
    expect(curvePath(d,d.curves[0])).toContain('L30,42 L30,50')
  })
  it('显式重连只修连接顺序，坐标、点身份及非目标曲线保持', () => {
    const d=clone(base);d.calibration.direction='y';d.curves[0].pathOrdered=true;d.curves[0].points.splice(1,0,{id:'manual',x:25,y:49.9,segment:'m',status:'人工调整',manual:true})
    const h: History={past:[],present:d,future:[]}, next=reconnectManualPoints(d,'a')
    const coords=(v:Document)=>Object.fromEntries(v.curves[0].points.map(p=>[p.id,[p.x,p.y]]))
    expect(coords(next)).toEqual(coords(d));expect(next.curves[1]).toEqual(d.curves[1]);expect(next.curves[0].points.map(p=>p.id).slice(0,4)).toEqual(['p0','p1','manual','p2'])
    expect(undo(commit(h,next)).present).toEqual(d)
  })
})


it('局部重连不会对整段密集峰执行全局重排', () => {
  const d=clone(base);d.calibration.direction='y';d.curves[0].pathOrdered=true
  d.curves[0].points=[{id:'a',x:20,y:60,segment:'s',status:'原始'},{id:'peak',x:90,y:59,segment:'s',manual:true,status:'人工补选'},{id:'c',x:20,y:58,segment:'s',status:'原始'}]
  expect(reconnectManualPoints(d,'a')).toBe(d)
})
