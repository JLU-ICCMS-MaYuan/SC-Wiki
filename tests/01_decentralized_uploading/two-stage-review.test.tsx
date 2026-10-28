import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { aiReasonText, useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { evidenceProblem } from '../../frontend/src/components/EvidenceFieldMarkers'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { TextField } from '@mui/material'
import { createFieldDraftSaver, fieldChanges } from '../../frontend/src/lib/fieldDrafts'
import { api } from '../../frontend/src/lib/api'
import TcScientificField from '../../frontend/src/components/TcScientificField'
import ReviewFieldSettings from '../../frontend/src/components/ReviewFieldSettings'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const base: EvidenceRecord = { key: 'name', item_key: 'name', field: 'paper.title', label: '标题', current_value: 'old',
  status: 'unsupported', reason: '旧名称不对应', required: true, evidences: [] }
beforeEach(() => {
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', records: [base], needs_check: false })
  vi.mocked(api.get).mockResolvedValue({ record: {}, records: [], history: [] })
  vi.mocked(api.put).mockResolvedValue({ saved: true })
})

it('无改保存及改后恢复在请求发送前短路', async () => {
  const saver = createFieldDraftSaver({ target: 'upload', target_id: 'test' })
  saver.initialize({ paper: { title: 'old' } })
  await saver.save({ paper: { title: 'old' } })
  expect(api.get).not.toHaveBeenCalled()
  expect(api.patch).not.toHaveBeenCalled()
})

it('局部写入只传变化字段及稳定实体身份', () => {
  const before = { material_states: [{ state_key: 's', property_modules: [{ module_key: 'm', records: [
    { record_key: 'r', name_raw: 'N(EF)', value_raw: '17.27', unit_raw: 'states/eV' },
  ] }] }] }
  const after = JSON.parse(JSON.stringify(before))
  after.material_states[0].property_modules[0].records[0].name_raw = '电子态密度'
  const changes = fieldChanges(before, after)
  expect(changes).toHaveLength(1)
  expect(changes[0].path).toEqual(['material_states', {key: 'state_key', value: 's'}, 'property_modules',
    {key: 'module_key', value: 'm'}, 'records', {key: 'record_key', value: 'r'}, 'name_raw'])
})

it('人工理由与旧接受标记不能解除有效的失败红框', () => {
  expect(evidenceProblem({...base, resolution: '我确认', human_confirmed: true,
    proposal_draft: { accepted: true, reason: '说明', values: {} }})).toBe(true)
  expect(evidenceProblem({...base, pending_review: true})).toBe(false)
})

it('字段设置入口无论原字段分项如何定位，都展示完整纵向设置表单', async () => {
  const { default: ScientificFieldSettingsDrawer } = await import('../../frontend/src/components/ScientificFieldSettingsDrawer')
  const host = document.createElement('div'); document.body.append(host)
  render(<ScientificFieldSettingsDrawer value={{name: 'Tc', kind: 'number', raw: '331', unit: 'K'}} readOnly={false}
    presentation={{container: host, part: 'raw', onDone: () => {}}} onChange={() => {}} onApply={() => {}} onClose={() => {}} />)
  expect(screen.getByLabelText('字段名称（key）')).toHaveValue('Tc')
  expect(screen.getByLabelText('值类型')).toBeInTheDocument()
  expect(screen.getByLabelText('值')).toHaveValue('331')
  expect(screen.getByLabelText('单位')).toHaveValue('K')
  host.remove()
})

it('待提交核对状态不伪装成 AI 理由', () => {
  expect(aiReasonText({...base, stale: true, pending_review: true, reason: '原文给出了明确的旧证据结论'}, () => '无理由'))
    .toBe('原文给出了明确的旧证据结论')
  expect(aiReasonText({...base, stale: true, pending_review: true, reason: ''}, () => '无理由')).toBe('')
})

it('μ* 真实控件通过来源侧栏定位设置表单并保存修改', async () => {
  const field = 'material_states[0].property_modules[0].records[0].payload.parameters.mu_star'
  const apply = vi.fn()
  const change = vi.fn()
  render(<>
    <TcScientificField value={0.1} label="μ*" field={field} readOnly={false} onChange={change} onApply={apply} />
    <ReviewFieldSettings identity="mu" field={field} settingsField={field} sourceField={field}
      enabled onDone={() => {}} />
  </>)
  await screen.findByLabelText('字段名称（key）')
  expect(screen.getByLabelText('值')).toHaveValue('0.1')
  expect(screen.getByLabelText('值类型')).toBeInTheDocument()
  expect(screen.getByLabelText('单位')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('字段名称（key）'), {target: {value: 'μ* 修订值'}})
  fireEvent.click(screen.getByRole('button', {name: '应用修改'}))
  await waitFor(() => expect(apply).toHaveBeenCalledWith(0.1, {name_raw: 'μ* 修订值', unit_raw: ''}))
})

it('主动核对使用草稿令牌，通过后关闭且提交直接复用', async () => {
  const passed = {...base, status: 'supported' as const, pending_review: false, reason: '模型已核对当前值及依据'}
  const save = vi.fn().mockResolvedValue(true)
  vi.mocked(api.post).mockImplementation(async (path) => {
    if (path.endsWith('/summary')) return {version: 'draft-v1', records: [base], needs_check: true} as never
    if (path.endsWith('/jobs')) return {id: 'field-job', status: 'queued'} as never
    if (path.endsWith('/submit-check')) return {status: 'completed', version: 'science-v1', records: [passed]} as never
    throw new Error(path)
  })
  vi.mocked(api.get).mockImplementation(async path => path.endsWith('/jobs/field-job')
    ? {id: 'field-job', status: 'completed', version: 'science-v1', records: [passed]} as never
    : {record: {}, records: [], history: []} as never)
  let flow: ReturnType<typeof useEvidenceWorkflow>
  function Harness() {
    flow = useEvidenceWorkflow({target: {target: 'upload', target_id: 'test'}, saveCurrent: save})
    return <><button onClick={() => flow.openIssue('name')}>打开核对</button>{flow.dialog}</>
  }
  render(<Harness />)
  await waitFor(() => expect(flow!.records).toHaveLength(1))
  fireEvent.click(screen.getByText('打开核对'))
  fireEvent.click(await screen.findByRole('button', {name: '大模型核对'}))
  await waitFor(() => expect(flow!.records[0].status).toBe('supported'))
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/jobs', {target: 'upload', target_id: 'test',
    expected_draft_version: 'draft-v1', purpose: 'field', retry_keys: ['name'], progress_id: expect.stringMatching(/^[0-9a-f]{32}$/)})
  expect(screen.queryByRole('button', {name: '大模型核对'})).not.toBeInTheDocument()
  let result
  await act(async () => { result = await flow!.gate({target: 'upload', target_id: 'test'}) })
  expect(result).toMatchObject({expected_evidence_version: 'science-v1'})
  expect(vi.mocked(api.post).mock.calls.filter(([path]) => path.endsWith('/jobs'))).toHaveLength(1)
})

