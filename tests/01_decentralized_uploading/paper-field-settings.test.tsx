import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import ReviewFieldSettings from '../../frontend/src/components/ReviewFieldSettings'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn() } }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 7, role: 'admin', is_admin: true } }) }))
const paper = { id: 148, title: '原始标题', abstract: '原始摘要', summary: '原始总结', key_finding: '原始发现',
  research_motivation: '原始动机', keywords_tags: ['hydride', 'high pressure'], methodology: ['DFT', 'SSCHA'],
  authors: [], material_families: [], review_status: 'pending', paper_type: 'theoretical', superconductor_kind: 'conventional' }
const records = Object.keys(paper).filter(key => ['title', 'abstract', 'summary', 'key_finding', 'research_motivation', 'keywords_tags', 'methodology'].includes(key))
  .map(key => ({ key, item_key: key, field: `paper.${key}`, label: key, current_value: paper[key as keyof typeof paper], status: 'supported', reason: '原文支持当前内容', evidences: [] }))
const draft = { paper, material_states: [], structure_candidates: [] }
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async path => {
    if (path === '/api/admin/papers/148') return { ...paper, material_states: [] } as never
    if (path.includes('/draft-state')) return { staged: false, version: 'v1', draft } as never
    if (path.includes('/field-detail')) return { record: {}, source_state: 'empty', review_token: 'token', can_approve: true, history: [] } as never
    if (path.includes('/classification-catalogs')) return { material_families: [], structure_families: [], material_dimensionalities: [] } as never
    if (path.includes('/draft')) return { ok: true, data: draft } as never
    return { data: {}, space_groups: [], modules: [] } as never
  })
  vi.mocked(api.post).mockImplementation(async (path, body) => {
    if (path.endsWith('/summary')) return { version: 'v1', records, needs_check: false } as never
    if (path.endsWith('/identify-field')) {
      const record = records.find(item => item.field === (body as { field: string }).field)
      if (!record) throw new Error('测试请求了未定义的字段记录')
      return { record } as never
    }
    return { ok: true, data: draft, revision_id: 'revision-148', draft_version: 1 } as never
  })
  vi.mocked(api.patch).mockResolvedValue({ changed: true, version: 'v2' })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
