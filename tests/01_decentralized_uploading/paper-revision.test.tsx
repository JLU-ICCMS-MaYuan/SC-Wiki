import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import PaperEditView from '../../frontend/src/components/PaperEditView'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
vi.mock('../../frontend/src/lib/classifications', async importOriginal => ({
  ...await importOriginal<typeof import('../../frontend/src/lib/classifications')>(),
  loadClassificationCatalogs: vi.fn(async () => ({ material_families: [], structure_families: [], material_dimensionalities: [] })),
}))
vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({ default: () => null }))

const base = '/api/rag/papers/7/revision-draft'
const initial = {
  ok: true, revision_id: 'a'.repeat(32), draft_version: 1, review_comment: '请核对压强',
  data: { paper: { title: '待返修论文', paper_type: 'review', authors: ['作者'],
    material_families: [{ name: '待确认家族', status: 'pending' }], superconductor_kind: 'unknown' },
    material_states: [], structure_candidates: [] },
}
const mockedApi = vi.mocked(api)
beforeEach(() => {
  mockedApi.get.mockResolvedValue([])
  mockedApi.post.mockImplementation(async url => {
    if (url === base) return structuredClone(initial)
    if (url.endsWith('/submit')) return { ok: true, paper_id: 7, content_revision: 2, review_status: 'pending' }
    if (url.endsWith('/proposals/prepare')) return { patches: [] }
    return { version: 'checked', records: [], needs_check: false, sources: [] }
  })
  mockedApi.put.mockImplementation(async (_url, body: any) => ({ ...structuredClone(initial), data: body.draft, draft_version: body.draft_version + 1 }))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('已拒绝论文的返修入口', () => {
  it('只根据服务端返修能力显示入口，并展示拒绝意见', () => {
    const { rerender } = render(<MemoryRouter><LanguageProvider><PaperEditView
      paper={{ id: 7, title: '返修论文', review_status: 'rejected', can_revise: true, review_comment: '请核对压强' }}
      onBack={() => undefined} /></LanguageProvider></MemoryRouter>)
    expect(screen.getByRole('link', { name: '修改并重新提交' })).toHaveAttribute('href', '/papers/7/revise')
    expect(screen.getByText('请核对压强')).toBeInTheDocument()
    rerender(<MemoryRouter><LanguageProvider><PaperEditView
      paper={{ id: 7, review_status: 'rejected', can_revise: false }}
      onBack={() => undefined} /></LanguageProvider></MemoryRouter>)
    expect(screen.queryByRole('link', { name: '修改并重新提交' })).not.toBeInTheDocument()
  })
})

describe('返修共享表单', () => {
  it('暂存只保存草稿；重新提交使用最新草稿版本并回到同一篇论文', async () => {
    const submitted = vi.fn()
    render(<LanguageProvider><UploadTaskEditor taskId="7" revisionPaperId={7} onSubmitted={submitted} /></LanguageProvider>)
    const title = await screen.findByDisplayValue('待返修论文')
    expect(screen.getByText('请核对压强')).toBeInTheDocument()
    fireEvent.change(title, { target: { value: '修订标题' } })
    fireEvent.click(screen.getByRole('button', { name: '立即保存' }))
    await waitFor(() => expect(mockedApi.put).toHaveBeenCalledWith(base, expect.objectContaining({
      revision_id: initial.revision_id, draft_version: 1, draft: expect.objectContaining({ paper: expect.objectContaining({ title: '修订标题' }) }),
    })))
    expect(mockedApi.post.mock.calls.some(([url]) => url.endsWith('/submit'))).toBe(false)
    await waitFor(() => expect(screen.getByRole('button', { name: '重新提交审核' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '重新提交审核' }))
    await waitFor(() => expect(submitted).toHaveBeenCalledWith(7))
    expect(mockedApi.post).toHaveBeenCalledWith(base+'/submit', expect.objectContaining({ revision_id: initial.revision_id, draft_version: 3 }))
    expect(mockedApi.post).toHaveBeenCalledWith('/api/rag/evidence/preflight', { target: 'revision', target_id: initial.revision_id })
  })

  it('保存冲突保留用户输入，不继续送审', async () => {
    mockedApi.put.mockRejectedValue(Object.assign(new Error('草稿已在其他窗口保存'), { status: 409, code: 'revision_draft_conflict',
      detail: { detail: { code: 'revision_draft_conflict', message: '草稿已在其他窗口保存' } } }))
    render(<LanguageProvider><UploadTaskEditor taskId="7" revisionPaperId={7} onSubmitted={vi.fn()} /></LanguageProvider>)
    const title = await screen.findByDisplayValue('待返修论文')
    fireEvent.change(title, { target: { value: '不能丢失的输入' } })
    fireEvent.click(screen.getByRole('button', { name: '重新提交审核' }))
    expect(await screen.findByText(/草稿已在其他窗口保存/)).toBeInTheDocument()
    expect(title).toHaveValue('不能丢失的输入')
    expect(mockedApi.post.mock.calls.some(([url]) => url.endsWith('/submit'))).toBe(false)
  })

  it('恢复基线已过期的草稿时保留展示并禁止保存和送审', async () => {
    mockedApi.post.mockImplementation(async url => url === base ? { ...structuredClone(initial), conflict: true }
      : { version: 'checked', records: [], needs_check: false, sources: [] })
    render(<LanguageProvider><UploadTaskEditor taskId="7" revisionPaperId={7} onSubmitted={vi.fn()} /></LanguageProvider>)
    await screen.findByDisplayValue('待返修论文')
    expect(screen.getByRole('button', { name: '立即保存' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '重新提交审核' })).toBeDisabled()
  })
})
