import { expect,it } from 'vitest'
import { canMergeStructureState,mergeStructureState } from '../../frontend/src/lib/splitMaterialState'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'

const geometry={structure_text:'original coordinates',structure_hash:'original',sources:[{file_id:'si',block_id:'table',pdf_page:30}],user_note:'原说明'}
const source:DraftMaterialState={state_key:'structure-only',material:'LaH9',pressure_value_gpa:50,state_kind:'theoretical',
  structure_optimization:'classical_static',reported_space_group_number:9,reported_space_group_symbol:'Cc',crystal_system:'monoclinic',
  structure:geometry,property_modules:[]}
const target:DraftMaterialState={state_key:'properties',material:'LaH9',pressure_value_gpa:50,state_kind:'theoretical',
  structure_optimization:'classical_static',reported_space_group_number:194,reported_space_group_symbol:'P6_3/mmc',crystal_system:'hexagonal',
  property_modules:[{module_key:'original-module',module_code:'electronic_properties',definition_key:'module.electronic_properties',
  definition_version:1,display_order:0,records:[{record_key:'original-record',module_code:'electronic_properties',record_type:'property',
  property_code:'dos_fermi',definition_key:'record.electronic_properties.dos_fermi',definition_version:1,value_kind:'number',value_number:.01,payload:{}}]}]}
const preview=(state:DraftMaterialState)=>({state,snapshot:JSON.stringify(state)})

it('moves only the canonical structure and keeps original property identity, parameters and provenance',()=>{
  const neighbor={state_key:'untouched',material:'YH10'}
  const next=mergeStructureState([source,target,neighbor],preview(source),preview(target),'人工裁定采用Cc',false)
  expect(next.map(x=>x.state_key)).toEqual(['properties','untouched'])
  expect(next[0].property_modules).toBe(target.property_modules)
  expect(next[0].structure?.sources).toBe(geometry.sources)
  expect(next[0].structure?.structure_hash).toBe(geometry.structure_hash)
  expect(next[0].structure?.user_note).toBe('原说明\n\n人工裁定采用Cc')
  expect(next[0].reported_space_group_number).toBe(9)
  expect(next[1]).toBe(neighbor)
  expect(source.structure).toBe(geometry)
})

it.each(['material','pressure','method','occupied','sourceChanged','targetChanged','sourceRemoved','readonly'])(
  'rejects %s without changing either state',kind=>{
    let s={...source},t={...target}
    const ps=preview(s),pt=preview(t)
    if(kind==='material')t.material='CeH9'
    if(kind==='pressure')t.pressure_value_gpa=200
    if(kind==='method')t.structure_optimization='sscha'
    if(kind==='occupied')t.structure=geometry
    if(kind==='sourceChanged')s.material_name='changed'
    if(kind==='targetChanged')t.material_name='changed'
    const states=kind==='sourceRemoved'?[t]:[s,t]
    const before=JSON.stringify(states)
    expect(()=>mergeStructureState(states,ps,pt,'',kind==='readonly')).toThrow()
    expect(JSON.stringify(states)).toBe(before)
  })

it('does not offer a state with other property records as a structure-only source',()=>{
  expect(canMergeStructureState({...source,property_modules:target.property_modules},target)).toBe(false)
})
