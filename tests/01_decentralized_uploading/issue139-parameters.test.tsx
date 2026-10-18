import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import SchemaDrivenRecordForm from '../../frontend/src/components/SchemaDrivenRecordForm'
import ScientificAssociations from '../../frontend/src/components/ScientificAssociations'
import type { PropertyRecordDraft } from '../../frontend/src/lib/propertyModules'
import { readTcPairs } from '../../frontend/src/lib/tcParameters'

afterEach(cleanup)
const row = (): PropertyRecordDraft => ({ record_key:'table1-a150', module_code:'superconductive_properties',
  record_type:'predicted_tc', property_code:'tc', method_code:'isotropic_eliashberg', name_raw:'Tc',
  definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg', definition_version:1,
  value_kind:'range', value_min:281, value_max:311, value_raw:'281–311', unit_raw:'K', canonical_unit:'K',
  payload:{ parameters:{lambda_ep:3.94,omega_log:745,extensions:[{key:'mu_star',value_kind:'range',value_min:0.1,value_max:0.16,unit_raw:'1'}]},
    calculation_conditions:{k_grid:'24×24×24',extensions:[{key:'sscha.energy_cutoff',name:'SSCHA 截断能',value_kind:'number',value_number:80,value_raw:'80',unit_raw:'Ry'}]},
    source_associations:[{target_path:'/payload/calculation_conditions/k_grid',stage:'electron_phonon',basis_kind:'paper_inference',
      explanation:'Methods 的声子计算设置适用于同物相的不同压力结果，仍需人工核对适用范围。',fact_evidences:[{file_id:'main',chunk_index:0,quote:'24×24×24 k grid'}],
      scope_evidences:[{file_id:'main',chunk_index:0,quote:'For LaSc2H24'}]}] } })

it('显示 150 GPa 两端配对、阶段扩展并保留人工清空', () => {
  const changed=vi.fn()
  function Harness() {
    const [value,setValue]=useState(row())
    return <SchemaDrivenRecordForm record={value} onChange={next=>{changed(next);setValue(next)}} />
  }
  render(<Harness />)
  expect(screen.getByLabelText('电声耦合强度 λ')).toHaveValue('3.94')
  expect(screen.getByLabelText('ωlog')).toHaveValue('745')
  expect(within(screen.getByTestId('tc-pair-0')).getByLabelText('μ*')).toHaveValue('0.16')
  expect(within(screen.getByTestId('tc-pair-1')).getByLabelText('μ*')).toHaveValue('0.1')
  expect(screen.getByRole('button', { name: '设置字段：SSCHA 截断能' })).toBeInTheDocument()
  expect(screen.queryByText('source_associations')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('ωlog'),{target:{value:''}})
  const updated=changed.mock.calls.at(-1)![0]
  expect(updated.payload.parameters.omega_log).toBeNull()
  expect(updated.payload.source_associations).toEqual(row().payload.source_associations)
})

it('只报告 μ* 范围时，两端 μ* 控件保持空白', () => {
  const r=row()
  ;(r.payload.parameters as any).extensions[0].key='mu_star_reported_range'
  expect(readTcPairs(r).map(p=>p.mu)).toEqual([null,null])
  render(<SchemaDrivenRecordForm record={r} onChange={()=>{}} />)
  expect(screen.getAllByLabelText('μ*').map(input=>(input as HTMLInputElement).value)).toEqual(['',''])
})

it('在已有理由入口分别展示参数值/范围来源和失效说明', () => {
  const associations=row().payload.source_associations as any
  const {rerender}=render(<ScientificAssociations associations={associations} />)
  expect(screen.getByText('由本文推断共用范围，待人工核对')).toBeInTheDocument()
  fireEvent.click(screen.getByText('参数值与适用范围的原文'))
  expect(screen.getByText('参数值来源')).toBeInTheDocument()
  expect(screen.getByText('适用范围来源')).toBeInTheDocument()
  expect(screen.getByText(/24×24×24 k grid/)).toBeInTheDocument()
  rerender(<ScientificAssociations associations={[{...associations[0],stale:true}]} />)
  expect(screen.getByText('旧关联已失效，请重新核对')).toBeInTheDocument()
})

it('原始包装元数据和重复 μ* 报告保留在 payload，主表单不重复创建输入', () => {
  const r=row(), p=r.payload.parameters as any
  p.extensions.push({key:'lambda_ep_reported',value_kind:'text',value_raw:'3.94',reported:{value_number:3.94}})
  p.extensions.push({key:'mu_star_reported_range',value_kind:'range',value_min:0.1,value_max:0.16,value_raw:'0.16 to 0.1'})
  render(<SchemaDrivenRecordForm record={r} onChange={()=>{}} />)
  expect(screen.queryByDisplayValue('lambda_ep_reported')).not.toBeInTheDocument()
  expect(screen.queryByDisplayValue('mu_star_reported_range')).not.toBeInTheDocument()
  expect(p.extensions).toHaveLength(3)
})
