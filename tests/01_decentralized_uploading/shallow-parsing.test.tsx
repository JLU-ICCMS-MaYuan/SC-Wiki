import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import UploadParsingModeChoice from '../../frontend/src/components/UploadParsingModeChoice'
import SearchPage from '../../frontend/src/pages/SearchPage'
import UploadPage from '../../frontend/src/pages/UploadPage'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() } }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 7, role: 'user' } }) }))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks() })
const draft = {
  paper: { title: 'Paper only', year: 2026, paper_type: 'experimental', authors: [],
    research_materials: ['CaH6'], material_families: [], summary: 'Summary' },
  material_states: [], _parsing_workflow: {
    workflow_key: 'paper-only', workflow_version: 1, form_key: 'paper-level-info',
    form_version: 1, form_sha256: 'a'.repeat(64),
  },
}

it('上传后选择浅度才启动，回调保留服务器模式', async () => {
  const started = vi.fn()
  vi.mocked(api.post).mockResolvedValue({ data: { task_id: 'choice', parsing_mode: 'shallow', status: 'queued' } })
  render(<LanguageProvider><UploadParsingModeChoice task={{ task_id: 'choice', status: 'uploading',
    defer_parsing: true, files: [{ upload_status: 'completed' }] } as any} onStarted={started} /></LanguageProvider>)
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '浅度解析' }))
  await waitFor(() => expect(started).toHaveBeenCalledWith(expect.objectContaining({ parsing_mode: 'shallow' })))
  expect(api.post).toHaveBeenCalledWith('/api/upload-tasks/choice/finalize', { parsing_mode: 'shallow' })
})

it('完整上传页恢复已上传任务后选择浅度，只启动一次且不显示科学核对进度', async () => {
  const consoleError = vi.spyOn(console, 'error')
  let task: any = { task_id: 'mode-host', filename: 'paper.pdf', status: 'uploading',
    stage: 'saving_file', stage_index: 1, stage_total: 5, processing_status: 'processing',
    defer_parsing: true, files: [{ file_id: 'main', role: 'main', upload_status: 'completed' }] }
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === '/api/upload-tasks/mode-host') return { data: task } as never
    if (path === '/api/upload-tasks') return { data: [task] } as never
    return { data: { chunks: [], files: [], summary: { total: 0, completed: 0 } } } as never
  })
  vi.mocked(api.post).mockImplementation(async (path: string) => {
    if (path.endsWith('/finalize')) task = { ...task, parsing_mode: 'shallow', defer_parsing: false,
      status: 'queued', stage: 'queued' }
    return { data: task } as never
  })
  render(<MemoryRouter><LanguageProvider><UploadPage taskId="mode-host" /></LanguageProvider></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '浅度解析' }))
  await screen.findByText('正在提取论文信息')
  expect(vi.mocked(api.post).mock.calls.filter(call => call[0].endsWith('/finalize'))).toHaveLength(1)
  expect(screen.queryByText('填写表单与自动核对')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '深度解析' })).not.toBeInTheDocument()
  expect(consoleError.mock.calls.flat().join(' ')).not.toMatch(/same key/)
})

it('完整浅度编辑器不请求核对，修改保存后直接提交', async () => {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.includes('/draft-state')) return { version: 'v1' } as never
    if (path.endsWith('/draft')) return { data: structuredClone(draft) } as never
    if (path.includes('classification-catalogs')) return { material_families: [], structure_families: [] } as never
    return { data: {}, space_groups: [], modules: [] } as never
  })
  vi.mocked(api.patch).mockResolvedValue({ version: 'v2', changed: true })
  vi.mocked(api.post).mockResolvedValue({ paper_id: 241, review_status: 'published' })
  const submitted = vi.fn()
  render(<MemoryRouter><LanguageProvider><UploadTaskEditor taskId="shallow" onSubmitted={submitted} /></LanguageProvider></MemoryRouter>)
  const submit = await screen.findByRole('button', { name: '提交入库' })
  expect(screen.queryByText('研究材料大纲')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /添加材料状态|来源核对/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '立即保存' }))
  expect(api.patch).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('标题'), { target: { value: 'Edited paper' } })
  fireEvent.click(submit)
  await waitFor(() => expect(submitted).toHaveBeenCalledWith(241))
  expect(api.patch).toHaveBeenCalledWith('/api/rag/evidence/draft',
    expect.objectContaining({ target: 'upload', target_id: 'shallow',
      changes: [{ path: ['paper', 'title'], before: 'Paper only', value: 'Edited paper' }] }))
  expect(api.post).toHaveBeenCalledWith('/api/rag/upload-tasks/shallow/submit', {})
  const requests = [...vi.mocked(api.get).mock.calls, ...vi.mocked(api.post).mock.calls,
    ...vi.mocked(api.patch).mock.calls].map(call => call[0])
  expect(requests.some(path => path.includes('/evidence')
    && !path.includes('/draft-state') && !path.endsWith('/draft'))).toBe(false)
})

it('搜索页可直接按论文信息查询，无需虚构元素条件', async () => {
  vi.mocked(api.post).mockResolvedValue({ items: [], total: 0, papers_total: 0, states_total: 0 })
  render(<MemoryRouter initialEntries={['/search']}><LanguageProvider><SearchPage /></LanguageProvider></MemoryRouter>)
  const input = screen.getByRole('textbox', { name: '标题、DOI 或期刊' })
  fireEvent.change(input, { target: { value: '10.1073/pnas.1118168109' } })
  fireEvent.submit(input.closest('form')!)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/papers/search/results',
    expect.objectContaining({ keyword: '10.1073/pnas.1118168109', elements: [], view: 'papers' })))
})

it('从深度任务切换到浅度任务时不使用旧草稿请求新任务核对', async () => {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith('/draft')) return { data: path.includes('/deep/')
      ? { ...draft, _parsing_workflow: { ...draft._parsing_workflow, workflow_key: 'conventional-theory-calculation' } }
      : structuredClone(draft) } as never
    return { space_groups: [], material_families: [], structure_families: [] } as never
  })
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', records: [], needs_check: false })
  const view = (taskId: string) => <MemoryRouter><LanguageProvider>
    <UploadTaskEditor taskId={taskId} onSubmitted={vi.fn()} />
  </LanguageProvider></MemoryRouter>
  const { rerender } = render(view('deep'))
  await screen.findByRole('button', { name: '提交审核' })
  rerender(view('next-shallow'))
  await screen.findByRole('button', { name: '提交入库' })
  expect(vi.mocked(api.post).mock.calls.some(call => call[0].endsWith('/summary')
    && (call[1] as any)?.target_id === 'next-shallow')).toBe(false)
})
