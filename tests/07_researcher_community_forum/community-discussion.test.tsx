import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import CommunityMarkdown from '../../frontend/src/components/community/CommunityMarkdown'
import CommunityComposer from '../../frontend/src/components/community/CommunityComposer'
import CommentPanel from '../../frontend/src/components/community/CommentPanel'
import DanmakuPanel from '../../frontend/src/components/community/DanmakuPanel'
import { api } from '../../frontend/src/lib/api'

const auth = vi.hoisted(() => ({ user: { id: 1, username: 'alice', is_email_verified: true }, token: 'test' }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => auth, getStoredToken: () => auth.token }))
vi.mock('../../frontend/src/components/AuthDialog', () => ({ default: () => null }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(), put: vi.fn() } }))
const comment = { id: 42, kind: 'comment', body: '已有评论', title: '', status: 'visible', author: { username: 'bob' }, parent_id: null, reply_to_id: null, can_reply: true, can_edit: false, can_delete: false, created_at: '2026-09-17T00:00:00Z', url: '/systems/Hg' }
beforeEach(() => { vi.clearAllMocks(); window.history.replaceState(null, '', '/'); vi.mocked(api.get).mockResolvedValue({ items: [], total: 0 }); vi.mocked(api.post).mockResolvedValue({ ...comment, id: 43 }) })
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('community content and interactions', () => {
  it('renders formatting and math without raw HTML, scripts, images or unsafe links', () => {
    const { container } = render(<CommunityMarkdown content={'**结论** $T_c$\n\n<img src="https://tracker.test/x" onerror="alert(1)">\n\n![remote](https://tracker.test/x) [danger](javascript:alert%281%29) [paper](https://doi.org/example)'} />)
    expect(screen.getByText('结论').tagName).toBe('STRONG')
    expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('img,script')).toBeNull()
    expect(screen.getByText('danger')).not.toHaveAttribute('href')
    expect(screen.getByText('paper')).toHaveAttribute('rel', 'noopener noreferrer nofollow')
  })
  it('preserves the draft on failure and prevents duplicate submissions', async () => {
    let reject!: (reason: unknown) => void
    const submit = vi.fn(() => new Promise<void>((_, fail) => { reject = fail }))
    render(<CommunityComposer onSubmit={submit} />)
    fireEvent.change(screen.getByRole('textbox', { name: /内容/ }), { target: { value: '需要保留的草稿' } })
    fireEvent.click(screen.getByRole('button', { name: '发布' }))
    expect(screen.getByRole('button', { name: '发布中…' })).toBeDisabled()
    reject(new Error('network'))
    expect(await screen.findByText('操作失败，请稍后重试。')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /内容/ })).toHaveValue('需要保留的草稿')
    expect(submit).toHaveBeenCalledTimes(1)
  })
  it('replies with the same target and explicit reply id', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [comment], total: 1 })
    render(<MemoryRouter><CommentPanel target={{ system_key: 'Hg' }} /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: '回复' }))
    fireEvent.change(screen.getByRole('textbox', { name: /回复 #42/ }), { target: { value: '针对评论的回复' } })
    fireEvent.click(screen.getAllByRole('button', { name: '发布' })[1])
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/community/entries', { kind: 'comment', system_key: 'Hg', reply_to_id: 42, body: '针对评论的回复' }))
  })
  it('does not show composers when paper permission fails', async () => {
    vi.mocked(api.get).mockRejectedValue({ code: 'paper_forbidden', status: 403 })
    render(<MemoryRouter><CommentPanel target={{ paper_id: 7 }} /></MemoryRouter>)
    await screen.findByText('你目前无权访问这篇论文及其讨论。')
    expect(screen.queryByRole('button', { name: '发布' })).not.toBeInTheDocument()
  })
  it('deduplicates the rolling snapshot and stops polling when disabled', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [{ ...comment, kind: 'danmaku', body: '正在滚动' }], total: 1 })
    render(<MemoryRouter><DanmakuPanel target={{ system_key: 'Hg' }} /></MemoryRouter>)
    await screen.findByText('正在滚动')
    expect(screen.getAllByText('正在滚动')).toHaveLength(1)
    fireEvent.click(screen.getByRole('switch', { name: '显示弹幕' }))
    expect(screen.queryByTestId('danmaku-stage')).not.toBeInTheDocument()
    const requests = vi.mocked(api.get).mock.calls.length
    vi.useFakeTimers(); await vi.advanceTimersByTimeAsync(6000)
    expect(vi.mocked(api.get).mock.calls.length).toBe(requests)
  })
  it('queues overflow messages and fills the next free lane without losing or replaying entries', async () => {
    vi.useFakeTimers()
    const items = Array.from({ length: 7 }, (_, i) => ({ ...comment, id: 7 - i, kind: 'danmaku', body: `弹幕${7 - i}` }))
    vi.mocked(api.get).mockResolvedValue({ items, total: 7 })
    await act(async () => { render(<MemoryRouter><DanmakuPanel target={{ system_key: 'Hg' }} /></MemoryRouter>) })
    expect(screen.queryByText('弹幕7')).not.toBeInTheDocument()
    fireEvent.animationEnd(screen.getByText('弹幕1'))
    expect(screen.getByText('弹幕7')).toBeInTheDocument()
    expect(screen.queryByText('弹幕1')).not.toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.queryByText('弹幕1')).not.toBeInTheDocument()
    expect(screen.getAllByText('弹幕7')).toHaveLength(1)
  })
  it('removes hidden messages from both active lanes and the pending queue', async () => {
    vi.useFakeTimers()
    const items = Array.from({ length: 8 }, (_, i) => ({ ...comment, id: 8 - i, kind: 'danmaku', body: `弹幕${8 - i}` }))
    vi.mocked(api.get).mockResolvedValue({ items, total: 8 })
    await act(async () => { render(<MemoryRouter><DanmakuPanel target={{ system_key: 'Hg' }} /></MemoryRouter>) })
    vi.mocked(api.get).mockResolvedValue({ items: items.filter(item => ![1, 7].includes(item.id)), total: 6 })
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.queryByText('弹幕1')).not.toBeInTheDocument()
    expect(screen.queryByText('弹幕7')).not.toBeInTheDocument()
    expect(screen.getByText('弹幕8')).toBeInTheDocument()
  })
  it('does not replay finished messages after a temporary polling failure', async () => {
    vi.useFakeTimers()
    const result = { items: [{ ...comment, kind: 'danmaku', body: '只播放一次' }], total: 1 }
    vi.mocked(api.get).mockResolvedValue(result)
    await act(async () => { render(<MemoryRouter><DanmakuPanel target={{ system_key: 'Hg' }} /></MemoryRouter>) })
    fireEvent.animationEnd(screen.getByText('只播放一次'))
    vi.mocked(api.get).mockRejectedValueOnce(new Error('network'))
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.getByText('操作失败，请稍后重试。')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(screen.queryByText('只播放一次')).not.toBeInTheDocument()
    expect(screen.queryByText('操作失败，请稍后重试。')).not.toBeInTheDocument()
  })
})
