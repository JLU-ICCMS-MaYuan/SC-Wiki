import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import PaperMaterialsSection from '../../frontend/src/components/PaperMaterialsSection'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { researchMaterials } from '../../frontend/src/lib/paperMaterials'
import type { EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'

afterEach(cleanup)

it('研究材料按名称优先汇总', () => {
  expect(researchMaterials([{ material_name: ' Tin ', material: 'Sn' }, { material_name: 'Tin' }, { material: 'Pb' }, {}])).toEqual(['Tin', 'Pb'])
})

it('同名材料汇总后只显示研究材料，不提供退役关系控件', () => {
  const view = render(<PaperMaterialsSection states={[{ material_name: 'Tin', material: 'Sn' }, { material_name: 'Tin', material: 'Sn' }]} />)
  expect(screen.getAllByRole('button', { name: /Tin · #/ })).toHaveLength(2)
  expect(screen.queryByText('材料关系')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '添加材料关系' })).not.toBeInTheDocument()
  view.rerender(<PaperMaterialsSection states={[{ material_name: 'Pure tin', material: 'Sn' }]} />)
  expect(screen.getByText('Pure tin (Sn)')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
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
