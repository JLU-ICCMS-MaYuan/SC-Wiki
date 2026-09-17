import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import CommunityMarkdown from '../../frontend/src/components/community/CommunityMarkdown'
import CommunityComposer from '../../frontend/src/components/community/CommunityComposer'
import CommentPanel from '../../frontend/src/components/community/CommentPanel'
import PaperCommunity from '../../frontend/src/components/community/PaperCommunity'
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
  it('uses one comment composer on paper details and keeps the system link', async () => {
    render(<MemoryRouter><PaperCommunity paper={{ id: 7, chemical_systems: [{ system_key: 'Hg' }] }} /></MemoryRouter>)
    const composer = await screen.findByRole('textbox', { name: /评论/ })
    expect(screen.getAllByRole('textbox')).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Hg 体系讨论' })).toHaveAttribute('href', '/systems/Hg')
    expect(screen.queryByRole('switch', { name: '显示弹幕' })).not.toBeInTheDocument()
    fireEvent.change(composer, { target: { value: '论文评论继续可用' } })
    fireEvent.click(screen.getByRole('button', { name: '发布' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/community/entries', { kind: 'comment', paper_id: 7, body: '论文评论继续可用' }))
    expect(vi.mocked(api.get).mock.calls.every(([url]) => !url.includes('danmaku'))).toBe(true)
  })
})
