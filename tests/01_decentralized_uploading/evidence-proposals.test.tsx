import { expect, it } from 'vitest'
import { applyEvidencePatches, type EvidencePatch } from '../../frontend/src/lib/evidenceProposals'

it('建议按稳定身份写入排序后的原材料记录，并保留其他记录及证据', () => {
 const record={record_key:'same',value_number:4.29,evidences:[{quote:'measured at 4.29 K'}]}
 const draft={paper:{summary:'original'},material_states:[
  {state_key:'Pb',property_modules:[{module_key:'tc',records:[{...record,value_number:7.19}]}]},
  {state_key:'Sn',property_modules:[{module_key:'tc',records:[record]}]},
 ]}
 const patch: EvidencePatch={key:'1',item_key:'s/m/r',field:'material_states[0].property_modules[0].records[0]',state_key:'Sn',module_key:'tc',record_key:'same',values:{value_number:3.78,value_raw:'3.78'}}
 const changed=applyEvidencePatches(draft,[patch])
 expect(changed.material_states[0].property_modules[0].records[0].value_number).toBe(7.19)
 expect(changed.material_states[1].property_modules[0].records[0]).toMatchObject({value_number:3.78,evidences:record.evidences})
 expect(draft.material_states[1].property_modules[0].records[0].value_number).toBe(4.29)
 expect(()=>applyEvidencePatches(draft,[{...patch,state_key:'removed'}])).toThrow(/状态已变化/)
})

it('科学分类的建议保留已有关联身份，新增名称进入待确认分类', () => {
 const draft={paper:{material_families:[{id:1,name:'元素',status:'confirmed'}]},material_states:[]}
 const changed=applyEvidencePatches(draft,[{key:'family',item_key:'family',field:'paper.material_families',values:{'':['元素','合金']}}])
 expect(changed.paper.material_families[0]).toEqual(draft.paper.material_families[0])
 expect(changed.paper.material_families[1]).toMatchObject({name:'合金',status:'pending'})
})
