import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import FieldAICandidate from '../../frontend/src/components/FieldAICandidate'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const original: EvidenceRecord = { key: 'motivation', item_key: 'motivation', field: 'paper.research_motivation', label: '研究驱动力',
  current_value: '1. Existing motivation.', status: 'supported', reason: '原值理由', evidences: [], human_confirmed: true,
  field_decision: { contract: 'field-review-v2', action: 'approve', actor_user_id: 7, occurred_at: '2026-10-22' } }
const candidate = { id: 'candidate', token: 'token', values: { '': '1. New motivation.' }, explanation: '新候选的独立理由',
  evidences: [], can_apply: true, historical: false }
const applied = { ...original, current_value: candidate.values[''], reason: candidate.explanation, ai_reason: candidate.explanation }
const target = { target: 'upload' as const, target_id: 'test' }
let saved = false
beforeEach(() => {
  saved = false
  vi.mocked(api.post).mockImplementation(async (url) => {
    if (url.endsWith('/summary')) return {version: 'v', records: [saved ? applied : original]} as never
    if (url.endsWith('/field-candidate/prepare')) return { preparation_id: 'p', patches: [{key: 'motivation', item_key: 'motivation', field: original.field, values: candidate.values}]} as never
    if (url.endsWith('/field-candidate/finalize')) return { record: applied, candidate: null, review_token: 'new', source_state: 'available' } as never
    if (url.endsWith('/submit-check')) return { status: 'completed', version: 'v2', records: [applied] } as never
    throw new Error('unexpected request: ' + url)
  })
  vi.mocked(api.get).mockImplementation(async () => ({ record: saved ? applied : original, review_token: 'review', source_state: 'available', candidate: saved ? null : candidate }) as never)
})

function Harness({failSave = false}: {failSave?: boolean}) {
  const [value, setValue] = useState(original.current_value)
  const [submitted, setSubmitted] = useState(false)
  const flow = useEvidenceWorkflow({ target, getCurrentValue: () => ({value, field: original.field}), saveCurrent: async () => true,
    saveCandidate: async patches => { if (failSave) return false; saved = true; setValue(patches[0].values['']); return true } })
  return <><output data-testid="value">{String(value)}</output>
    <input aria-label="并发编辑" value={String(value)} onChange={event => setValue(event.target.value)} />
    <button onClick={() => flow.openIssue('motivation', undefined, undefined, 'settings')}>打开字段</button>
    <button onClick={() => void flow.gate(target).then(result => setSubmitted(Boolean(result)))}>提交</button>
    {submitted && <span>提交成功</span>}{flow.dialog}</>
}

it('候选位于字段设置，应用新值和理由后提交零模型任务', async () => {
  await act(async () => render(<Harness />))
  fireEvent.click(screen.getByText('打开字段'))
  const card = await screen.findByRole('region', {name: 'AI 候选值'})
  expect(await within(card).findByText('1. New motivation.')).toBeVisible()
  expect(within(card).getByText('新候选的独立理由')).toBeVisible()
  fireEvent.click(within(card).getByRole('button', {name: '应用 AI 候选值'}))
  await waitFor(() => expect(screen.getByTestId('value')).toHaveTextContent('1. New motivation.'))
  await screen.findByText('已应用 AI 候选值并保存认可，提交时无需再次核对。')
  fireEvent.click(screen.getByText('提交'))
  await screen.findByText('提交成功')
  expect(vi.mocked(api.post).mock.calls.filter(([url]) => url.endsWith('/jobs'))).toHaveLength(0)
  const prepare = vi.mocked(api.post).mock.calls.find(([url]) => url.endsWith('/field-candidate/prepare'))![1]
  expect(prepare).toEqual({...target, item_key: 'motivation', candidate_token: 'token'})
})

it('保存失败不确认通过，候选与原值保留', async () => {
  await act(async () => render(<Harness failSave />))
  fireEvent.click(screen.getByText('打开字段'))
  const button = await screen.findByRole('button', {name: '应用 AI 候选值'})
  fireEvent.click(button)
  await waitFor(() => expect(vi.mocked(api.post).mock.calls.some(([url]) => url.endsWith('/field-candidate/prepare'))).toBe(true))
  expect(screen.getByTestId('value')).toHaveTextContent('1. Existing motivation.')
  expect(vi.mocked(api.post).mock.calls.some(([url]) => url.endsWith('/field-candidate/finalize'))).toBe(false)
})

it('确认失败可重试且不再次保存或调用模型', async () => {
  const originalPost = vi.mocked(api.post).getMockImplementation()!
  let attempts = 0
  vi.mocked(api.post).mockImplementation(async (url, body, opts) => {
    if (url.endsWith('/field-candidate/finalize') && ++attempts === 1) throw new Error('确认暂时失败')
    return originalPost(url, body, opts)
  })
  await act(async () => render(<Harness />))
  fireEvent.click(screen.getByText('打开字段'))
  fireEvent.click(await screen.findByRole('button', {name: '应用 AI 候选值'}))
  const retry = await screen.findByRole('button', {name: '重试确认已保存候选'})
  await waitFor(() => expect(retry).toBeEnabled())
  fireEvent.click(retry)
  await screen.findByText('已应用 AI 候选值并保存认可，提交时无需再次核对。')
  expect(vi.mocked(api.post).mock.calls.filter(([url]) => url.endsWith('/field-candidate/prepare'))).toHaveLength(1)
})

it('历史、过期及只读候选不可直接采纳，列表值可读', () => {
  render(<FieldAICandidate candidate={{...candidate, values: {'': ['DFT', 'SSCHA']}, historical: true, can_apply: false}}
    disabled={false} busy={false} retrying={false} onApply={vi.fn()} />)
  expect(screen.getByText('DFT')).toBeVisible()
  expect(screen.getByRole('button', {name: '应用 AI 候选值'})).toBeDisabled()
})

it('准备期间字段被修改，不用候选覆盖未保存的新输入', async () => {
  const post = vi.mocked(api.post).getMockImplementation()!
  let finish!: () => void
  vi.mocked(api.post).mockImplementation(async (url, body, opts) => {
    if (url.endsWith('/field-candidate/prepare')) await new Promise<void>(resolve => { finish = resolve })
    return post(url, body, opts)
  })
  await act(async () => render(<Harness />))
  fireEvent.click(screen.getByText('打开字段'))
  fireEvent.click(await screen.findByRole('button', {name: '应用 AI 候选值'}))
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.change(screen.getByLabelText('并发编辑'), {target: {value: 'Concurrent unsaved edit'}})
  await act(async () => finish())
  expect(screen.getByTestId('value')).toHaveTextContent('Concurrent unsaved edit')
  expect(saved).toBe(false)
  expect(vi.mocked(api.post).mock.calls.some(([url]) => url.endsWith('/field-candidate/finalize'))).toBe(false)
})
