import React, { useState } from 'react'
import '@testing-library/jest-dom/vitest'
import { fireEvent, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { splitMaterialState } from '../../frontend/src/lib/splitMaterialState'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({api:{get:vi.fn(async()=>({items:[],data:{}})),post:vi.fn(),patch:vi.fn()}}))
afterEach(cleanup)
const geometry={structure_text:'original geometry',structure_hash:'original-hash',representations:{},
  validation:{structure_hash:'original-hash'},sources:[{file_id:'si',block_id:'original-row',pdf_page:30}]}
const source:DraftMaterialState={state_key:'source',material:'LaH9',pressure_value_gpa:50,state_kind:'theoretical',
  crystal_system:'monoclinic',reported_space_group_number:9,reported_space_group_symbol:'Cc',structure:geometry,
  property_modules:[{module_key:'module',module_code:'electronic_properties',definition_key:'module.electronic_properties',
    definition_version:1,display_order:0,records:[{record_key:'record',module_code:'electronic_properties',
      property_code:'dos_fermi',record_type:'property',definition_key:'record.electronic_properties.dos_fermi',
      definition_version:1,value_kind:'number',value_number:.01,payload:{},evidences:[{file_id:'main',block_id:'fig4'}]}]}]}
const group={number:194,symbol:'P6_3/mmc',crystalSystem:'hexagonal' as const}

it('preserves exact property/module/source objects and untouched neighbor when moving only structure',()=>{
  const neighbor={state_key:'neighbor',material:'YH10'}
  const before=[source,neighbor]
  const preview={stateKey:'source',state:source,snapshot:JSON.stringify(source)}
  const next=splitMaterialState(before,preview,group,false)
  expect(next[0].state_key).toBe('source')
  expect(next[0].property_modules).toBe(source.property_modules)
  expect(next[0].property_modules![0].records[0].evidences).toBe(source.property_modules![0].records[0].evidences)
  expect(next[1]).toBe(neighbor)
  expect(next[2].structure).toBe(geometry)
  expect(next[2].state_key).not.toBe(source.state_key)
  expect(next[2].property_modules).toEqual([])
  expect(source.structure).toBe(geometry)
  expect(()=>splitMaterialState(next,preview,group,false)).toThrow()
  expect(()=>splitMaterialState(before,preview,group,true)).toThrow()
})

it.each(['edited','deleted','readonly','neighbor'])('%s while preview is open uses current identity and permissions',kind=>{
  const changed=vi.fn()
  function Host(){
    const [states,setStates]=useState<DraftMaterialState[]>([source,{state_key:'neighbor',material:'YH10',property_modules:[]}])
    const [readOnly,setReadOnly]=useState(false)
    return <LanguageProvider>
      <button onClick={()=>kind==='readonly'?setReadOnly(true):setStates(current=>kind==='deleted'
        ?current.filter(s=>s.state_key!=='source'):current.map(s=>s.state_key===(kind==='neighbor'?'neighbor':'source')?{...s,material_name:'changed'}:s))}>concurrent</button>
      <MaterialStatesEditor states={states} catalogs={null} readOnly={readOnly} spaceGroups={[{number:9,symbol:'Cc'},group]}
        onChange={next=>{changed(next);setStates(next)}} />
    </LanguageProvider>
  }
  render(<Host/> )
  fireEvent.click(screen.getByRole('button',{name:'拆分结构与物性',exact:true}))
  fireEvent.change(screen.getByLabelText('物性状态空间群号'),{target:{value:'194'}})
  // 后台刷新、另一标签编辑或权限收回发生在预览与确认之间。
  fireEvent.click(screen.getByText('concurrent'))
  fireEvent.click(screen.getByRole('button',{name:'确认拆分',exact:true}))
  if(kind==='neighbor'){
    expect(changed).toHaveBeenCalledOnce()
    expect(changed.mock.calls[0][0][1].material_name).toBe('changed')
  }else{
    expect(changed).not.toHaveBeenCalled()
    if(kind==='readonly')expect(screen.getByRole('button',{name:'确认拆分',exact:true})).toBeDisabled()
    else expect(screen.getByText('原状态已变化或不可编辑，请关闭后重新打开预览。')).toBeVisible()
  }
})
