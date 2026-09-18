import React, { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import PaperMaterialsSection from '../../frontend/src/components/PaperMaterialsSection'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { parseMaterialRelations, researchMaterials } from '../../frontend/src/lib/paperMaterials'
import type { EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'

afterEach(cleanup)

it('历史关系解析不损失来源，非法历史值不被清空', () => {
  const relation = { material: 'Sn', relation: 'investigates', page: 2, quote: 'source', evidence: { file_id: 'a' } }
  expect(parseMaterialRelations(JSON.stringify([relation]))).toEqual([relation])
  expect(parseMaterialRelations([relation])).toEqual([relation])
  expect(parseMaterialRelations(null)).toEqual([])
  expect(parseMaterialRelations('invalid JSON')).toBeNull()
  expect(parseMaterialRelations('["old free text"]')).toBeNull()
  expect(researchMaterials([{ material_name: ' Tin ', material: 'Sn' }, { material_name: 'Tin' }, { material: 'Pb' }, {}])).toEqual(['Tin', 'Pb'])
})

it('关系增删改保留未知来源字段，名称变更更新汇总，详情只读', () => {
  const source = { material: 'Sn', relation: 'investigates', page: 2, quote: 'source evidence' }
  let saved: unknown
  function Form() {
    const [relations, setRelations] = useState([source])
    return <PaperMaterialsSection states={[{ material_name: 'Tin', material: 'Sn' }, { material_name: 'Tin', material: 'Sn' }]} relations={relations} onChange={values => { saved = values; setRelations(values as typeof relations) }} />
  }
  const view = render(<Form />)
  fireEvent.change(screen.getByLabelText('论文与该材料的关系'), { target: { value: 'Very long relationship '.repeat(15) } })
  expect(saved).toEqual([{ ...source, relation: 'Very long relationship '.repeat(15) }])
  fireEvent.click(screen.getByRole('button', { name: '添加材料关系' }))
  expect(screen.getAllByLabelText('论文与该材料的关系')).toHaveLength(2)
  fireEvent.click(screen.getAllByRole('button', { name: '删除材料关系' })[1])
  expect(screen.getAllByLabelText('论文与该材料的关系')).toHaveLength(1)
  view.rerender(<PaperMaterialsSection states={[{ material_name: 'Pure tin', material: 'Sn' }]} relations={saved} />)
  expect(screen.getByText('Pure tin (Sn)')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByText('source evidence')).not.toBeInTheDocument()
})

it('未选中的结构不挂到当前模型，缺失状态不按旧数组索引误挂；清单不输出原始值', async () => {
  const open = vi.fn()
  const records: EvidenceRecord[] = [
    { key: 'other-structure', state_key: 'tin', structure_hash: 'other', field: 'material_states[0].structures[1]', label: '晶体结构', status: 'missing', reason: '', evidences: [], current_value: { secretRaw: 'must not display' } },
    { key: 'removed', state_key: 'deleted', field: 'material_states[0].state_kind', label: '材料状态类型', status: 'uncertain', reason: '', evidences: [] },
  ]
  const form = (hash: string) => <div data-evidence-scope="layout">
    <EvidenceFieldMarkers records={records} scope="layout" onOpen={open} onChange={() => {}} />
    <div data-state-key="tin" data-state-label="Sn" data-material-state-index="0">
      <div data-issue-field="material_states[0].state_kind" data-testid="kind">实验</div>
      <section data-scientific-structure data-structure-hash={hash} data-testid="structure"><h3>Sn.cif</h3></section>
    </div>
  </div>
  const view = render(form('selected'))
  await waitFor(() => expect(view.container.querySelector('[data-evidence-fallback]')).toHaveTextContent('待定位的来源核对（2）'))
  expect(screen.getByTestId('structure')).not.toHaveAttribute('data-evidence-problem')
  expect(screen.getByTestId('kind')).not.toHaveAttribute('data-evidence-problem')
  expect(screen.queryByText(/must not display/)).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: /Sn.*晶体结构/ }))
  expect(open).toHaveBeenCalledWith('other-structure')
  view.rerender(form('other'))
  await waitFor(() => expect(screen.getByTestId('structure')).toHaveAttribute('data-evidence-problem', 'true'))
  expect(within(screen.getByTestId('structure')).getByRole('button', { name: 'Sn.cif' })).toBeInTheDocument()
  expect(view.container.querySelector('[data-evidence-fallback]')).toHaveTextContent('待定位的来源核对（1）')
})
