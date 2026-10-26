import { it, expect } from 'vitest'
import { appendPoint, curvePath, removePoints, prepareMove, validateDocument, commit, undo, redo, type Document } from '../../frontend/src/components/spectrumEditor/engine'

const doc:Document={schemaVersion:1,id:'chain',title:'谱',description:'',source:{id:'source',sha256:'hash',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,10],unit:'pixel'},amplitudeEvidence:''},curves:[{id:'a',name:'A',color:'red',pathOrdered:true,points:[{id:'a0',x:10,y:50,segment:'s',status:'observed',breakBefore:true},{id:'a1',x:30,y:40,segment:'s',status:'observed',breakBefore:false},{id:'a2',x:50,y:50,segment:'s',status:'observed',breakBefore:false}]},{id:'b',name:'B',color:'blue',points:[{id:'b0',x:60,y:50,segment:'b',status:'observed'}]}],zero:null,operations:[]}

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
