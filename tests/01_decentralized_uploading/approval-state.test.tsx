import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { evidenceProblem } from '../../frontend/src/components/EvidenceFieldMarkers'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
const target = { target: 'upload' as const, target_id: 'approval-fixture' }
const original: EvidenceRecord = { key: 'optimization', item_key: 'optimization', field: 'material_states[2].structure_optimization',
  label: '结构优化核处理', current_value: 'classical_static', status: 'uncertain', reason: '已找到依据，待人工确认', evidences: [], required: true }
const decision = { contract: 'field-review-v2', action: 'approve' as const, actor_user_id: 7, occurred_at: '2026-10-23T08:00:00Z' }
const approved = { ...original, status: 'supported' as const, field_decision: decision }
let rows: EvidenceRecord[], flow: ReturnType<typeof useEvidenceWorkflow>
const detail = (record: EvidenceRecord) => ({ record, review_token: 'token', can_approve: true, source_state: 'empty' })
function Form() {
  flow = useEvidenceWorkflow({ target })
  return <><button onClick={() => flow.openIssue('optimization')}>打开字段</button>
    <span data-testid="red-count">{flow.records.filter(evidenceProblem).length}</span>{flow.dialog}</>
}
beforeEach(() => {
  rows = [original]
  vi.mocked(api.get).mockImplementation(async path => detail(rows.find(r => new URL('http://fixture' + path).searchParams.get('item_key') === r.key) || rows[0]) as never)
  vi.mocked(api.post).mockImplementation(async (path, body: any) => {
    if (path.endsWith('/field-decision')) {
      rows = rows.map(r => r.key === body.item_key ? { ...r, status: body.action === 'approve' ? 'supported' : 'uncertain', field_decision: { ...decision, action: body.action } } : r)
      return detail(rows.find(r => r.key === body.item_key)!) as never
    }
    return { version: 'v1', records: [...rows], needs_check: false } as never
  })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
async function open() {
  fireEvent.click(await screen.findByText('打开字段'))
  await waitFor(() => expect(screen.getByRole('button', { name: '人工审核不通过', exact: true })).toBeEnabled())
}
const pass = () => screen.getByRole('button', { name: '人工审核通过', exact: true })
it.each([
  { status: 'supported' },
  { status: 'supported', field_decision: decision },
  { status: 'uncertain', required: false },
  { status: 'missing', pending_review: true },
] as Partial<EvidenceRecord>[])('无红框状态 %j 的通过置灰，不通过可用', async state => {
  rows = [{ ...original, ...state }]; render(<Form />); await open()
  expect(screen.getByTestId('red-count')).toHaveTextContent('0')
  expect(pass()).toBeDisabled()
  fireEvent.click(pass())
  expect(vi.mocked(api.post).mock.calls.filter(([p]) => p.endsWith('/field-decision'))).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '人工审核不通过', exact: true }))
  await screen.findByText('人工修改记录')
  expect(vi.mocked(api.post).mock.calls.at(-1)?.[1]).toMatchObject({ action: 'reject' })
})
it('旧版本仍保留版本保护，不对过期内容保存人工决定', async () => {
  rows = [{ ...original, stale: true }]; render(<Form />)
  fireEvent.click(await screen.findByText('打开字段'))
  expect(await screen.findByRole('button', { name: '人工审核通过', exact: true })).toBeDisabled()
  expect(screen.getByRole('button', { name: '人工审核不通过', exact: true })).toBeDisabled()
})
it('红框通过后关闭并消红，重开通过置灰而不通过仍可用', async () => {
  render(<Form />); await open(); expect(pass()).toBeEnabled()
  fireEvent.click(pass())
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.getByTestId('red-count')).toHaveTextContent('0')
  await open(); expect(pass()).toBeDisabled()
  expect(screen.getByRole('button', { name: '人工审核不通过', exact: true })).toBeEnabled()
})
it.each(['network', 'invalid'])('保存异常 %s 保留侧栏与红框，不伪造通过', async kind => {
  render(<Form />); await open()
  if (kind === 'network') vi.mocked(api.post).mockRejectedValueOnce(new Error('保存失败'))
  else vi.mocked(api.post).mockResolvedValueOnce({})
  fireEvent.click(pass())
  await screen.findByText(kind === 'network' ? '保存失败' : '未收到已保存的人工审核结果，请重试；当前问题仍保留。')
  expect(screen.getByRole('dialog')).toBeVisible()
  expect(screen.getByTestId('red-count')).toHaveTextContent('1')
  expect(pass()).toBeEnabled()
})
it('通过后迟到的旧摘要不能恢复红框或重启通过按钮', async () => {
  render(<Form />); await open()
  let resolve!: (value: unknown) => void
  const implementation = vi.mocked(api.post).getMockImplementation()!
  vi.mocked(api.post).mockImplementation(async (path, body) => path.endsWith('/summary') ? await new Promise(r => { resolve = r }) as never : implementation(path, body))
  await act(async () => { void flow.restore(target); await Promise.resolve() })
  await waitFor(() => expect(resolve).toBeTypeOf('function'))
  fireEvent.click(pass())
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await act(async () => resolve({ version: 'old', records: [original], needs_check: false }))
  expect(screen.getByTestId('red-count')).toHaveTextContent('0')
  await open(); expect(pass()).toBeDisabled()
})
it('保存期间按钮置灰；切到其他字段后，迟到成功仅消除原字段红框', async () => {
  rows = [original, { ...original, key: 'other', item_key: 'other', field: 'paper.title', label: '另一字段' }]
  render(<Form />); await open()
  let resolve!: (value: unknown) => void
  vi.mocked(api.post).mockImplementationOnce(async () => await new Promise(r => { resolve = r }) as never)
  fireEvent.click(pass()); expect(pass()).toBeDisabled()
  fireEvent.click(screen.getByLabelText('关闭来源详情'))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await act(async () => flow.openIssue('other'))
  await screen.findByText('另一字段')
  await act(async () => resolve(detail(approved)))
  expect(screen.getByRole('dialog')).toHaveTextContent('另一字段')
  expect(screen.getByTestId('red-count')).toHaveTextContent('1')
})
it('保存期间修改无关字段，不丢弃本字段已保存的决定和关闭反馈', async () => {
  render(<Form />); await open()
  let resolve!: (value: unknown) => void
  vi.mocked(api.post).mockImplementationOnce(async () => await new Promise(r => { resolve = r }) as never)
  fireEvent.click(pass())
  await act(async () => flow.invalidate('paper.title'))
  await act(async () => resolve(detail(approved)))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.getByTestId('red-count')).toHaveTextContent('0')
})
it('另一字段正在加载详情时收到前一字段的保存成功，详情仍能正常加载', async () => {
  const other = { ...original, key: 'other', item_key: 'other', field: 'paper.title', label: '另一字段' }
  rows = [original, other]; render(<Form />); await open()
  let save!: (value: unknown) => void, source!: (value: unknown) => void
  vi.mocked(api.post).mockImplementationOnce(async () => await new Promise(r => { save = r }) as never)
  fireEvent.click(pass())
  fireEvent.click(screen.getByLabelText('关闭来源详情'))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  vi.mocked(api.get).mockImplementationOnce(async () => await new Promise(r => { source = r }) as never)
  await act(async () => flow.openIssue('other'))
  await waitFor(() => expect(source).toBeTypeOf('function'))
  await act(async () => save(detail(approved)))
  await act(async () => source(detail(other)))
  await waitFor(() => expect(screen.getByRole('button', { name: '人工审核不通过', exact: true })).toBeEnabled())
  expect(screen.getByRole('dialog')).toHaveTextContent('另一字段')
})
