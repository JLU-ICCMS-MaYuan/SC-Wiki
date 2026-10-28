import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
const original = 'Superconductivity in compressed hydrides'
const updated = 'Electron phonon coupling in compressed hydrides'
let draft: any, record: any, conflict: boolean
beforeEach(() => {
  conflict = false
  draft = { paper: { title: 'Original paper title', knowledge_graph_title: original,
    paper_type: 'review', year: 2026, authors: [], material_families: [{ id: 1, name: 'Hydrides' }] },
    material_states: [], structure_candidates: [] }
  record = { key: 'graph-title', item_key: 'graph-title', field: 'paper.knowledge_graph_title',
    label: '图谱科学标题', current_value: original, status: 'supported', reason: '来源支持', evidences: [], required: true }
  vi.mocked(api.get).mockImplementation(async path => {
    if (path.includes('/draft-state')) return { version: 'v1', draft: structuredClone(draft) } as never
    if (path.includes('/field-detail')) return { record: structuredClone(record), source_state: 'empty', review_token: 'fixture-token', history: [] } as never
    if (path.includes('/classification-catalogs')) return { material_families: [], structure_families: [], material_dimensionalities: [] } as never
    if (path.endsWith('/draft')) return { data: structuredClone(draft) } as never
    return { space_groups: [], modules: [] } as never
  })
  vi.mocked(api.post).mockImplementation(async path => {
    if (path.endsWith('/summary')) return { version: 'v1', records: record ? [structuredClone(record)] : [], needs_check: false } as never
    if (path.endsWith('/revision-draft')) return { data: structuredClone(draft), revision_id: 'revision-173', draft_version: 1, conflict } as never
    throw new Error(`Unexpected request: ${path}`)
  })
  vi.mocked(api.patch).mockImplementation(async (_path, body: any) => {
    for (const change of body.changes) {
      expect(change.path).toEqual(['paper', 'knowledge_graph_title'])
      draft.paper.knowledge_graph_title = change.value
    }
    return { changed: true, version: 'v2' } as never
  })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
function show(props: { readOnly?: boolean; revisionPaperId?: number } = {}) {
  return render(<LanguageProvider><UploadTaskEditor taskId="title-173" onSubmitted={() => {}} {...props} /></LanguageProvider>)
}
async function input() { return screen.findByRole('textbox', { name: '图谱科学标题', exact: true }) }
async function openSettings() {
  const label = await waitFor(() => {
    const node = document.querySelector('[data-issue-field="paper.knowledge_graph_title"] label')
    expect(node).toHaveAttribute('role', 'button'); return node!
  })
  fireEvent.click(label)
  fireEvent.click(await screen.findByRole('tab', { name: '字段设置' }))
  const dialog = screen.getByRole('dialog')
  await within(dialog).findByLabelText('当前值')
  return dialog
}
it.each([original, '', null, undefined])('显示草稿原值 %s，空值与缺失仍有输入框', async value => {
  if (value === undefined) delete draft.paper.knowledge_graph_title
  else draft.paper.knowledge_graph_title = value
  record = null
  show()
  expect(await input()).toHaveValue(value ?? '')
  expect(screen.getByText(/paper\.knowledge_graph_title/)).toBeVisible()
  expect(api.patch).not.toHaveBeenCalled()
})
it('只保存图谱标题，重载后保留新值且不覆盖原标题', async () => {
  const view = show()
  fireEvent.change(await input(), { target: { value: updated } })
  fireEvent.click(screen.getByRole('button', { name: '立即保存', exact: true }))
  await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1))
  expect(vi.mocked(api.patch).mock.calls[0]).toEqual(['/api/rag/evidence/draft', {
    target: 'upload', target_id: 'title-173', expected_version: 'v1',
    changes: [{ path: ['paper', 'knowledge_graph_title'], before: original, value: updated }],
  }])
  view.unmount(); show()
  expect(await input()).toHaveValue(updated)
  expect(screen.getByRole('textbox', { name: '标题', exact: true })).toHaveValue('Original paper title')
})
it('问题记录定位到字段，设置侧栏编辑后旧通过结论变为待核对', async () => {
  show()
  expect(await input()).toHaveValue(original)
  const dialog = await openSettings()
  expect(document.querySelector('[data-evidence-fallback]')).toBeNull()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue(original)
  fireEvent.change(within(dialog).getByLabelText('当前值'), { target: { value: updated } })
  fireEvent.click(within(dialog).getByRole('button', { name: '应用修改' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(await input()).toHaveValue(updated)
  const reopened = await openSettings()
  fireEvent.click(within(reopened).getByRole('tab', { name: '来源核对' }))
  expect(await within(reopened).findByText('当前内容待提交核对；下方仅显示已有核对结论。')).toBeVisible()
  expect(document.querySelector('[data-evidence-fallback]')).toBeNull()
  expect(api.patch).not.toHaveBeenCalled()
})
it('待处理核对直接绑定输入框，不落入待定位列表', async () => {
  record.status = 'uncertain'
  show()
  await input()
  const dialog = await openSettings()
  expect(within(dialog).getByLabelText('当前值')).toHaveValue(original)
  expect(document.querySelector('[data-evidence-fallback]')).toBeNull()
  expect(document.querySelector('[data-issue-field="paper.knowledge_graph_title"] [data-evidence-problem="true"]')).not.toBeNull()
})
it('保存失败保留编辑并显示错误，不报告成功', async () => {
  vi.mocked(api.patch).mockRejectedValue(new Error('保存失败测试'))
  show()
  fireEvent.change(await input(), { target: { value: updated } })
  fireEvent.click(screen.getByRole('button', { name: '立即保存', exact: true }))
  expect(await screen.findByText(/保存失败/)).toBeVisible()
  expect(await input()).toHaveValue(updated)
  expect(draft.paper.knowledge_graph_title).toBe(original)
})
it('只读显示真实值，侧栏禁止应用且不写入', async () => {
  show({ readOnly: true })
  expect(await input()).toHaveAttribute('readonly')
  const dialog = await openSettings()
  expect(within(dialog).getByLabelText('当前值')).toBeDisabled()
  expect(within(dialog).queryByRole('button', { name: '应用修改' })).not.toBeInTheDocument()
  expect(api.patch).not.toHaveBeenCalled()
})
it('返修草稿版本冲突时禁用图谱标题输入', async () => {
  conflict = true
  show({ revisionPaperId: 173 })
  expect(await input()).toBeDisabled()
  expect(api.patch).not.toHaveBeenCalled()
})
