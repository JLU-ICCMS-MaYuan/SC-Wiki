import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import { conditionName } from '../../frontend/src/components/CalculationConditionFields'
import type { PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'

afterEach(cleanup)
const row = (): PropertyRecordDraft => ({ record_key:'phonon-172', module_code:'superconductive_properties',
  record_type:'predicted_tc', property_code:'tc', method_code:'allen_dynes', name_raw:'Tc',
  definition_key:'record.superconductive_properties.predicted_tc.allen_dynes', definition_version:1,
  value_kind:'number', value_number:220, value_raw:'220', unit_raw:'K', canonical_unit:'K',
  payload:{calculation_conditions:{calculation_code:'Quantum ESPRESSO', extensions:[{
    key:'electron_phonon.phonon_method', name:'electron_phonon · phonon_method', value_kind:'text', value_raw:'DFPT',
  }] }}, evidences:[{file_id:'main',pdf_page:1,block_id:'b1',quote:'Phonons use DFPT.'}] })

it('声子方法在超导计算条件中编辑并保存重开，阶段与来源保留', () => {
  let saved = row()
  function Harness() {
    const [value,setValue] = useState(saved)
    return <SchemaDrivenRecordForm record={value} onChange={next=>{saved=JSON.parse(JSON.stringify(next));setValue(next)}} />
  }
  const first = render(<Harness />)
  expect(screen.getByRole('button', {name:'设置字段：声子方法'})).toBeVisible()
  fireEvent.change(screen.getByLabelText('声子方法'), {target:{value:'finite displacement'}})
  expect((saved.payload.calculation_conditions as any).extensions[0].key).toBe('electron_phonon.phonon_method')
  expect(saved.evidences).toEqual(row().evidences)
  first.unmount()
  render(<SchemaDrivenRecordForm record={saved} onChange={vi.fn()} />)
  expect(screen.getByLabelText('声子方法')).toHaveValue('finite displacement')
})

it('自动声子方法不加阶段前缀，人工名称与其他条件名称保留', () => {
  expect(conditionName({key:'electron_phonon.phonon_method'})).toBe('声子方法')
  expect(conditionName({key:'electron_phonon.phonon_method',name_raw:'我的声子方法'})).toBe('我的声子方法')
  expect(conditionName({key:'sscha.energy_cutoff'})).toBe('SSCHA · 截断能')
})