it('编辑只去当前键旧红框，不预检查、不启动模型；恢复旧值不实时新增红框', async () => {
  let value = 'old'
  let flow: ReturnType<typeof useEvidenceWorkflow>
  function Harness() {
    flow = useEvidenceWorkflow({ target: {target: 'upload', target_id: 'test'},
      getCurrentValue: r => ({ value, field: r.field }) })
    return <div>{flow.records.map(r => <span key={r.key}>{evidenceProblem(r) ? '红' : '不红'}</span>)}</div>
  }
  render(<Harness />)
  await screen.findByText('红')
  await act(async () => { value = 'new'; flow!.invalidate('paper.title'); await new Promise(r => setTimeout(r, 5)) })
  expect(screen.getByText('不红')).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(1)
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/summary', {target: 'upload', target_id: 'test'})
  await act(async () => { value = 'old'; flow!.invalidate('paper.title'); await new Promise(r => setTimeout(r, 5)) })
  expect(screen.getByText('不红')).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('认可原内容只保存正式人工决定，不写科学值、不调用模型、不填写理由', async () => {
  const save = vi.fn().mockResolvedValue(true)
  const decision = {contract: 'field-review-v2', action: 'approve', actor_user_id: 7, occurred_at: '2026-10-22T08:00:00Z'}
  vi.mocked(api.get).mockResolvedValue({record: base, review_token: 'field-token', can_approve: true, source_state: 'empty'})
  vi.mocked(api.post).mockImplementation(async (path) => path.endsWith('/field-decision')
    ? {record: {...base, status: 'supported', field_decision: decision}, review_token: 'approved', can_approve: true} as never
    : {version: 'v1', records: [base], needs_check: false} as never)
  function Harness() {
    const flow = useEvidenceWorkflow({target: {target: 'upload', target_id: 'test'}, saveCurrent: save})
    return <><button onClick={() => flow.openIssue('name')}>打开</button>{flow.dialog}</>
  }
  render(<Harness />)
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByText('打开'))
  await waitFor(() => expect(screen.getByRole('button', {name: '人工审核通过', exact: true})).toBeEnabled())
  expect(screen.queryByLabelText('人工修改判断理由（必填）')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', {name: '人工审核通过', exact: true}))
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
  expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/field-decision', {target: 'upload', target_id: 'test', item_key: 'name', action: 'approve', review_token: 'field-token'})
  expect(save).not.toHaveBeenCalled()
  expect(api.put).not.toHaveBeenCalled()
})

it('提交同版本失败不会进入旧人工理由绕过路径', async () => {
  let flow: ReturnType<typeof useEvidenceWorkflow>
  function Harness() { flow = useEvidenceWorkflow(); return <>{flow.dialog}</> }
  render(<Harness />)
  vi.mocked(api.post).mockResolvedValue({ status: 'completed', version: 'v1', records: [base] })
  let answer
  await act(async () => { answer = await flow!.gate({target: 'upload', target_id: 'test'}) })
  expect(answer).toBeNull()
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/submit-check', {target: 'upload', target_id: 'test', progress_id: expect.stringMatching(/^[0-9a-f]{32}$/)})
})

it('原文加载中或失败不显示无证据，重试和同版本摘要刷新不丢原文', async () => {
  let rejectLoad: (error: Error) => void
  vi.mocked(api.get).mockImplementationOnce(() => new Promise((_, reject) => { rejectLoad = reject }))
  let flow: ReturnType<typeof useEvidenceWorkflow>
  function Harness() { flow = useEvidenceWorkflow({target: {target: 'upload', target_id: 'test'}}); return <><button onClick={() => flow.openIssue('name')}>看原文</button>{flow.dialog}</> }
  render(<Harness />)
  await waitFor(() => expect(flow!.records).toHaveLength(1))
  fireEvent.click(screen.getByText('看原文'))
  expect(await screen.findByText('正在加载此字段的原文依据…')).toBeInTheDocument()
  expect(screen.queryByText(/未找到可定位的论文原文依据/)).not.toBeInTheDocument()
  await act(async () => rejectLoad!(new Error('连接失败')))
  expect(await screen.findByText(/原文依据加载失败/)).toBeInTheDocument()
  expect(screen.queryByText(/未找到可定位的论文原文依据/)).not.toBeInTheDocument()
  vi.mocked(api.get).mockResolvedValue({record: {...base, evidences: [{file_id: 'main', quote: '原文确实保存着', source_name: 'paper.pdf'}]}, review_token: 'current', can_approve: true, source_state: 'available'})
  fireEvent.click(screen.getByRole('button', {name: '重试加载'}))
  await screen.findByText(/原文确实保存着/)
  await act(async () => { await flow!.restore({target: 'upload', target_id: 'test'}) })
  expect(screen.getByText(/原文确实保存着/)).toBeInTheDocument()
})

it('人工不通过只记录拒绝并展开修改记录，不自动修改值或启动模型', async () => {
  const row = {...base, item_key: 'a'.repeat(64)}
  vi.mocked(api.get).mockImplementation(async path => path.includes('/manual/')
    ? {ok: true, data: {changed: false, reason: '', no_evidence_reason: '', items: []}} as never
    : {record: row, review_token: 'before', can_approve: true, source_state: 'empty'} as never)
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('/field-decision')
    ? {record: {...row, field_decision: {contract: 'field-review-v2', action: 'reject', actor_user_id: 7, occurred_at: '2026-10-22T08:00:00Z'}}, review_token: 'after', can_approve: true} as never
    : {version: 'v', records: [row], needs_check: false} as never)
  function Harness() { const flow = useEvidenceWorkflow({target: {target: 'upload', target_id: 'test'}}); return <><button onClick={() => flow.openIssue('name')}>打开拒绝</button>{flow.dialog}</> }
  render(<Harness />)
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByText('打开拒绝'))
  await waitFor(() => expect(screen.getByRole('button', {name: '人工审核不通过'})).toBeEnabled())
  fireEvent.click(screen.getByRole('button', {name: '人工审核不通过'}))
  await screen.findByLabelText('人工修改判断理由（必填）')
  expect(screen.getByRole('button', {name: '保存', exact: true})).toBeDisabled()
  expect(api.put).not.toHaveBeenCalled()
  expect(api.patch).not.toHaveBeenCalled()
  expect(vi.mocked(api.post).mock.calls.map(([path]) => path)).toEqual(['/api/rag/evidence/summary', '/api/rag/evidence/field-decision'])
})

