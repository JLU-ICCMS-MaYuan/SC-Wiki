import { expect, it } from 'vitest'
import { applyEvidencePatches } from '../../frontend/src/lib/evidenceProposals'
import { currentEvidenceField, evidenceFieldAffected } from '../../frontend/src/lib/evidenceFields'
const record=(key:string,group='g',mu=.1):any=>({record_key:key,record_type:'predicted_tc',value_kind:'number',value_number:311,value_raw:'311',unit_raw:'K',
 payload:{tc_group:{version:1,group_key:group,method_key:'method',point_key:key},parameters:{lambda_ep:3.94,mu_star:mu},calculation_conditions:{extensions:[{field_key:'a',value_kind:'number',value_number:80},{field_key:'b',value_kind:'text',value_text:'保留'}]}}})
const draft=()=>({paper:{},material_states:[{state_key:'s',property_modules:[{module_key:'m',records:[record('r1','g',.16),record('r2'),record('r3','other')]}]}]})
it('共同字段建议只传播同状态同模块的明确分组，保留各点μ和独立组',()=>{
 const input=draft(),result=applyEvidencePatches(input,[{key:'k',item_key:'k',field:'unused',state_key:'s',module_key:'m',record_key:'r1',record_field:'payload.parameters.lambda_ep',record_group_key:'g',values:{'':3.95}}])
 const points=result.material_states[0].property_modules[0].records
 expect(points.map(r=>r.payload.parameters.lambda_ep)).toEqual([3.95,3.95,3.94])
 expect(points.map(r=>r.payload.parameters.mu_star)).toEqual([.16,.1,.1])
 expect(input.material_states[0].property_modules[0].records[0].payload.parameters.lambda_ep).toBe(3.94)
})
it('补充字段按稳定key写入当前顺序，不依服务器旧数组下标',()=>{
 const input=draft();input.material_states[0].property_modules[0].records[0].payload.calculation_conditions.extensions.reverse()
 const result=applyEvidencePatches(input,[{key:'k',item_key:'k',field:'unused',state_key:'s',module_key:'m',record_key:'r1',record_field:'payload.calculation_conditions.extensions.0',record_field_key:'a',values:{'':{field_key:'a',value_kind:'number',value_number:90}}}])
 expect(result.material_states[0].property_modules[0].records[0].payload.calculation_conditions.extensions.map((x:any)=>x.field_key)).toEqual(['b','a'])
 expect(result.material_states[0].property_modules[0].records[0].payload.calculation_conditions.extensions[1].value_number).toBe(90)
})
it('μ范围重排后仍按自身key读取配对端点及当前定位路径',()=>{
 const input=draft(),r=input.material_states[0].property_modules[0].records[0];r.payload.parameters.extensions=[{key:'other'},{key:'mu_star',value_kind:'range',value_min:.1,value_max:.16}]
 const field:any={record_key:'r1',module_key:'m',state_key:'s',record_field:'payload.parameters.extensions.0.value_max',record_field_key:'mu_star',field:'material_states[0].property_modules[0].records[0].payload.parameters.extensions.0.value_max'}
 const actual=currentEvidenceField(field,{},input.material_states)
 expect(actual?.value).toBe(.16);expect(actual?.field).toContain('extensions.1.value_max')
})
it('方法变化仅影响具有真实依赖的结果，不把λ同步标红',()=>{
 const root='material_states[0].property_modules[0].records[0].'
 const tc:any={field:root+'value_number',record_field:'value_number',record_dependencies:['method_code','payload.parameters.mu_star']}
 const lambda:any={field:root+'payload.parameters.lambda_ep',record_field:'payload.parameters.lambda_ep',record_dependencies:['payload.calculation_conditions']}
 expect(evidenceFieldAffected(tc,root+'method_code')).toBe(true)
 expect(evidenceFieldAffected(tc,root+'payload.parameters.mu_star')).toBe(true)
 expect(evidenceFieldAffected(lambda,root+'method_code')).toBe(false)
})
