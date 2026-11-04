import '@testing-library/jest-dom/vitest'
import formSeeds from '../fixtures/issue176/form-definitions.json'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
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
const draft = { paper, material_states: states, structure_candidates: [], _parsing_workflow: {
  workflow_key: 'conventional-theory-calculation', workflow_version: 1,
  form_key: 'scientific-form-contract', form_version: 1, form_sha256: 'a'.repeat(64),
} }
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
it.each(['upload', 'revision', 'admin', 'superadmin'])('191 四类宿主：%s 未完成字段可见并从自身侧栏恢复', async kind => {
  const record = { key: 'graph-review', item_key: 'graph-review', field: 'paper.knowledge_graph_title',
    label: '图谱科学标题', current_value: 'Graph title', required: true,
    status: 'unchecked', pending_review: true, reason: '模型技术失败，输入已保留。', evidences: [] }
  const originalPost = vi.mocked(api.post).getMockImplementation()!
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('/summary')
    ? { version: 'v1', records: [record], needs_check: false } as never : originalPost(path))
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async path => path.includes('/field-detail')
    ? { record, review_token: 'graph-token', approval_state: 'ready', source_state: 'empty' } as never : original(path))
  await host(kind)
  expect(document.querySelector('[data-evidence-pending-navigation]')).toBeNull()
  const caption = await screen.findByRole('button', { name: /图谱.*标题/ })
  expect(caption).toHaveAttribute('data-evidence-status', 'failed')
  expect(caption).toHaveAttribute('data-evidence-caption-problem', 'true')
  fireEvent.click(caption)
  fireEvent.click(await screen.findByRole('tab', { name: '来源核对' }))
  await waitFor(() => expect(document.querySelector('[data-field-ai-reason]')).toHaveTextContent(record.reason))
  expect(screen.getByRole('button', { name: '大模型核对', exact: true })).toBeEnabled()
  expect(document.querySelector('[data-field-ai-reason]')).toHaveAttribute('data-evidence-status', 'failed')
  expect(vi.mocked(api.post).mock.calls.filter(([path]) => path.endsWith('/jobs'))).toHaveLength(0)
})
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
it.each(['upload', 'revision', 'admin', 'superadmin'])('%s 完整宿主：保持解析流程和表单身份', async kind => {
  await host(kind)
  expect(screen.getByText('解析审核流程：常规超导理论计算 · 表单 v1')).toBeVisible()
})
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

it.each(['upload', 'revision', 'admin', 'superadmin'])('#176 %s 固定 Tc 表单和其他方法编辑保持宿主隔离', async kind => {
  clearFormDefinitionCache()
  const defs = formSeeds.filter(d => d.target_kind === 'property_record' && d.module_code === 'superconductive_properties')
  const oldGet = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (...args) => {
    const path = args[0]
    if (path.startsWith('/api/form-definitions?')) return defs as never
    if (path.startsWith('/api/form-definitions/')) return defs.find(d => path.includes(encodeURIComponent(d.definition_key))) as never
    return oldGet(...args)
  })
  ;(states[0] as any).property_modules = [{module_key:'tc176',module_code:'superconductive_properties',
    definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[{
      record_key:'point176',module_code:'superconductive_properties',property_code:'tc',record_type:'predicted_tc',
      definition_key:'record.superconductive_properties.predicted_tc.other',definition_version:1,method_code:'other',
      method_raw:'Original method',name_raw:'Tc',value_kind:'number',value_number:235,value_raw:'235 K',unit_raw:'K',
      canonical_unit:'K',is_representative:false,payload:{parameters:{lambda_ep:2.69,mu_star:0.1},
        calculation_conditions:{},tc_group:{version:1,group_key:'g176',method_key:'m176',point_key:'p176'}},
    }]}]
  try {
    await host(kind)
    fireEvent.click(screen.getAllByText('超导性质').find(node => node.closest('[data-property-module-toggle]'))!)
    const input = await screen.findByLabelText('具体方法名称')
    counters.cards=[]
    fireEvent.change(input,{target:{value:'用户自定义方法'}})
    await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))})
    expect(screen.getByLabelText('具体方法名称')).toHaveValue('用户自定义方法')
    expect(screen.getByLabelText('Tc')).toHaveValue('235')
    expect(screen.queryByLabelText('文本值')).not.toBeInTheDocument()
    expect(new Set(counters.cards)).toEqual(new Set([0]))
    expect(vi.mocked(api.post).mock.calls.some(([path])=>/jobs|preflight|submit-check/.test(path))).toBe(false)
  } finally {
    states[0].property_modules=[]
    clearFormDefinitionCache()
  }
})

