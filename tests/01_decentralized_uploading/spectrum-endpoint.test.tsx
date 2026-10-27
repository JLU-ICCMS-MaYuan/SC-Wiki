import { expect,it } from 'vitest'
import { automaticConnections, undoAutomaticConnections, commit,undo,redo,type Document } from '../../frontend/src/components/spectrumEditor/engine'
const data=():Document=>({schemaVersion:1,id:'test',title:'α²F',description:'测试',
 source:{id:'source',sha256:'hash',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},
 calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,1],unit:'dimensionless'},amplitudeEvidence:'原图刻度'},
 curves:[{id:'a',name:'α²F',color:'red',pathOrdered:true,points:[{id:'p0',x:0,y:100,segment:'one',status:'manual_adjusted',breakBefore:true},{id:'p1',x:60,y:80,segment:'one',status:'manual_adjusted',breakBefore:false}]}],
 zero:{pixel:0,pointIds:['p0']},operations:[]})

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
