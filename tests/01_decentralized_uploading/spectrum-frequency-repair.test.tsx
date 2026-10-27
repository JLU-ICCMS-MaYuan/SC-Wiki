import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { latestFrequencyRepair, undoFrequencyRepair } from '../../frontend/src/components/spectrumEditor/frequencyRepairs'
import FrequencyRepairReport from '../../frontend/src/components/spectrumEditor/FrequencyRepairReport'
import { commit, undo, redo, type Document } from '../../frontend/src/components/spectrumEditor/engine'

afterEach(cleanup)
function document():Document {
 const axis={pixels:[0,20],values:[0,20],unit:'THz'} as Document['calibration']['frequency']
 return {schemaVersion:1,id:'a',title:'谱',description:'',source:{id:'source',sha256:'hash',image:'',width:21,height:21,plot:[0,0,20,20],viewport:[0,0,20,20]},
 calibration:{direction:'x',frequency:axis,amplitude:{pixels:[0,20],values:[0,20],unit:'pixel'}},
 curves:[{id:'a',name:'H',color:'green',pathOrdered:true,points:[
  {id:'p0',x:0,y:0,status:'原点',segment:'a'},{id:'p1',x:4.8999995,y:5,status:'自动频率微调',segment:'a'},
  {id:'p2',x:4.9000005,y:7,status:'自动频率微调',segment:'a'},{id:'p3',x:10,y:2,status:'原点',segment:'a'}]}],
 zero:{pixel:0,pointIds:['p0']},operations:[
  {kind:'auto-frequency-repair',at:'test',detail:JSON.stringify({batch_id:'b',direction:'x',frequency_calibration:axis,changes:[['p1',5,4.8999995]]})},
  {kind:'auto-frequency-repair',at:'test',detail:JSON.stringify({batch_id:'b',direction:'x',frequency_calibration:axis,changes:[['p2',4.8,4.9000005]]})}
 ]}
}
it('分片批次合并，撤销仅恢复频率坐标，保存意图进入操作记录',()=>{
 const doc=document(),before=structuredClone(doc),batch=latestFrequencyRepair(doc)!
 expect(batch.pointCount).toBe(2);expect(batch.canUndo).toBe(true)
 const restored=undoFrequencyRepair(doc)
 expect(restored.curves[0].points.map(p=>p.x)).toEqual([0,5,4.8,10])
 expect(restored.curves[0].points.map(p=>p.y)).toEqual(doc.curves[0].points.map(p=>p.y))
 expect(doc).toEqual(before)
 expect(latestFrequencyRepair(restored)).toBeNull()
 expect(restored.operations.at(-1)?.kind).toBe('undo-frequency-repair')
 const history=commit({past:[],present:doc,future:[]},restored)
 expect(undo(history).present).toEqual(doc)
 expect(redo(undo(history)).present).toEqual(restored)
})
it.each(['frequency','calibration','deleted'])('后续%s变化阻止直接撤销覆盖',kind=>{
 const doc=document()
 if(kind==='frequency')doc.curves[0].points[1].x=4.7
 if(kind==='calibration')doc.calibration.frequency.values=[0,30]
 if(kind==='deleted')doc.curves[0].points.splice(1,1)
 expect(latestFrequencyRepair(doc)?.canUndo).toBe(false)
 expect(undoFrequencyRepair(doc)).toBe(doc)
})
it('后续只改幅值时，撤销频率保留新的幅值',()=>{
 const doc=document();doc.curves[0].points[1].y=13
 const restored=undoFrequencyRepair(doc)
 expect(restored.curves[0].points[1]).toMatchObject({x:5,y:13})
})
it('越限或空批次不能用于回写坐标',()=>{
 for(const changes of [[],[['p1',12,4.8999995]]]){
  const doc=document();doc.operations=[{kind:'auto-frequency-repair',at:'test',detail:JSON.stringify({batch_id:'bad',direction:'x',frequency_calibration:doc.calibration.frequency,changes})}]
  expect(latestFrequencyRepair(doc)).toBeNull();expect(undoFrequencyRepair(doc)).toBe(doc)
 }
})
it('已处理修正无论首次或刷新都不显示清单，仅未处理原因保留',()=>{
 const report={curve_id:'a',name:'H',new_point_count:2,point_count:17,max_shift_px:.234,
 points:[{point_id:'p1',x:5,y:3,shift_px:.234},{point_id:'p2',x:4,y:5,shift_px:.234}],skipped:[] as {reason:string}[]}
 const before=structuredClone(report)
 const {container,rerender}=render(<FrequencyRepairReport reports={[report]}/>)
 expect(container).toBeEmptyDOMElement()
 rerender(<FrequencyRepairReport reports={[{...report,new_point_count:0}]}/>)
 expect(container).toBeEmptyDOMElement()
 rerender(<FrequencyRepairReport reports={[{...report,skipped:[{reason:'超过0.5原图像素'}]}]}/>)
 expect(screen.getByText(/未自动修正.*超过0.5/)).toBeVisible()
 expect(screen.queryByRole('button')).toBeNull()
 expect(screen.queryByText(/自动频率微调：当前/)).toBeNull()
 expect(screen.queryByText(/最大移动/)).toBeNull()
 expect(report).toEqual(before)
})