it.each(['upload', 'revision', 'admin', 'superadmin'])('213 %s 完整宿主：材料大纲可折叠、定位且不写入', async kind => {
  await host(kind)
  const outline = screen.getByRole('navigation', { name: '研究材料大纲' })
  const target = document.querySelector('[data-state-key="s1"]') as HTMLElement
  const scroll = vi.fn()
  target.scrollIntoView = scroll
  fireEvent.click(within(outline).getByRole('button', { name: /#2 · 空间群未填写 · Sn · 压强未填写/ }))
  expect(scroll).toHaveBeenCalled()
  fireEvent.click(within(outline).getByRole('button', { name: '收起研究材料大纲' }))
  expect(within(outline).queryByRole('button', { name: /#2 ·/ })).not.toBeInTheDocument()
  fireEvent.click(within(outline).getByRole('button', { name: '展开研究材料大纲' }))
  expect(within(outline).getByRole('button', { name: /#2 ·/ })).toBeVisible()
  expect(api.patch).not.toHaveBeenCalled()
  expect(vi.mocked(api.post).mock.calls.some(([path]) => /jobs|submit-check/.test(path))).toBe(false)
})

it.each(['admin', 'superadmin'])('213 %s 完整宿主：失权统一一条警告且写入口不可用', async kind => {
  const fail = Object.assign(new Error('稿件已交出，当前没有编辑权；须由其他合法经手人正式退回'), { code: 'manuscript_handed_off', status: 409 })
  const get = vi.mocked(api.get).getMockImplementation()!
  const post = vi.mocked(api.post).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async path => {
    if (path.includes('/draft-state')) throw fail
    if (path.includes('/structural-records/paper/')) throw new Error('独立结构读取失败213')
    return get(path)
  })
  vi.mocked(api.post).mockImplementation(async path => {
    if (path.endsWith('/summary') || path.endsWith('/open-workdraft')) throw fail
    return post(path)
  })
  await host(kind)
  expect(screen.getAllByText('稿件已交出，当前账号没有编辑权。')).toHaveLength(1)
  expect(screen.queryByText(/加载失败.*稿件已交出/)).not.toBeInTheDocument()
  expect(screen.getByText(/独立结构读取失败213/)).toBeVisible()
  expect(screen.getByDisplayValue('Original title')).toBeDisabled()
  expect(screen.getByRole('button', { name: '提交审核', exact: true })).toBeDisabled()
  expect(api.patch).not.toHaveBeenCalled()
})


it.each(["upload", "revision", "admin", "superadmin"])("220 %s 宿主标红：原免审项实际输入立即红，同值及未改空项不红，保存不消红", async kind => {
  const record = {key:"empty-doi",item_key:"empty-doi",field:"paper.doi",label:"DOI",current_value:null,
    status:"unchecked",required:false,human_modified:false,pending_review:false,evidences:[],reason:""}
  const original = vi.mocked(api.post).getMockImplementation()!
  vi.mocked(api.post).mockImplementation(async (path, body) => path.endsWith("/summary")
    ? {version:"v1",records:[record],needs_check:false} as never : original(path,body))
  await host(kind)
  const caption = await screen.findByRole("button",{name:"DOI"})
  expect(caption).toHaveAttribute("data-evidence-caption-problem","false")
  const input=screen.getByRole("textbox",{name:"DOI"})
  fireEvent.input(input,{target:{value:""}})
  expect(caption).toHaveAttribute("data-evidence-caption-problem","false")
  counters.cards=[]
  fireEvent.input(input,{target:{value:"10.1234/manual"}})
  await waitFor(()=>expect(caption).toHaveAttribute("data-evidence-caption-problem","true"))
  expect(counters.cards).toEqual([])
  expect(vi.mocked(api.post).mock.calls.filter(([path])=>/jobs|submit-check|preflight/.test(path))).toHaveLength(0)
  const save=screen.getByRole("button",{name:/立即保存|保存修改|保存更改/})
  fireEvent.click(save)
  await waitFor(()=>expect(api.patch).toHaveBeenCalled())
  expect(caption).toHaveAttribute("data-evidence-caption-problem","true")
})
