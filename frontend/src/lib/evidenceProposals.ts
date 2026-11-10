export interface EvidencePatch { key: string; item_key: string; field: string; state_key?: string; module_key?: string; record_key?: string; record_field?: string; record_field_key?: string; record_group_key?: string; record_method_key?: string; values: Record<string, unknown> }
import { setAtPath } from './formDefinitions'
import { setTcMethodValue } from './predictedTcGroups'
export interface PreparedProposals { preparation_id?: string; resume_stage?: 'scientific' | 'finalize'; patches: EvidencePatch[]; version: string }

/** 接受草稿按稳定身份应用，禁止将旧数组下标写到排序后的其他记录。 */
export function applyEvidencePatches<T extends { paper: Record<string, any>; material_states: Array<Record<string, any>> }>(draft: T, patches: EvidencePatch[]): T {
  const next = structuredClone(draft)
  for (const patch of patches) {
    let target: Record<string, any> = next.paper
    if (patch.state_key) {
      target = next.material_states.find(s => s.state_key === patch.state_key)!
      if (!target) throw new Error('建议对应的材料状态已变化，请刷新')
      if (patch.record_key) {
        const module = target.property_modules?.find((m: any) => m.module_key === patch.module_key)
        target = module?.records?.find((r: any) => r.record_key === patch.record_key)
        if (!target) throw new Error('建议对应的科学记录已变化，请刷新')
      }
    }
    const state = next.material_states.find(s => s.state_key === patch.state_key)
    const members = patch.record_group_key ? state?.property_modules?.find((m: any) => m.module_key === patch.module_key)?.records
      .filter((r: any) => r.payload?.tc_group?.group_key === patch.record_group_key
        && (!patch.record_method_key || r.payload?.tc_group?.method_key === patch.record_method_key)) || [] : [target]
    if (!members.length) throw new Error('共同参数组已变化，请刷新')
    for (const [path, value] of Object.entries(patch.values)) {
      if (patch.record_field && path === '') {
        let fieldPath = patch.record_field
        if (patch.record_field_key && fieldPath.includes('.extensions.')) {
          const root = fieldPath.split('.extensions.')[0]
          const entries = root.split('.').reduce((v, k) => v?.[k], target)?.extensions || []
          const index = entries.findIndex((item: any) => (item.field_key || item.key) === patch.record_field_key)
          if (index < 0) throw new Error('补充字段已变化，请刷新')
          fieldPath = fieldPath.replace(/\.extensions\.\d+/, `.extensions.${index}`)
        }
        for (const member of members) Object.assign(member, ['method_code', 'method_raw'].includes(fieldPath)
          ? setTcMethodValue(member as PropertyRecordDraft, fieldPath as 'method_code' | 'method_raw', value as string | null)
          : setAtPath(member, fieldPath, value))
        continue
      }
      const field = path || patch.field.split('.').at(-1)!
      if (field === 'material_families' || field === 'structure_families') {
        const original = target[field] || []
        target[field] = (value as string[]).map(name => original.find((x: any) => (x.name || x.name_zh) === name) || { name, name_zh: name, status: 'pending', ...(field === 'structure_families' ? { is_primary: false } : {}) })
      } else for (const member of patch.record_method_key && ['method_code', 'method_raw'].includes(field) ? members : [target]) {
        if (['method_code', 'method_raw'].includes(field)) Object.assign(member,
          setTcMethodValue(member as PropertyRecordDraft, field as 'method_code' | 'method_raw', value as string | null))
        else member[field] = value
      }
    }
    if (patch.record_key) for (const member of members) Object.assign(member, normalizeCurrentTcValue(member as PropertyRecordDraft))
  }
  return next
}
import { normalizeCurrentTcValue, type PropertyRecordDraft } from './propertyModules'


/** 普通字段编辑只拷贝实际所属节点；候选批量应用仍使用原入口。 */
export function applySingleEvidenceValue<T extends {paper:Record<string,any>;material_states:Array<Record<string,any>>}>(draft:T, record:Omit<EvidencePatch,'values'>, value:unknown):T {
  const patch={...record,values:{'':value}}
  if(!record.state_key){
    const key=record.field.split('.').at(-1)!
    const actual=['material_families','structure_families'].includes(key)
      ? (value as string[]).map(name=>(draft.paper[key] || []).find((x:any)=>(x.name || x.name_zh)===name)
        || {name,name_zh:name,status:'pending'}) : value
    return {...draft,paper:{...draft.paper,[key]:actual}}
  }
  const si=draft.material_states.findIndex(s=>s.state_key===record.state_key)
  if(si<0)throw new Error('当前材料状态已移除')
  const state=draft.material_states[si]
  let next:Record<string,any>
  if(!record.record_key){
    next=applyEvidencePatches({paper:{},material_states:[{state_key:state.state_key,
      [record.field.split('.').at(-1)!]:state[record.field.split('.').at(-1)!]}]},[patch]).material_states[0]
    next={...state,...next}
  }else{
    const mi=state.property_modules.findIndex((m:any)=>m.module_key===record.module_key)
    if(mi<0)throw new Error('当前物性模块已移除')
    const module=state.property_modules[mi]
    const affected=record.record_group_key?module.records.filter((r:any)=>r.payload?.tc_group?.group_key===record.record_group_key
      && (!record.record_method_key || r.payload?.tc_group?.method_key===record.record_method_key))
      :module.records.filter((r:any)=>r.record_key===record.record_key)
    if(!affected.length)throw new Error('当前物性记录已移除')
    const subset={paper:{},material_states:[{state_key:state.state_key,property_modules:[{...module,records:affected}]}]}
    const changed=applyEvidencePatches(subset,[patch]).material_states[0].property_modules[0].records
    const replacements=new Map(changed.map((r:any)=>[r.record_key,r]))
    next={...state,property_modules:state.property_modules.map((m:any,i:number)=>i===mi?{...module,
      records:module.records.map((r:any)=>replacements.get(r.record_key)||r)}:m)}
  }
  return {...draft,material_states:draft.material_states.map((s,i)=>i===si?next:s)}
}