it('提交被程序阻止时即使侧栏关闭也显示具体缺项', async () => {
  let flow: ReturnType<typeof useEvidenceWorkflow>
  function Harness() { flow = useEvidenceWorkflow(); return <>{flow.dialog}</> }
  render(<Harness />)
  vi.mocked(api.post).mockRejectedValue(Object.assign(new Error('人工修改记录不完整'), {issues: [{field: 'paper.title', message: '请填写人工修改理由'}]}))
  await act(async () => { expect(await flow!.gate({target: 'upload', target_id: 'test'})).toBeNull() })
  expect(screen.getByRole('alert')).toHaveTextContent('请填写人工修改理由')
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('N(EF)真实控件定位：名称失败只标名称，数值与单位各自打开自己的侧栏', async () => {
  const path = 'material_states[0].property_modules[0].records[0]'
  const fields = ['name_raw', 'value_raw', 'unit_raw']
  const rows: EvidenceRecord[] = fields.map((field, i) => ({...base, key: field, item_key: field,
    state_key: 's', module_key: 'm', record_key: 'r', record_field: field,
    field: `${path}.${field}`, fields: [`${path}.${field}`], label: field,
    status: i === 0 ? 'unsupported' : 'supported'}))
  const open = vi.fn()
  render(<div data-evidence-scope="dos"><div data-state-key="s"><div data-module-key="m"><div data-record-key="r">
    {fields.map(field => <TextField key={field} label={field} data-issue-field={`${path}.${field}`}
      data-dos-current-value={field === 'value_raw' || undefined} defaultValue={field} />)}
  </div></div></div><EvidenceFieldMarkers records={rows} scope="dos" onOpen={open} onChange={() => {}} /></div>)
  await waitFor(() => expect(document.querySelectorAll('[data-evidence-problem="true"]')).toHaveLength(1))
  expect(document.querySelector('[data-evidence-problem="true"]')!.closest('[data-issue-field]')?.getAttribute('data-issue-field')).toBe(`${path}.name_raw`)
  fireEvent.click(screen.getByRole('button', {name: 'unit_raw'}))
  expect(open).toHaveBeenLastCalledWith('unit_raw', ['unit_raw'])
  fireEvent.click(screen.getByRole('button', {name: 'value_raw'}))
  expect(open).toHaveBeenLastCalledWith('value_raw', ['value_raw'])
})
