import { it,expect } from 'vitest'
import { appendPoint,insertDrawnPoints,joinExistingPoint,curvePath,validateDocument,prepareMove,commit,undo,redo,type Document } from '../../frontend/src/components/spectrumEditor/engine'

const initial=():Document=>({schemaVersion:1,id:'insert',title:'谱',description:'',
 source:{id:'source',sha256:'hash',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},
 calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,1],unit:'pixel'},amplitudeEvidence:''},
 curves:[{id:'a',name:'A',color:'red',pathOrdered:true,points:[
 {id:'a0',x:10,y:50,segment:'s',status:'observed',breakBefore:true},
 {id:'a1',x:30,y:40,segment:'s',status:'observed',breakBefore:false},
 {id:'a2',x:50,y:50,segment:'s',status:'observed',breakBefore:false}]},
 {id:'b',name:'B',color:'blue',points:[{id:'b0',x:60,y:50,segment:'b',status:'observed'}]}],zero:null,operations:[]})
const edge=(a:string,b:string)=>[a,b].sort().join('|')
// 从实际SVG绘制命令恢复边，验证用户看见的形状。
function drawn(doc:Document){
 const curve=doc.curves[0],ids=new Map(curve.points.map(p=>[p.x+','+p.y,p.id])),result=new Set<string>()
 let previous:string|undefined
 for(const command of curvePath(doc,curve).match(/[ML][^ML]+/g)||[]){
   const coords=command.slice(1).trim().split(/[ ,]+/).map(Number),id=ids.get(coords.join(','))
   if(command[0]==='L'&&previous&&id)result.add(edge(previous,id))
   previous=id
 }
 return result
}
function add(doc:Document,start:string,coords:number[][]){
 const ids:string[]=[]
 for(const [x,y] of coords){doc=appendPoint(doc,'a',ids.at(-1)||start,x,y);ids.push(doc.curves[0].points.at(-1)!.id)}
 return {doc,ids}
}
it.each([false,true])('单点/多点插入替换原边、原点与其他边保持，反向=%s',reverse=>{
 const source=initial(),old=structuredClone(source),start=reverse?'a1':'a0',target=reverse?'a0':'a1'
 const chain=add(source,start,reverse?[[25,43],[20,47]]:[[20,47],[25,43]])
 const next=insertDrawnPoints(chain.doc,'a',start,target,chain.ids)
 expect(drawn(next)).toEqual(new Set([edge('a1','a2'),edge(start,chain.ids[0]),edge(chain.ids[0],chain.ids[1]),edge(chain.ids[1],target)]))
 expect(next.curves[0].points.map(p=>p.id)).toEqual(['a0',...(reverse?[...chain.ids].reverse():chain.ids),'a1','a2'])
 for(const p of old.curves[0].points)expect(next.curves[0].points.find(v=>v.id===p.id)).toMatchObject({id:p.id,x:p.x,y:p.y,status:p.status})
 expect(next.curves[1]).toBe(source.curves[1]);expect(source).toEqual(old)
 expect(()=>validateDocument(next,source)).not.toThrow()
})
it('显式父边插入不误接中间存储的其他点',()=>{
 const doc=initial();doc.curves[0].points[2].connectTo='a0';doc.curves[0].points[2].breakBefore=true
 const chain=add(doc,'a2',[[40,52],[20,55]])
 const next=insertDrawnPoints(chain.doc,'a','a2','a0',chain.ids)
 expect(drawn(next)).toEqual(new Set([edge('a0','a1'),edge('a2',chain.ids[0]),edge(chain.ids[0],chain.ids[1]),edge(chain.ids[1],'a0')]))
 expect(()=>validateDocument(next,doc)).not.toThrow()
})
it('替换join边时保留终点原有的父边',()=>{
 const doc=initial();doc.curves[0].points[2].joinTo='a0'
 const chain=add(doc,'a0',[[20,55]])
 const next=insertDrawnPoints(chain.doc,'a','a0','a2',chain.ids)
 expect(drawn(next)).toEqual(new Set([edge('a0','a1'),edge('a1','a2'),edge('a0',chain.ids[0]),edge(chain.ids[0],'a2')]))
 expect(()=>validateDocument(next,doc)).not.toThrow()
})
it('未连接片段仍用原有加点/吸附补接，不要求目标原本直连',()=>{
 const doc=initial();doc.curves[0].points[1].breakBefore=true
 const chain=add(doc,'a0',[[20,45]])
 expect(()=>insertDrawnPoints(chain.doc,'a','a0','a1',chain.ids)).toThrow('原线段')
 const joined=joinExistingPoint(chain.doc,'a',chain.ids[0],'a1')
 expect(drawn(joined)).toEqual(new Set([edge('a1','a2'),edge('a0',chain.ids[0]),edge(chain.ids[0],'a1')]))
 expect(()=>validateDocument(joined,doc)).not.toThrow()
})
it('最终插入可撤销重做，局部联动沿新链经过两个端点',()=>{
 const doc=initial(),chain=add(doc,'a0',[[20,45]])
 const next=insertDrawnPoints(chain.doc,'a','a0','a1',chain.ids)
 const h=commit({past:[],present:chain.doc,future:[]},next)
 expect(undo(h).present).toEqual(chain.doc);expect(redo(undo(h)).present).toEqual(next)
 const linked=prepareMove(next,'a',chain.ids[0],true)!
 expect(linked.byId.has('a0')).toBe(true);expect(linked.byId.has('a1')).toBe(true);expect(linked.byId.has('b0')).toBe(false)
})
it('错误终点、跨曲线、空链或被修改的链不改动原数据',()=>{
 const doc=initial(),chain=add(doc,'a0',[[20,45]]),before=structuredClone(chain.doc)
 for(const target of ['missing','b0','a0'])expect(()=>insertDrawnPoints(chain.doc,'a','a0',target,chain.ids)).toThrow()
 expect(()=>insertDrawnPoints(chain.doc,'a','a0','a1',[])).toThrow()
 const changed=structuredClone(chain.doc);changed.curves[0].points.at(-1)!.connectTo='a2'
 expect(()=>insertDrawnPoints(changed,'a','a0','a1',chain.ids)).toThrow()
 expect(chain.doc).toEqual(before)
})
it('纵轴频率及负向标定仅影响数值，不影响按ID插入',()=>{
 const doc=initial();doc.calibration.direction='y';doc.calibration.frequency={pixels:[100,0],values:[0,10],unit:'THz'}
 const chain=add(doc,'a0',[[20,45]])
 const next=insertDrawnPoints(chain.doc,'a','a0','a1',chain.ids)
 expect(drawn(next)).toEqual(new Set([edge('a1','a2'),edge('a0',chain.ids[0]),edge(chain.ids[0],'a1')]))
 expect(()=>validateDocument(next,doc)).not.toThrow()
})
