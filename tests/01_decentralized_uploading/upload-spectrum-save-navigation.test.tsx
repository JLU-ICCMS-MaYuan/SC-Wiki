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

it.each([false, true])('新标签页查看谱不会触发保存，已有改动=%s', async changed => {
  vi.mocked(api.put).mockRejectedValue(new Error('保存接口失败不应影响查看'))
  mountEditor()
  if (changed) fireEvent.change(await screen.findByLabelText('标题'), { target: { value: '保留当前输入' } })
  const link = await screen.findByRole('link', { name:'核对归属' })
  expect(link).toHaveAttribute('target', '_blank')
  expect(link.getAttribute('href')).toContain('/spectra/spectrum')
  expect(api.put).not.toHaveBeenCalled()
  expect(screen.getByLabelText('标题')).toHaveValue(changed ? '保留当前输入' : '原始标题')
})
