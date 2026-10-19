import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { api } from '../../frontend/src/lib/api'
import type { UploadDraft } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
vi.mock('../../frontend/src/lib/classifications', async original => ({
  ...await original<typeof import('../../frontend/src/lib/classifications')>(),
  loadClassificationCatalogs: vi.fn(async () => ({ material_families: [], structure_families: [], material_dimensionalities: [] })),
}))
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async path => path.startsWith('/api/rag/spectra?') ? {
    items: [{ id: 'spectrum', version: 1, state_key: null, stale: false, source: { source_name: 'paper.pdf', pdf_page: 3 },
      run: { id: 'run', status: 'succeeded' }, review: {}, result: { curves: [{ id: 'a', kind: 'alpha2f', unit: '1', points: [] }] } }],
    jobs: [], version: 'v1', can_edit: true, can_review: false,
  } as never : { space_groups: [] } as never)
  vi.mocked(api.post).mockResolvedValue({ records: [], sources: [], needs_check: false, version: 'v1' } as never)
  vi.mocked(api.put).mockResolvedValue({ ok: true } as never)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mountEditor() {
  const draft = { paper: { title: '原始标题', authors: [], paper_type: 'experimental', superconductor_kind: 'unknown', keywords_tags: [], methodology: [], material_families: [] }, material_states: [], structure_candidates: [], field_evidence: {} } as unknown as UploadDraft
  render(<MemoryRouter initialEntries={['/upload']}><Routes>
    <Route path="/upload" element={<UploadTaskEditor taskId="task" draftOverride={draft} onSubmitted={vi.fn()} />} />
    <Route path="/spectra/:collectionId" element={<div>已打开谱详情</div>} />
  </Routes></MemoryRouter>)
}

it('已保存的主表单直接打开谱，不因无关字段重新校验而拦截', async () => {
  vi.mocked(api.put).mockRejectedValue(new Error('不应发起保存'))
  mountEditor()
  fireEvent.click(await screen.findByRole('button', { name: '核对归属' }))
  expect(await screen.findByText('已打开谱详情')).toBeVisible()
  expect(api.put).not.toHaveBeenCalled()
})

it('未保存的改动先成功持久化，再进入谱详情', async () => {
  mountEditor()
  fireEvent.change(await screen.findByLabelText('标题'), { target: { value: '修改后标题' } })
  fireEvent.click(await screen.findByRole('button', { name: '核对归属' }))
  expect(await screen.findByText('已打开谱详情')).toBeVisible()
  expect(api.put).toHaveBeenCalledWith('/api/rag/upload-tasks/task/draft', expect.objectContaining({ paper: expect.objectContaining({ title: '修改后标题' }) }))
})

it('保存失败时谱入口显示后端具体原因并保留当前表单', async () => {
  vi.mocked(api.put).mockRejectedValue({ detail: { code: 'draft_conflict', message: '草稿版本冲突，请刷新后核对' } })
  mountEditor()
  fireEvent.change(await screen.findByLabelText('标题'), { target: { value: '保留当前输入' } })
  fireEvent.click(await screen.findByRole('button', { name: '核对归属' }))
  await waitFor(() => expect(screen.getAllByText(/草稿版本冲突，请刷新后核对/).length).toBeGreaterThan(0))
  expect(screen.getByLabelText('标题')).toHaveValue('保留当前输入')
  expect(screen.queryByText('已打开谱详情')).not.toBeInTheDocument()
})
