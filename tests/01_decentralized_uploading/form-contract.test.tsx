import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { TextField } from '@mui/material'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import AdminPaperEditPage from '../../frontend/src/pages/AdminPaperEditPage'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { within } from '@testing-library/react'
import { api } from '../../frontend/src/lib/api'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'

const counters = vi.hoisted(() => ({ cards: [] as number[], role: 'admin' }))
// 只计数，不替换真实字段逻辑；生产宿主、卡片缓存、核对 Hook 仍实际运行。
vi.mock('../../frontend/src/components/PressureEditor', async original => {
  const actual = await original<any>()
  return { ...actual, default: (props: any) => { counters.cards.push(props.index); return React.createElement(actual.default, props) } }
})
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 7, role: counters.role, is_admin: true, is_approved: true } }) }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn() } }))
const states = Array.from({ length: 5 }, (_, i) => ({ id: i + 1, state_key: `s${i}`, material: 'Sn', material_name: `State ${i}`,
  state_kind: 'experimental', material_dimensionality: 'unknown', crystal_system: 'unknown', element_count: 1,
  superconductor: { chemical_formula: 'Sn', material_name: `State ${i}` }, structure_families: [], property_modules: [] }))
const paper = { id: 174, title: 'Original title', knowledge_graph_title: 'Graph title', authors: [], year: 2026,
  paper_type: 'review', material_families: [], review_status: 'pending', uploaded_by_user_id: 8 }
const draft = { paper, material_states: states, structure_candidates: [] }
beforeEach(() => {
  counters.cards = []; counters.role = 'admin'
  vi.mocked(api.get).mockImplementation(async path => {
    if (path === '/api/admin/papers/174') return { ...paper, material_states: structuredClone(states) } as never
    if (path.includes('/draft-state')) return { staged: false, version: 'v1', draft: structuredClone(draft) } as never
    if (path.includes('/classification-catalogs')) return { material_families: [], structure_families: [], material_dimensionalities: [] } as never
    if (path.endsWith('/draft')) return { data: structuredClone(draft) } as never
    return { data: {}, space_groups: [], modules: [], items: [], jobs: [] } as never
  })
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('/summary')
    ? { version: 'v1', records: [], needs_check: false } as never
    : { data: structuredClone(draft), revision_id: 'revision-174', draft_version: 1 } as never)
  vi.mocked(api.patch).mockResolvedValue({ changed: true, version: 'v2' })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks() })
