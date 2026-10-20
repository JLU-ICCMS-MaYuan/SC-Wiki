import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import CommunityMarkdown from '../../frontend/src/components/community/CommunityMarkdown'
import CommunityComposer from '../../frontend/src/components/community/CommunityComposer'
import CommentPanel from '../../frontend/src/components/community/CommentPanel'
import PaperCommunity from '../../frontend/src/components/community/PaperCommunity'
import EntryCard from '../../frontend/src/components/community/EntryCard'
import DiscussionPage from '../../frontend/src/pages/DiscussionPage'
import { api } from '../../frontend/src/lib/api'

const auth = vi.hoisted(() => ({ user: { id: 1, username: 'alice', role: 'user', is_email_verified: true } as any, token: 'test' }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => auth, getStoredToken: () => auth.token }))
vi.mock('../../frontend/src/components/AuthDialog', () => ({ default: () => null }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(), put: vi.fn() } }))
const comment: any = { id: 42, kind: 'comment', body: '已有评论', title: '', status: 'visible', origin: 'human', author: { username: 'bob' }, parent_id: null, reply_to_id: null, can_reply: false, can_edit: false, can_delete: false, created_at: '2026-09-17T00:00:00Z', url: '/systems/Hg', revision: 1 }
beforeEach(() => { vi.clearAllMocks(); auth.user = { id: 1, username: 'alice', role: 'user', is_email_verified: true }; window.history.replaceState(null, '', '/'); vi.mocked(api.get).mockResolvedValue({ items: [], total: 0 }); vi.mocked(api.post).mockResolvedValue({ id: 'batch', question_id: null, state: 'queued', tasks: [] }) })
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('只读社区与多模型问答', () => {
  it('保留数学与安全 Markdown 渲染', () => {
    const { container } = render(<CommunityMarkdown content={'**结论** $T_c$\n\n<img src="https://tracker.test/x" onerror="alert(1)">\n\n![remote](https://tracker.test/x) [danger](javascript:alert%281%29) [paper](https://doi.org/example)'} />)
    expect(screen.getByText('结论').tagName).toBe('STRONG'); expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('img,script')).toBeNull(); expect(screen.getByText('danger')).not.toHaveAttribute('href')
  })
  it.each(['user', 'admin', 'superadmin'])('所有身份的论文与体系评论均只读：%s', async role => {
    auth.user.role = role; vi.mocked(api.get).mockResolvedValue({ items: [comment], total: 1 })
    render(<MemoryRouter><PaperCommunity paper={{ id: 7, chemical_systems: [{ system_key: 'Hg' }] }} /></MemoryRouter>)
    await screen.findByText('已有评论'); expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '回复' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '举报' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Hg 体系讨论' })).toHaveAttribute('href', '/systems/Hg')
    expect(api.post).not.toHaveBeenCalled()
  })
  it.each(['user', 'admin', null])('非超级管理员没有提问按钮：%s', async role => {
    auth.user = role ? { ...auth.user, role } : null
    render(<MemoryRouter><DiscussionPage /></MemoryRouter>)
    await screen.findByText('暂无内容。'); expect(screen.queryByRole('button', { name: '发起问题' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'AI 随机提问' })).not.toBeInTheDocument()
    expect(vi.mocked(api.get).mock.calls.some(([url]) => url.includes('/ai/'))).toBe(false)
  })
  it('超级管理员点击一次只创建一个随机问题任务，不发送个人模型配置作为任务数据', async () => {
    auth.user.role = 'superadmin'
    render(<MemoryRouter><DiscussionPage /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'AI 随机提问' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    expect(api.post).toHaveBeenCalledWith('/api/community/ai/questions/generate', { request_id: expect.any(String) })
  })
  it('失败保留草稿并抑制重复提交', async () => {
    auth.user.role = 'superadmin'
    let reject!: (reason: unknown) => void
    const submit = vi.fn(() => new Promise<void>((_, fail) => { reject = fail }))
    render(<CommunityComposer question onSubmit={submit} />)
    fireEvent.change(screen.getByLabelText(/问题标题/), { target: { value: '超导问题' } })
    fireEvent.click(screen.getByRole('button', { name: '发布' }))
    expect(screen.getByRole('button', { name: '发布中…' })).toBeDisabled()
    reject({ code: 'queue_unavailable' })
    await screen.findByText('任务队列不可用，请稍后重试。')
    expect(screen.getByLabelText(/问题标题/)).toHaveValue('超导问题'); expect(submit).toHaveBeenCalledTimes(1)
  })
  it('AI 作者、人工修订和来源显示明确，普通用户没有投票或编辑', () => {
    render(<MemoryRouter><EntryCard entry={{ ...comment, kind: 'answer', origin: 'ai', author: null, body: '模型答案 [S1]', model_name: '模型一', model: 'm1', human_edited: true, citations: [{ id: 'S1', paper_id: 9, paper_revision: 1, title: '来源论文' }], can_edit: true }} reload={() => {}} /></MemoryRouter>)
    expect(screen.getByText('AI 生成，超级管理员修订')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '[S1] 来源论文' })).toHaveAttribute('href', '/papers/9')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
  it('公开详情展示各模型状态，用户无法触发重生成', async () => {
    const question = { ...comment, kind: 'question', title: '多模型问题', generation_tasks: [{ id: 1, model_name: '模型一', model: 'm1', state: 'failed', error: 'generation_failed' }, { id: 2, model_name: '模型二', model: 'm2', state: 'succeeded' }] }
    vi.mocked(api.get).mockImplementation(async url => url === '/api/community/entries/42' ? question : { items: [], total: 0 })
    render(<MemoryRouter initialEntries={['/share/discussions/42']}><Routes><Route path="/share/discussions/:id" element={<DiscussionPage />} /></Routes></MemoryRouter>)
    await screen.findByText('模型一 · m1'); expect(screen.getByText('生成失败')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重新生成' })).not.toBeInTheDocument()
  })
  it('论文权限失败不显示历史内容或输入', async () => {
    vi.mocked(api.get).mockRejectedValue({ code: 'paper_forbidden', status: 403 })
    render(<MemoryRouter><CommentPanel target={{ paper_id: 7 }} /></MemoryRouter>)
    await screen.findByText('你目前无权访问这篇论文及其讨论。'); expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})
