import { it, expect } from 'vitest'
import { createInfluenceKernel } from '../../frontend/src/components/spectrumEditor/dragInfluence'
import { appendPoint, curvePath, removePoints, prepareMove, validateDocument, commit, undo, redo, snapTarget, joinExistingPoint, movePrepared, type Document } from '../../frontend/src/components/spectrumEditor/engine'

const doc:Document={schemaVersion:1,id:'chain',title:'谱',description:'',source:{id:'source',sha256:'hash',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,10],unit:'pixel'},amplitudeEvidence:''},curves:[{id:'a',name:'A',color:'red',pathOrdered:true,points:[{id:'a0',x:10,y:50,segment:'s',status:'observed',breakBefore:true},{id:'a1',x:30,y:40,segment:'s',status:'observed',breakBefore:false},{id:'a2',x:50,y:50,segment:'s',status:'observed',breakBefore:false}]},{id:'b',name:'B',color:'blue',points:[{id:'b0',x:60,y:50,segment:'b',status:'observed'}]}],zero:null,operations:[]}

it('跟随边界等于截断值时保留最外侧邻点，严格低于边界的尾部不参与',()=>{
  expect(createInfluenceKernel({coreNeighbors:2,edgeWeight:.1,decayLength:1,minWeight:.1})).toEqual([1,.55,.1])
})

it('没有起点、跨曲线起点、图外点不能开始描线',()=>{
  for(const anchor of ['', 'missing','b0'])expect(()=>appendPoint(doc,'a',anchor,40,80)).toThrow('已有点')
  expect(()=>appendPoint(doc,'a','a1',110,50)).toThrow('图框')
})
it('从中间点起画仅增加一条父子边，旧边和其他曲线不变',()=>{
  const next=appendPoint(doc,'a','a1',42,79),point=next.curves[0].points.at(-1)!
  expect(point.connectTo).toBe('a1');expect(point.breakBefore).toBe(true)
  expect(next.curves[0].points.slice(0,3)).toEqual(doc.curves[0].points)
  expect(curvePath(next,next.curves[0])).toBe('M10,50 L30,40 L50,50 M30,40 L42,79')
  expect(next.curves[1]).toBe(doc.curves[1]);expect(()=>validateDocument(next,doc)).not.toThrow()
})
it('后续点只连前一新点，不按频率/距离改接其他点',()=>{
  const first=appendPoint(doc,'a','a1',42,79),tail=first.curves[0].points.at(-1)!
  const next=appendPoint(first,'a',tail.id,49,50.1),last=next.curves[0].points.at(-1)!
  expect(last.connectTo).toBe(tail.id);expect(curvePath(next,next.curves[0])).toContain('M42,79 L49,50.1')
  expect(last.connectTo).not.toBe('a2')
})
it('删除父点断开该边，子链仍连接自己的后续点，不产生悬空前驱',()=>{
  const first=appendPoint(doc,'a','a1',42,79),tail=first.curves[0].points.at(-1)!
  const next=appendPoint(first,'a',tail.id,49,80),removed=removePoints(next,'a',['a1'])
  expect(removed.curves[0].points.find(p=>p.id===tail.id)?.connectTo).toBeUndefined()
  expect(removed.curves[0].points.at(-1)!.connectTo).toBe(tail.id)
  expect(()=>validateDocument(removed,doc)).not.toThrow()
})
it('分支联动遇分叉停止，不扩散到其他分支；撤销重做保留精确连接',()=>{
  const next=appendPoint(doc,'a','a1',42,79),tail=next.curves[0].points.at(-1)!
  const prepared=prepareMove(next,'a',tail.id,true)!
  expect(prepared.byId.has('a1')).toBe(true);expect(prepared.byId.has('a0')).toBe(false);expect(prepared.byId.has('a2')).toBe(false)
  const history=commit({past:[],present:doc,future:[]},next)
  expect(undo(history).present).toEqual(doc);expect(redo(undo(history)).present).toEqual(next)
  const invalid=structuredClone(next);invalid.curves[0].points[0].connectTo=tail.id
  expect(()=>validateDocument(invalid,doc)).toThrow()
})

it('8px屏幕距离吸附最近已有点，缩放后阈值正确且不扫描其他曲线',()=>{
  expect(snapTarget(doc.curves[0],57.9,50,1)?.id).toBe('a2')
  expect(snapTarget(doc.curves[0],58.1,50,1)).toBeNull()
  expect(snapTarget(doc.curves[0],53.9,50,2)?.id).toBe('a2')
  expect(snapTarget(doc.curves[0],54.1,50,2)).toBeNull()
  expect(snapTarget(doc.curves[0],60,50,1)).toBeNull() // b0属于其他分波
  expect(snapTarget(doc.curves[0],50,50,0)).toBeNull()
  expect(snapTarget(doc.curves[0],50,50,1,'a2')).toBeNull()
})
it('吸附只增加尾点到已有目标的边，不复制点或移动目标，保存和撤销可复现',()=>{
  const extended=appendPoint(doc,'a','a0',40,70),tail=extended.curves[0].points.at(-1)!
  const joined=joinExistingPoint(extended,'a',tail.id,'a2')
  expect(joined.curves[0].points).toHaveLength(4)
  expect(joined.curves[0].points.at(-1)!.joinTo).toBe('a2')
  expect(joined.curves[0].points.slice(0,3)).toEqual(doc.curves[0].points)
  expect(curvePath(joined,joined.curves[0])).toContain('M40,70 L50,50')
  expect(()=>validateDocument(JSON.parse(JSON.stringify(joined)),doc)).not.toThrow()
  const h=commit({past:[],present:extended,future:[]},joined)
  expect(undo(h).present).toEqual(extended);expect(redo(undo(h)).present).toEqual(joined)
  expect(joinExistingPoint(joined,'a',tail.id,'a2')).toBe(joined)
})
it('已有边/自身不重复连接，删除任一端清理吸附引用，拒绝跨曲线目标',()=>{
  expect(joinExistingPoint(doc,'a','a0','a1')).toBe(doc)
  expect(joinExistingPoint(doc,'a','a0','a0')).toBe(doc)
  expect(()=>joinExistingPoint(doc,'a','a0','b0')).toThrow()
  const joined=joinExistingPoint(doc,'a','a0','a2')
  const removed=removePoints(joined,'a',['a2'])
  expect(removed.curves[0].points[0].joinTo).toBeUndefined()
  expect(()=>validateDocument(removed,doc)).not.toThrow()
  const removedTail=removePoints(joined,'a',['a0']);expect(()=>validateDocument(removedTail,doc)).not.toThrow()
})
it('形成闭环后局部联动不重复遍历或覆盖中心，距离权重对两侧一致',()=>{
  const joined=joinExistingPoint(doc,'a','a0','a2'),prepared=prepareMove(joined,'a','a1',true)!
  expect(prepared.byId.get('a1')).toBe(1)
  expect(prepared.byId.get('a0')).toBe(prepared.byId.get('a2'))
  expect(prepared.byId.size).toBe(3)
  expect(movePrepared(prepared,0,5,'free').curves[0].points[1].y).toBe(45)
})