async function host(kind: string) {
  counters.role = kind === 'superadmin' ? 'superadmin' : 'admin'
  render(<LanguageProvider><MemoryRouter initialEntries={['/admin/papers/174/edit']}>
    {['admin', 'superadmin'].includes(kind)
      ? <Routes><Route path="/admin/papers/:id/edit" element={<AdminPaperEditPage />} /></Routes>
      : <UploadTaskEditor taskId="contract-174" revisionPaperId={kind === 'revision' ? 174 : undefined} onSubmitted={() => {}} />}
  </MemoryRouter></LanguageProvider>)
  await screen.findByDisplayValue('Original title')
  await waitFor(() => expect(screen.getAllByRole('combobox', { name: '晶系' })).toHaveLength(5))
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 30)) })
  counters.cards = []
}
it.each(['upload', 'revision', 'admin', 'superadmin'])('%s 完整宿主：论文标题编辑不重绘无关材料卡片', async kind => {
  await host(kind)
  fireEvent.change(screen.getByDisplayValue('Original title'), { target: { value: 'Changed title' } })
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(counters.cards).toEqual([])
  expect(api.patch).not.toHaveBeenCalled()
  expect(vi.mocked(api.post).mock.calls.some(([path]) => /jobs|preflight|submit-check/.test(path))).toBe(false)
})
it.each(['upload', 'revision', 'admin', 'superadmin'])('%s 完整宿主：首卡晶系编辑不重绘其他四卡', async kind => {
  await host(kind)
  fireEvent.mouseDown(screen.getAllByRole('combobox', { name: '晶系' })[0])
  fireEvent.click(screen.getByRole('option', { name: '立方' }))
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(counters.cards.length).toBeGreaterThan(0)
  expect(new Set(counters.cards)).toEqual(new Set([0]))
})
it('相同路径的新数组不清空缓存，实际问题计数只更新相关卡片', async () => {
  const form = (reviewFields: string[]) => <MaterialStatesEditor states={states as any} onChange={() => {}} catalogs={null} reviewFields={reviewFields} />
  const view = render(form([]))
  counters.cards = []
  view.rerender(form([]))
  expect(counters.cards).toEqual([])
  view.rerender(form(['material_states[1].material']))
  expect(new Set(counters.cards)).toEqual(new Set([1]))
  expect(document.querySelector('[data-state-key="s1"] .MuiChip-label')).toHaveTextContent('1')
})
it('核对状态变化复用定位节点，不重新扫描整表且仍更新颜色', async () => {
  const record = { key: 'title', field: 'paper.title', label: '标题', current_value: 'old', status: 'supported' as const, reason: '', evidences: [] }
  const form = (r: any) => <div data-evidence-scope="contract"><TextField label="标题" data-issue-field="paper.title" defaultValue="old" />
    <EvidenceFieldMarkers records={[r]} scope="contract" onOpen={() => {}} onChange={() => {}} /></div>
  const view = render(form(record))
  await screen.findByRole('button', { name: '标题' })
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  const root = view.container.querySelector('[data-evidence-scope]')!
  const scan = vi.spyOn(root, 'querySelectorAll')
  view.rerender(form({ ...record, status: 'uncertain' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '标题' })).toHaveAttribute('data-evidence-caption-problem', 'true'))
  expect(scan.mock.calls.filter(([selector]) => selector === '[data-issue-field]')).toHaveLength(0)
})
it('没有摘要的占位入口读取最新输入，不因缓存显示旧值', async () => {
  const onOpen = vi.fn()
  render(<div data-evidence-scope="placeholder"><TextField label="标题" data-issue-field="paper.title" defaultValue="old" />
    <EvidenceFieldMarkers records={[]} scope="placeholder" onOpen={onOpen} onChange={() => {}} /></div>)
  const label = await screen.findByRole('button', { name: '标题' })
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '最新值' } })
  fireEvent.click(label)
  expect(onOpen.mock.calls.at(-1)?.[2]).toMatchObject({ current_value: '最新值' })
})
it('单字段输入不读取并比较其他字段的值', async () => {
  const records = ['title', ...Array.from({ length: 50 }, (_, i) => `other${i}`)].map(name => ({
    key: name, item_key: name, field: `paper.${name}`, label: name, current_value: 'old', status: 'supported', reason: '', evidences: [],
  }))
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', records, needs_check: false })
  let value = 'old', flow: ReturnType<typeof useEvidenceWorkflow>
  const read = vi.fn((record: EvidenceRecord) => ({ field: record.field, value: record.key === 'title' ? value : 'old' }))
  function Harness() { flow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'read-count' }, getCurrentValue: read }); return null }
  render(<Harness />)
  await waitFor(() => expect(flow.records).toHaveLength(51))
  read.mockClear(); value = 'new'
  await act(async () => { flow.invalidate('paper.title'); await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(new Set(read.mock.calls.map(([record]) => record.key))).toEqual(new Set(['title']))
})
it('临时错误只更新当前卡片，删除前卡后错误与输入仍属于原状态', async () => {
  await host('upload')
  const inputs = screen.getAllByLabelText('不同元素种类数')
  fireEvent.change(inputs[1], { target: { value: '0' } })
  expect(screen.getByText('请输入 1–118 的整数')).toBeVisible()
  expect(new Set(counters.cards)).toEqual(new Set([1]))
  const first = document.querySelector('[data-state-key="s0"]') as HTMLElement
  fireEvent.click(within(first).getByRole('button', { name: '删除', exact: true }))
  const remaining = document.querySelector('[data-state-key="s1"]') as HTMLElement
  expect(within(remaining).getByLabelText('不同元素种类数')).toHaveValue('0')
  expect(within(remaining).getByText('请输入 1–118 的整数')).toBeVisible()
  expect(document.querySelector('[data-state-key="s2"]')).not.toHaveTextContent('请输入 1–118 的整数')
})
it.each(['upload', 'revision', 'admin', 'superadmin'])('%s 缓存事件使用最新宿主，先改标题再改材料不恢复旧标题', async kind => {
  await host(kind)
  fireEvent.change(screen.getByDisplayValue('Original title'), { target: { value: '最新标题' } })
  fireEvent.change(screen.getAllByLabelText('材料名')[0], { target: { value: '新的材料名' } })
  expect(screen.getByDisplayValue('最新标题')).toBeVisible()
  expect(screen.getByDisplayValue('新的材料名')).toBeVisible()
})
it('中文组合输入保留当前文本，未变化的数据保存不写请求', async () => {
  await host('upload')
  const input = screen.getByDisplayValue('Original title')
  fireEvent.compositionStart(input)
  fireEvent.change(input, { target: { value: '超导标题' } })
  fireEvent.compositionEnd(input, { data: '超导标题' })
  expect(input).toHaveValue('超导标题')
  fireEvent.change(input, { target: { value: 'Original title' } })
  fireEvent.click(screen.getByRole('button', { name: '立即保存', exact: true }))
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(api.patch).not.toHaveBeenCalled()
})
it('中间指数和零值持续输入保留，清空不改其他卡片', async () => {
  await host('upload')
  const input = screen.getAllByLabelText('压强 (GPa)')[0]
  for (const value of ['1', '1e', '1e-', '1e-2', '0', '']) {
    fireEvent.change(input, { target: { value } })
    expect(input).toHaveValue(value)
  }
  expect(new Set(counters.cards)).toEqual(new Set([0]))
  expect(screen.getAllByLabelText('压强 (GPa)')[1]).toHaveValue('')
  expect(api.patch).not.toHaveBeenCalled()
})
it('动态删除首卡后核对标记跟随稳定身份，新位置输入仍通知原字段', async () => {
  const change = vi.fn(), open = vi.fn()
  const record = { key: 'tin', state_key: 'Sn', field: 'material_states[1].material', label: '锡', status: 'uncertain' as const, reason: '', evidences: [] }
  const form = (removed: boolean) => <div data-evidence-scope="delete">
    {(removed ? ['Sn'] : ['Pb', 'Sn']).map((key, index) => <div data-state-key={key} key={key}>
      <TextField label={key} data-issue-field={`material_states[${index}].material`} defaultValue={key} />
    </div>)}
    <EvidenceFieldMarkers records={[record]} scope="delete" onOpen={open} onChange={change} />
  </div>
  const view = render(form(false))
  fireEvent.click(await screen.findByRole('button', { name: 'Sn' }))
  expect(open).toHaveBeenLastCalledWith('tin', ['tin'])
  view.rerender(form(true))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Sn' })).toHaveAttribute('data-evidence-key', 'tin'))
  fireEvent.input(screen.getByRole('textbox', { name: 'Sn' }), { target: { value: 'Tin' } })
  await waitFor(() => expect(change).toHaveBeenCalledWith('material_states[1].material', 'snapshot'))
  expect(screen.queryByRole('textbox', { name: 'Pb' })).not.toBeInTheDocument()
})
it('材料摘要名称变化只更新所属标签，不扫描所有字段', async () => {
  const record = { key: 'missing', state_key: 'Sn', field: 'material_states[0].missing', label: '未显示字段', status: 'uncertain' as const, reason: '', evidences: [] }
  const view = render(<div data-evidence-scope="rename"><div data-state-key="Sn" data-state-label="旧名称" />
    <EvidenceFieldMarkers records={[record]} scope="rename" onOpen={() => {}} onChange={() => {}} /></div>)
  await screen.findByText(/旧名称.*未显示字段/)
  const root = view.container.querySelector('[data-evidence-scope]')!
  const scan = vi.spyOn(root, 'querySelectorAll')
  await act(async () => { (root.querySelector('[data-state-key]') as HTMLElement).dataset.stateLabel = '新名称'; await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(screen.getByText(/新名称.*未显示字段/)).toBeInTheDocument()
  expect(scan.mock.calls.filter(([selector]) => selector === '[data-issue-field]')).toHaveLength(0)
})