function host(kind: 'upload' | 'revision' | 'admin', readOnly = false) {
  return render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/148/edit']}>
    {kind === 'admin' ? <Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage />} /></Routes>
      : <UploadTaskEditor taskId="settings-148" {...(kind === 'revision' ? { revisionPaperId: 148 } : { draftOverride: draft })} readOnly={readOnly} onSubmitted={() => {}} />}
  </MemoryRouter></LanguageProvider>)
}
async function open(field = 'methodology') {
  const label = await waitFor(() => {
    const node = document.querySelector(`[data-issue-field="paper.${field}"] label`)
    expect(node).toHaveAttribute('role', 'button'); return node!
  })
  fireEvent.click(label)
  fireEvent.click(await screen.findByRole('tab', { name: '字段设置' }))
  const dialog = screen.getByRole('dialog')
  await within(dialog).findByLabelText('字段名称（key）')
  return dialog
}
it('返修汇总尚未返回时，先定位字段再打开设置仍保留当前值', async () => {
  const post = vi.mocked(api.post).getMockImplementation()!
  let finishSummary!: () => void
  const summary = new Promise(resolve => { finishSummary = () => resolve({ version: 'v1', records, needs_check: false }) })
  vi.mocked(api.post).mockImplementation((path, body) => path.endsWith('/summary') ? summary as never : post(path, body))
  host('revision')
  try {
    const dialog = await open()
    expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA')
    expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/\/identify-field$/), expect.objectContaining({ field: 'paper.methodology' }))
  } finally { finishSummary() }
})
it.each(['upload', 'revision', 'admin'] as const)('%s 的真实宿主显示研究方法并仅保存该列表，无额外模型调用', async kind => {
  host(kind)
  let dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA')
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: 'DFT\nSSCHA revised' } })
  fireEvent.click(within(dialog).getByRole('tab', { name: '来源核对' }))
  expect(within(dialog).queryByText('返回编辑当前值')).not.toBeInTheDocument()
  expect(within(dialog).queryByText('返回修改记录')).not.toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('tab', { name: '历史记录' }))
  fireEvent.click(within(dialog).getByRole('tab', { name: '字段设置' }))
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA revised')
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: kind === 'admin' ? '保存修改' : '立即保存', exact: true }))
  await waitFor(() => expect(api.patch).toHaveBeenCalled())
  expect(vi.mocked(api.patch).mock.calls.at(-1)?.[1]).toMatchObject({ changes: [
    { path: ['paper', 'methodology'], value: ['DFT', 'SSCHA revised'] },
  ] })
  expect((vi.mocked(api.patch).mock.calls.at(-1)?.[1] as any).changes).toHaveLength(1)
  expect(vi.mocked(api.post).mock.calls.some(([url]) => /jobs|submit-check|preflight/.test(url))).toBe(false)
  dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA revised')
})
it('管理员设置读取主表单尚未保存的逐行文本，包括空行和逗号', async () => {
  host('admin')
  const input = await waitFor(() => {
    const node = document.querySelector<HTMLTextAreaElement>('[data-issue-field="paper.methodology"] textarea:not([aria-hidden])')
    expect(node).toBeInTheDocument(); return node!
  })
  fireEvent.change(input, { target: { value: 'DFT, with EPC\n\nSSCHA\n' } })
  const dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT, with EPC\n\nSSCHA\n')
  fireEvent.click(within(dialog).getByRole('button', { name: '取消', exact: true }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: '保存修改', exact: true }))
  await waitFor(() => expect(api.patch).toHaveBeenCalled())
  expect(vi.mocked(api.patch).mock.calls.at(-1)?.[1]).toMatchObject({ changes: [
    { path: ['paper', 'methodology'], value: ['DFT, with EPC', 'SSCHA'] },
  ] })
})
it.each(['upload', 'admin'] as const)('%s 的七类论文设置均显示真实当前值，名称固定，无改应用被禁用', async kind => {
  host(kind)
  for (const field of ['title', 'abstract', 'summary', 'key_finding', 'research_motivation', 'keywords_tags', 'methodology'] as const) {
    const dialog = await open(field)
    const value = paper[field]
    expect(within(dialog).getByLabelText('当前值')).toHaveValue(Array.isArray(value) ? value.join('\n') : value)
    expect(within(dialog).getByLabelText('字段名称（key）')).toHaveAttribute('readonly')
    expect(within(dialog).getByRole('button', { name: '应用修改' })).toBeDisabled()
    fireEvent.click(within(dialog).getByRole('button', { name: '取消', exact: true }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  }
  expect(api.patch).not.toHaveBeenCalled()
})
it('未应用修改关闭时可继续编辑或放弃，取消不改变主表单', async () => {
  host('upload')
  const dialog = await open()
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: '未应用的修改' } })
  fireEvent.click(within(dialog).getByLabelText('关闭来源详情'))
  fireEvent.click(await screen.findByRole('button', { name: '继续编辑' }))
  await waitFor(() => expect(screen.getAllByRole('dialog')).toHaveLength(1))
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('未应用的修改')
  fireEvent.click(within(dialog).getByLabelText('关闭来源详情'))
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改并关闭' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  const reopened = await open()
  expect(within(reopened).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA')
  expect(api.patch).not.toHaveBeenCalled()
})
it('同字段外部修改拒绝覆盖并保留侧栏输入，无关字段修改不阻止应用', async () => {
  host('upload')
  let dialog = await open()
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: '我的新内容' } })
  fireEvent.change(document.querySelector('[data-issue-field="paper.methodology"] textarea:not([aria-hidden])')!, { target: { value: '其他操作的新内容' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  expect(await within(dialog).findByText(/字段已发生变化/)).toBeVisible()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('我的新内容')
  fireEvent.click(within(dialog).getByRole('button', { name: '取消', exact: true }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('其他操作的新内容')
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: '允许的修改' } })
  fireEvent.change(document.querySelector('[data-issue-field="paper.title"] input')!, { target: { value: '仅修改无关标题' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(document.querySelector('[data-issue-field="paper.methodology"] textarea:not([aria-hidden])')).toHaveValue('允许的修改')
})
it('只读宿主可查看名称和值，不能应用或发出保存请求', async () => {
  host('upload', true)
  const dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toBeDisabled()
  expect(within(dialog).queryByRole('button', { name: '应用修改' })).not.toBeInTheDocument()
  expect(api.patch).not.toHaveBeenCalled()
})
it('长文本保留换行，可选空字段应用后保持空白；恢复原值不产生保存差异', async () => {
  host('upload')
  let dialog = await open('abstract')
  const text = 'Long description\n'.repeat(150)
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: text } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  dialog = await open('abstract')
  expect(within(dialog).getByLabelText('当前值')).toHaveValue(text)
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: '' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  dialog = await open('abstract')
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('')
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: paper.abstract } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: '立即保存', exact: true }))
  expect(api.patch).not.toHaveBeenCalled()
})
it('专用工作区未接入通用编辑时仍显示可读名称和值，不出现重复返回按钮', () => {
  render(<ReviewFieldSettings identity="structure" field="structure.geometry" enabled label="晶格几何" value={{a: 3.2}} onDone={() => {}} />)
  expect(screen.getByText('晶格几何')).toBeVisible()
  expect(screen.getByText('3.2')).toBeVisible()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
it('没有核对摘要的字段也能打开设置，不顺带保存主表单其他未保存修改', async () => {
  const originalPost = vi.mocked(api.post).getMockImplementation()!
  vi.mocked(api.post).mockImplementation(async (path, body) => {
    if (path.endsWith('/summary')) return { version: 'v1', records: [], needs_check: false } as never
    if (path.endsWith('/identify-field')) return { record: { ...records.find(r => r.key === 'methodology')!, status: 'unchecked', pending_review: true } } as never
    return originalPost(path, body)
  })
  host('upload')
  const input = await screen.findByDisplayValue(paper.title)
  fireEvent.change(input, { target: { value: '尚未保存的标题' } })
  const dialog = await open()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue('DFT\nSSCHA')
  expect(api.patch).not.toHaveBeenCalled()
  expect(vi.mocked(api.post).mock.calls.some(([url]) => /jobs|submit-check|preflight/.test(url))).toBe(false)
})
it('管理员 Go 详情的 JSON 列表以草稿数组作为保存前值，避免误报并发冲突', async () => {
  const originalGet = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, ...args) => path === '/api/admin/papers/148'
    ? { ...paper, methodology: JSON.stringify(paper.methodology), keywords_tags: JSON.stringify(paper.keywords_tags), material_states: [] } as never
    : originalGet(path, ...args))
  host('admin')
  const dialog = await open()
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: 'DFT\nSSCHA revised' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: '保存修改', exact: true }))
  await waitFor(() => expect(api.patch).toHaveBeenCalled())
  expect(vi.mocked(api.patch).mock.calls.at(-1)?.[1]).toMatchObject({ changes: [
    { path: ['paper', 'methodology'], before: ['DFT', 'SSCHA'], value: ['DFT', 'SSCHA revised'] },
  ] })
})
