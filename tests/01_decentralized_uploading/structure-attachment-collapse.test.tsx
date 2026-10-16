import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import StructureCandidatePanel from '../../frontend/src/components/StructureCandidatePanel'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import type { StructureCandidate } from '../../frontend/src/lib/paperProcessing'
import type { EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'

vi.mock('../../frontend/src/components/CrystalStructureView', () => ({
  default: ({ data }: { data: string }) => <div data-testid="structure-model">{data}</div>,
}))
afterEach(cleanup)

const candidate = (id: string): StructureCandidate => ({
  candidate_id: id, status: 'valid', confirmation: 'unreviewed',
  validation: { structure_hash: `hash-${id}` }, sources: [{ filename: `${id}.cif` }],
  representations: { conventional: { cif: { text: `structure ${id}` } } },
})

it('附件独立折叠，保留模型节点、文件选择和来源入口，不触发修改', async () => {
  const onChange = vi.fn(), onUpload = vi.fn(), onOpen = vi.fn(), onEvidenceChange = vi.fn()
  const records: EvidenceRecord[] = [{ key: 'structure', state_key: 'sn', structure_hash: 'hash-first', field: 'material_states[0].structures[0]', label: '晶体结构', status: 'missing', reason: '', evidences: [] }]
  const view = render(<div data-evidence-scope="compact">
    <EvidenceFieldMarkers records={records} scope="compact" onOpen={onOpen} onChange={onEvidenceChange} />
    <div data-state-key="sn"><StructureCandidatePanel materialName="Sn" candidates={[candidate('first'), candidate('second')]} uploading={false} onChange={onChange} onUpload={onUpload} /></div>
  </div>)
  const initialToggle = screen.getByRole('button', { name: /^晶体结构/ })
  expect(initialToggle).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.getByTestId('structure-model')).not.toBeVisible()
  fireEvent.click(initialToggle)
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
  fireEvent.click(screen.getByRole('option', { name: 'first.cif' }))
  const toggle = screen.getByRole('button', { name: /^晶体结构/ })
  const model = screen.getByTestId('structure-model')
  const content = document.getElementById(toggle.getAttribute('aria-controls')!)!
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await waitFor(() => expect(screen.getByRole('button', { name: '来源核对' })).toBeVisible())
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(content).not.toBeVisible()
  expect(model).toBeInTheDocument()
  expect(model).not.toBeVisible()
  expect(screen.getAllByText('待确认').some(node => !node.closest('[hidden]'))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '来源核对' }))
  expect(onOpen).toHaveBeenCalledWith('structure', ['structure'])
  expect(view.container.querySelectorAll('[data-scientific-structure]')).toHaveLength(1)
  fireEvent.click(toggle)
  expect(model).toBeVisible()
  expect(screen.getByTestId('structure-model')).toBe(model)
  expect(screen.getAllByRole('combobox')[0]).toHaveTextContent('first.cif')
  expect(onChange).not.toHaveBeenCalled()
  expect(onUpload).not.toHaveBeenCalled()
  expect(onEvidenceChange).not.toHaveBeenCalled()
})

it('无结构也可以收起，上传或新增候选后自动展开', () => {
  const onUpload = vi.fn(), onChange = vi.fn()
  const view = render(<StructureCandidatePanel materialName="Pb" candidates={[]} uploading={false} onChange={onChange} onUpload={onUpload} />)
  const toggle = screen.getByRole('button', { name: /^晶体结构/ })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByText('该记录暂无结构数据')).not.toBeVisible()
  fireEvent.click(toggle)
  fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [new File(['cif'], 'Pb.cif')] } })
  expect(onUpload).toHaveBeenCalledOnce()
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  fireEvent.click(toggle)
  view.rerender(<StructureCandidatePanel materialName="Pb" candidates={[candidate('Pb')]} uploading={false} onChange={onChange} onUpload={onUpload} />)
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByTestId('structure-model')).toBeVisible()
  expect(onChange).not.toHaveBeenCalled()
})

it('PDF 结构未经 ASE 校验时只显示来源和缺失说明，不渲染三维模型', () => {
  const item = candidate('paper')
  item.source_kind = 'pdf_reported'
  item.validation = { ase_valid: false, message: '原子坐标不完整' }
  item.reported_structure = { cell_parameters: { a: 6.389 } }
  item.sources = [{ filename: 'supp.pdf', page: 4, quote: 'a=6.389 Å' }]
  render(<StructureCandidatePanel candidates={[item]} uploading={false} onChange={vi.fn()} onUpload={vi.fn()} />)
  expect(screen.queryByTestId('structure-model')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^晶体结构/ }))
  expect(screen.getByText('原子坐标不完整')).toBeInTheDocument()
  expect(screen.getByText('a=6.389')).toBeInTheDocument()
  expect(screen.getByText(/a=6.389 Å/)).toBeInTheDocument()
})


it('同卡已有规范几何时不能再采纳第二份；原胞和格式仍可切换', () => {
  const onChange = vi.fn()
  const confirmed = { ...candidate('first'), confirmation: 'confirmed', status: 'confirmed' } as StructureCandidate
  render(<StructureCandidatePanel candidates={[confirmed, candidate('second')]} uploading={false} onUpload={vi.fn()} onChange={onChange} />)
  fireEvent.click(screen.getByRole('button', { name: /^晶体结构/ }))
  expect(screen.getByRole('button', { name: '采用此结构' })).toBeDisabled()
  expect(screen.getByText(/每张状态卡只保存一份结构几何/)).toBeVisible()
  expect(screen.getAllByRole('combobox')).toHaveLength(3)
  fireEvent.click(screen.getByRole('button', { name: '采用此结构' }))
  expect(onChange).not.toHaveBeenCalled()
})


it('只读仍能展开并切换视图，没有上传、采用、排除或恢复入口', () => {
  const onChange = vi.fn(), onUpload = vi.fn()
  const item = candidate('readonly')
  item.representations!.primitive = { cif: { text: 'primitive readonly' } }
  const view = render(<StructureCandidatePanel readOnly candidates={[item]} uploading={false} onChange={onChange} onUpload={onUpload} />)
  fireEvent.click(screen.getByRole('button', { name: /^晶体结构/ }))
  expect(screen.getByTestId('structure-model')).toBeVisible()
  expect(view.container.querySelector('input[type="file"]')).toBeNull()
  expect(screen.queryByRole('button', { name: /采用此结构|不采用|恢复为待确认/ })).not.toBeInTheDocument()
  fireEvent.mouseDown(screen.getByRole('combobox', { name: '晶胞表示' }))
  fireEvent.click(screen.getByRole('option', { name: '原胞' }))
  expect(screen.getByTestId('structure-model')).toHaveTextContent('primitive readonly')
  const toggle = screen.getByRole('button', { name: /^晶体结构/ })
  fireEvent.click(toggle)
  fireEvent.click(toggle)
  expect(screen.getByRole('combobox', { name: '晶胞表示' })).toHaveTextContent('原胞')
  expect(onChange).not.toHaveBeenCalled()
  expect(onUpload).not.toHaveBeenCalled()
})
