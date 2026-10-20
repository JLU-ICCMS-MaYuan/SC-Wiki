import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import PaperStructuralWorkspace from '../../frontend/src/components/PaperStructuralWorkspace'
import { StructuralResults } from '../../frontend/src/components/PaperStructuralCollection'
import StructuralRecordPage from '../../frontend/src/pages/StructuralRecordPage'
import { mergeStructuralPreview } from '../../frontend/src/lib/structuralRecords'
import { normalizeUploadDraft, type StructureCandidate } from '../../frontend/src/lib/paperProcessing'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn(), download: vi.fn() } }))
vi.mock('../../frontend/src/components/CrystalStructureView', () => ({ default: () => <div>已挂载结构查看器</div> }))
const candidate: StructureCandidate = { candidate_id: 'model', status: 'valid', confirmation: 'unreviewed', retention: 'pending', material_state_ref: 'unassigned:source',
  reported_structure: { material: 'LaSc2', space_group_symbol: 'Fddd', pressure_value_gpa: 300 },
  representations: { conventional: { cif: { text: 'data_test', available: true }, poscar: { text: 'test', available: true } } },
  sources: [{ filename: 'supp.pdf', page: 8, table: 'Table S1', quote: 'La (8b) 0 0 0.500' }] }
const observation = { record_key: 'lattice', material: 'LaSc2H24', pressure_value_gpa: 300, calculation_label: 'Harmonic', retention: 'pending' as const,
  cell_parameters: { a: 4.735, c: 3.216 }, derived_cell_parameters: { b: 4.735, alpha: 90, beta: 90, gamma: 120 },
  sources: [{ filename: 'supp.pdf', page: 9, quote: '300 4.735 3.216' }] }
beforeEach(() => { vi.mocked(api.post).mockResolvedValue({ items: [], total: 0 }); vi.mocked(api.download).mockResolvedValue(new Blob(['content'])) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('未关联结构可独立保留，不把保留决定改为状态规范几何确认', () => {
  const onCandidates = vi.fn()
  render(<PaperStructuralWorkspace candidates={[candidate]} observations={[observation]} onCandidates={onCandidates} onObservations={vi.fn()} />)
  expect(screen.getAllByText(/LaSc2 · Fddd · 300/)[0]).toBeVisible()
  expect(screen.getAllByText(/尚未关联材料状态/).length).toBeGreaterThan(0)
  fireEvent.click(screen.getByRole('button', { name: '保留此结构' }))
  expect(onCandidates.mock.calls[0][0][0]).toMatchObject({ retention: 'retained', material_state_ref: 'unassigned:source', confirmation: 'unreviewed' })
  expect(screen.getByText(/原文未报告原子位置/)).toBeVisible()
  expect(screen.getByText(/a = 4.735，c = 3.216/)).toBeVisible()
  expect(screen.getByRole('button', { name: '下载 JSON' })).toBeVisible()
  expect(screen.getAllByRole('button', { name: '下载 CIF' })).toHaveLength(1)
})

it('重提取先预览数量，明确应用前不修改表单', async () => {
  const apply = vi.fn(), read = vi.fn(async () => ({ structure_candidates: [candidate], structural_observations: [observation], structural_extraction_issues: [], model_calls: 0 }))
  render(<PaperStructuralWorkspace candidates={[]} observations={[]} onCandidates={vi.fn()} onObservations={vi.fn()} onReextract={read} onApplyPreview={apply} />)
  fireEvent.click(screen.getByRole('button', { name: '重新读取结构资料' }))
  expect(await screen.findByText(/1 个模型候选，1 条晶格观测/)).toBeVisible()
  expect(apply).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '应用预览到表单' }))
  expect(apply).toHaveBeenCalledTimes(1)
})

it('重提取保留人工决定与结构附件，同来源新结果只出现一次', () => {
  const retained = { ...candidate, retention: 'retained' as const }
  const fresh = { ...candidate, retention: 'pending' as const }
  expect(mergeStructuralPreview([retained], [fresh])).toEqual([retained])
  expect(mergeStructuralPreview([fresh], [fresh])).toEqual([fresh])
  const raw = normalizeUploadDraft({ paper: {}, material_states: [], structure_candidates: [retained], structural_observations: [observation], structural_extraction_version: 'v1' })
  expect(raw.structural_observations).toEqual([observation])
})

it('元素检索展示无Tc结构、来源论文和模型入口，支持下一页', async () => {
  vi.mocked(api.post).mockResolvedValue({ items: [{ id: 'record', kind: 'model', material: 'LaSc2', pressure_gpa: 300, space_group: 'Fddd',
    title: 'Original paper', doi: '10.1000/source', paper_id: 7, retention: 'retained', data: candidate }], total: 21 })
  render(<MemoryRouter><StructuralResults query={{ elements: ['La', 'Sc'], mode: 'elements_exact_search' }} /></MemoryRouter>)
  expect(await screen.findByText(/LaSc2 · 300 GPa · Fddd/)).toBeVisible()
  expect(screen.getByText(/Original paper/)).toHaveTextContent('10.1000/source')
  expect(screen.getByRole('link', { name: '查看结构与下载' })).toHaveAttribute('href', '/structures/record')
  expect(screen.getByRole('link', { name: '查看来源论文' })).toHaveAttribute('href', '/papers/7')
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/api/rag/structural-records/search', expect.objectContaining({ offset: 20 })))
})

it('接口失败明确显示，不能伪装成没有结构数据', async () => {
  vi.mocked(api.post).mockRejectedValue(new Error('资料存储尚未升级'))
  render(<MemoryRouter><StructuralResults query={{ elements: ['La', 'Sc'] }} /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('资料存储尚未升级')
  expect(screen.queryByText('暂无符合条件的已批准结构资料。')).not.toBeInTheDocument()
})

it('结构详情读取来源并按记录鉴权接口下载，部分观测没有CIF入口', async () => {
  vi.mocked(api.get).mockResolvedValue({ id: 'partial', kind: 'lattice', material: 'LaSc2H24', paper_id: 8, paper_revision: 2, title: 'Source', data: observation })
  render(<MemoryRouter initialEntries={['/structures/partial']}><Routes><Route path="/structures/:recordId" element={<StructuralRecordPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText(/来源：Source/)).toBeVisible()
  expect(screen.queryByRole('button', { name: '下载 CIF' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '下载 CSV' })).toBeVisible()
})
