import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { evidenceProblem } from '../../frontend/src/components/EvidenceFieldMarkers'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { TextField } from '@mui/material'
import { createFieldDraftSaver, fieldChanges } from '../../frontend/src/lib/fieldDrafts'
import { api } from '../../frontend/src/lib/api'

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

it('完成只保存实际改动并关闭，不调用预检查或接受建议接口', async () => {
  const save = vi.fn().mockResolvedValue(true)
  function Harness() {
    const flow = useEvidenceWorkflow({target: {target: 'upload', target_id: 'test'}, saveCurrent: save})
    return <><button onClick={() => flow.openIssue('name')}>打开</button>{flow.dialog}</>
  }
  render(<Harness />)
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByText('打开'))
  await screen.findByRole('button', {name: '完成', exact: true})
  fireEvent.click(screen.getByRole('button', {name: '完成', exact: true}))
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1))
  expect(api.post).toHaveBeenCalledTimes(1)
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
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/submit-check', {target: 'upload', target_id: 'test'})
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
