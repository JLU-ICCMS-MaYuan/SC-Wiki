import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import UploadModelActivity from '../../frontend/src/components/UploadModelActivity'
import type { UploadTaskState } from '../../frontend/src/lib/paperProcessing'

const t = (key: string) => key
vi.mock('../../frontend/src/context/LanguageContext', () => ({ useLanguage: () => ({ t }) }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 2 } }), getStoredToken: () => null }))
const task = { task_id: 'task', status: 'summarizing', stage: 'summarizing',
  human_questions_summary: { queue_revision: 1, pending_count: 1, can_answer_existing: true, can_create_questions: true },
} as UploadTaskState
const question = (id: string) => ({ question_id: id, prompt_revision: 1, target_token: id,
  title: `真实冲突-${id}`, state: 'waiting', checked_context: '已核对正文与附件',
  target_refs: [{ item_key: id, state_key: 's1', field: 'reported_space_group_symbol' }],
  source_refs: [{ file_id: 'main', quote: '正文 P63/mmc' }, { file_id: 'si', quote: '附件 Cc' }],
  options: [{ choice_id: 'recommended', label: '采用推荐处理', description: '采用附件，保留冲突' },
    { choice_id: 'investigate', label: '需要进一步查证', description: '查证' },
    { choice_id: 'manual', label: '人工填写', description: '填写方向' }] })
const props = { onUpdated: vi.fn(), onRetry: vi.fn(), onManual: vi.fn() }
let questions: ReturnType<typeof question>[]
let fetcher: ReturnType<typeof vi.fn>
beforeEach(() => {
  sessionStorage.clear(); questions = [question('q1')]
  fetcher = vi.fn(async (_url: string, init: RequestInit = {}) => new Response(JSON.stringify({ ok: true,
    data: init.method === 'POST' ? { accepted: true } : {
      queue_revision: questions.length, pending_count: questions.length, can_answer_existing: true, questions,
    } }), { headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetcher)
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('mounts in real process panel; no click means no answer and later sends nothing', async () => {
  render(<UploadModelActivity task={task} {...props} />)
  expect(await screen.findByText('真实冲突-q1')).toBeVisible()
  expect(screen.getByTestId('upload-model-activity')).toContainElement(screen.getByTestId('upload-human-questions'))
  fireEvent.click(screen.getByRole('button', { name: 'upload.humanQuestionLater' }))
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '采用推荐处理' }))
  await waitFor(() => expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1))
  const call = fetcher.mock.calls.find(call => call[1]?.method === 'POST')!
  expect(String(call[0])).toContain('/task/human-questions/q1/answers')
  expect(JSON.parse(String(call[1].body)).choice_id).toBe('recommended')
})

it('retains manual input and focus when another question is appended; failure retries same answer ID', async () => {
  const view = render(<UploadModelActivity task={task} {...props} />)
  await screen.findByText('真实冲突-q1')
  fireEvent.click(screen.getByRole('button', { name: 'upload.humanQuestionManual' }))
  const direction = screen.getByLabelText('upload.humanQuestionDirection')
  fireEvent.change(direction, { target: { value: '采用 Cc' } })
  fireEvent.change(screen.getByLabelText('upload.humanQuestionReason'), { target: { value: '附件结构直接给出' } })
  direction.focus()
  questions.push(question('q2'))
  view.rerender(<UploadModelActivity task={{ ...task, human_questions_summary: { ...task.human_questions_summary!, queue_revision: 2 } }} {...props} />)
  await screen.findByText('真实冲突-q2')
  expect(direction).toHaveValue('采用 Cc'); expect(direction).toHaveFocus()
  fetcher.mockImplementation(async (_url: string, init: RequestInit = {}) => init.method === 'POST'
    ? new Response(JSON.stringify({ detail: { message: '保存失败' } }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    : new Response(JSON.stringify({ ok: true, data: { queue_revision: 2, questions, can_answer_existing: true } }), { headers: { 'Content-Type': 'application/json' } }))
  const card = within(screen.getByTestId('human-question-q1'))
  fireEvent.click(card.getByRole('button', { name: 'upload.humanQuestionSend' }))
  await card.findByText('保存失败')
  expect(direction).toHaveValue('采用 Cc')
  fireEvent.click(card.getByRole('button', { name: 'upload.humanQuestionSend' }))
  await waitFor(() => expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(2))
  const sent = fetcher.mock.calls.filter(call => call[1]?.method === 'POST').map(call => JSON.parse(String(call[1].body)))
  expect(sent[0].answer_id).toBe(sent[1].answer_id)
  expect(sent[0].manual_text).toBe('采用 Cc')
})

it('does not fetch questions for legacy or disabled task without a queue', () => {
  render(<UploadModelActivity task={{ ...task, human_questions_summary: undefined }} {...props} />)
  expect(fetcher).not.toHaveBeenCalled()
})
