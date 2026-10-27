import { expect,it } from 'vitest'
import { confirmHighEndpoint, highEndpointValid, automaticConnections, undoAutomaticConnections, commit,undo,redo,type Document } from '../../frontend/src/components/spectrumEditor/engine'
const data=():Document=>({schemaVersion:1,id:'test',title:'α²F',description:'测试',
 source:{id:'source',sha256:'hash',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},
 calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,1],unit:'dimensionless'},amplitudeEvidence:'原图刻度'},
 curves:[{id:'a',name:'α²F',color:'red',pathOrdered:true,points:[{id:'p0',x:0,y:100,segment:'one',status:'manual_adjusted',breakBefore:true},{id:'p1',x:60,y:80,segment:'one',status:'manual_adjusted',breakBefore:false}]}],
 zero:{pixel:0,pointIds:['p0']},highEndpoint:null,operations:[]})

it('真实截止低于图框上沿也可确认，点坐标不改变并可撤销重做',()=>{
 const doc=data(),next=confirmHighEndpoint(doc,'p1','原图红线在6THz终止')
 expect(highEndpointValid(next)).toBe(true)
 expect(next.curves).toBe(doc.curves);expect(next.highEndpoint?.frequencyTHz).toBe(6)
 const h=commit({past:[],present:doc,future:[]},next)
 expect(highEndpointValid(undo(h).present)).toBe(false)
 expect(highEndpointValid(redo(undo(h)).present)).toBe(true)
 expect(()=>confirmHighEndpoint(doc,'p0','不是真实高端')).toThrow('最高频点')
})
it('移动末端、删除末端、改频率标定或新增更高点后证据失效',()=>{
 const next=confirmHighEndpoint(data(),'p1','原图依据')
 for(const change of [
  (d:Document)=>{d.curves[0].points[1].y++},
  (d:Document)=>{d.curves[0].points.pop()},
  (d:Document)=>{d.calibration.frequency.values[1]=20},
  (d:Document)=>{d.curves[0].points.push({...d.curves[0].points[1],id:'new',x:70})}
 ]){
  const edited=structuredClone(next);change(edited);expect(highEndpointValid(edited)).toBe(false)
 }
})
it('自动连接可显式撤销，保留全部坐标且常规撤销能恢复连接',()=>{
 const doc=data();doc.curves[0].points[0].joinTo='p1'
 doc.operations=[{kind:'auto-connect-exact-endpoints',at:'test',detail:JSON.stringify({from_id:'p0',to_id:'p1'})}]
 expect(automaticConnections(doc)).toHaveLength(1)
 const next=undoAutomaticConnections(doc)
 expect(next.curves[0].points).toEqual(doc.curves[0].points.map(({joinTo,...p})=>p))
 expect(automaticConnections(next)).toHaveLength(0)
 const h=commit({past:[],present:doc,future:[]},next)
 expect(automaticConnections(undo(h).present)).toHaveLength(1)
})
