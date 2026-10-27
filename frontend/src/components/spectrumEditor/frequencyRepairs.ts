import { clone, record, type Document } from './engine'

type Change = [string, number, number]
type Batch = { batch_id: string; direction: 'x' | 'y'; frequency_calibration: Document['calibration']['frequency']; changes: Change[] }
export type FrequencyRepair = Batch & { canUndo: boolean; pointCount: number; maxShiftPx: number }

/** 只解析受限批次；不能用损坏记录执行任意坐标回写。 */
export function latestFrequencyRepair(doc: Document): FrequencyRepair | null {
  const batches=new Map<string,Batch>(),undone=new Set<string>()
  for(const op of doc.operations){
    if(op.kind!=='auto-frequency-repair'&&op.kind!=='undo-frequency-repair')continue
    try{
      const value=JSON.parse(op.detail)
      if(typeof value.batch_id!=='string')continue
      if(op.kind==='undo-frequency-repair'){undone.add(value.batch_id);continue}
      if(!['x','y'].includes(value.direction)||!Array.isArray(value.changes)||!value.changes.length||!value.frequency_calibration)continue
      if(!value.changes.every((c:unknown)=>Array.isArray(c)&&c.length===3&&typeof c[0]==='string'&&Number.isFinite(c[1])&&Number.isFinite(c[2])&&Math.abs(c[2]-c[1])>0&&Math.abs(c[2]-c[1])<=.5))continue
      const batch=batches.get(value.batch_id)
      if(batch){
        if(batch.direction!==value.direction||JSON.stringify(batch.frequency_calibration)!==JSON.stringify(value.frequency_calibration))return null
        batch.changes.push(...value.changes)
      }else batches.set(value.batch_id,value)
    }catch{continue}
  }
  const batch=[...batches.values()].reverse().find(b=>!undone.has(b.batch_id))
  if(!batch)return null
  const points=new Map(doc.curves[0].points.map(p=>[p.id,p]))
  const unique=new Set(batch.changes.map(c=>c[0]))
  const sameAxis=batch.direction===doc.calibration.direction&&JSON.stringify(batch.frequency_calibration)===JSON.stringify(doc.calibration.frequency)
  const [x0,y0,x1,y1]=doc.source.plot
  const low=batch.direction==='x'?x0:y0,high=batch.direction==='x'?x1:y1
  const canUndo=sameAxis&&unique.size===batch.changes.length&&batch.changes.every(([id,before,after])=>before>=low&&before<=high&&points.get(id)?.[batch.direction]===after)
  return {...batch,canUndo,pointCount:batch.changes.length,maxShiftPx:Math.max(...batch.changes.map(c=>Math.abs(c[2]-c[1])))}
}

export function undoFrequencyRepair(doc: Document): Document {
  const batch=latestFrequencyRepair(doc)
  if(!batch?.canUndo)return doc
  const restored=clone(doc),before=new Map(batch.changes.map(([id,value])=>[id,value]))
  for(const point of restored.curves[0].points){
    const pixel=before.get(point.id)
    if(pixel!==undefined){point[batch.direction]=pixel;point.status='撤销自动频率微调';point.manual=true}
  }
  return record(restored,'undo-frequency-repair',JSON.stringify({batch_id:batch.batch_id}))
}
