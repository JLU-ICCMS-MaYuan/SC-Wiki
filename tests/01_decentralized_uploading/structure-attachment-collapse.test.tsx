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
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
  fireEvent.click(screen.getByRole('option', { name: 'first.cif' }))
  const toggle = screen.getByRole('button', { name: 'Sn · 结构附件' })
  const model = screen.getByTestId('structure-model')
  const content = document.getElementById(toggle.getAttribute('aria-controls')!)!
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await waitFor(() => expect(screen.getByRole('button', { name: 'first.cif' })).toBeVisible())
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(content).not.toBeVisible()
  expect(model).toBeInTheDocument()
  expect(model).not.toBeVisible()
  expect(screen.getByText('待确认')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'first.cif' }))
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
  const toggle = screen.getByRole('button', { name: 'Pb · 结构附件' })
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [new File(['cif'], 'Pb.cif')] } })
  expect(onUpload).toHaveBeenCalledOnce()
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  fireEvent.click(toggle)
  view.rerender(<StructureCandidatePanel materialName="Pb" candidates={[candidate('Pb')]} uploading={false} onChange={onChange} onUpload={onUpload} />)
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByTestId('structure-model')).toBeVisible()
  expect(onChange).not.toHaveBeenCalled()
})
