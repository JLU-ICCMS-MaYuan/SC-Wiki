import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import CommunityMarkdown from '../../frontend/src/components/community/CommunityMarkdown'
import CommunityComposer from '../../frontend/src/components/community/CommunityComposer'
import CommentPanel from '../../frontend/src/components/community/CommentPanel'
import PaperCommunity from '../../frontend/src/components/community/PaperCommunity'
import ModelAnswerCard from '../../frontend/src/components/community/ModelAnswerCard'
import EntryCard from '../../frontend/src/components/community/EntryCard'
import DiscussionPage from '../../frontend/src/pages/DiscussionPage'
import DiscussionAnswerPage from '../../frontend/src/pages/DiscussionAnswerPage'
import AnswerQueue from '../../frontend/src/components/community/AnswerQueue'
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
  it('历史问题详情可选择模型排队，已有任务运行时仍可加入', async () => {
    auth.user.role = 'superadmin'
    const question = { ...comment, kind: 'question', title: '问题详情', model_count: 0, response_count: 0 }
    vi.mocked(api.get).mockImplementation(async url => url === '/api/community/entries/42' ? question : url.endsWith('/models') ? { items: [{ key: 'a'.repeat(64), name: 'DeepSeek', model: 'deepseek' }] } : url.endsWith('/queue') ? { items: [{ id: 2, sequence: 1, model_name: 'OpenAI', model: 'gpt', state: 'running', error: '' }] } : { items: [], total: 0 })
    render(<MemoryRouter initialEntries={['/share/discussions/42']}><Routes><Route path="/share/discussions/:id" element={<DiscussionPage />} /></Routes></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: '生成答案 (1)' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/community/ai/questions/42/answers/batch', { request_id: expect.any(String), model_keys: ['a'.repeat(64)] }))
  })
  it('历史问题没有模型任务时使用不依赖新字段的排序', async () => {
    const question = { ...comment, kind: 'question', title: '迁移前的历史问题', generation_tasks: [], origin: '', revision: 0 }
    vi.mocked(api.get).mockImplementation(async url => url === '/api/community/entries/42' ? question : { items: [], total: 0 })
    render(<MemoryRouter initialEntries={['/share/discussions/42']}><Routes><Route path="/share/discussions/:id" element={<DiscussionPage />} /></Routes></MemoryRouter>)
    await screen.findByText('迁移前的历史问题')
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/community/entries?kind=answer&question_id=42&sort=latest&offset=0', expect.anything()))
    expect(vi.mocked(api.get).mock.calls.some(([url]) => url.includes('sort=models'))).toBe(false)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
  it('同模型卡片展示首答和补充，保留回应定位而不是另建卡片', () => {
    const entry = { ...comment, kind: 'answer', origin: 'ai', question_id: 7, model_name: 'DeepSeek', model: 'deepseek', turns: [
      { key: 'A42', id: null, body: '这是初始论点', sequence: 1, revision: 1, created_at: comment.created_at },
      { key: 'A42T1', id: 1, body: '补充不同角度并承认前述限制', sequence: 3, revision: 1, created_at: comment.created_at, replies: [{ key: 'A43', model_name: 'OpenAI', sequence: 2 }] },
    ] }
    render(<MemoryRouter><ModelAnswerCard entry={entry} reload={() => {}} /></MemoryRouter>)
    expect(screen.getAllByText('DeepSeek')).toHaveLength(1)
    expect(screen.getByText('初始回答')).toBeInTheDocument()
    expect(screen.getByText('补充回答')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'OpenAI #2' })).toHaveAttribute('href', '/share/discussions/7/answers/43#answer-A43')
    expect(screen.queryByRole('button', { name: '编辑' })).not.toBeInTheDocument()
  })
  it('行内多选保持勾选顺序，空选禁用，失败重试复用UUID', async () => {
    vi.mocked(api.get).mockImplementation(async url => url.endsWith('/models') ? { items: [{ key: 'a'.repeat(64), name: 'DeepSeek', model: 'd' }, { key: 'b'.repeat(64), name: 'OpenAI', model: 'gpt' }] } : { items: [] })
    vi.mocked(api.post).mockRejectedValueOnce({ code: 'queue_unavailable' }).mockResolvedValue({ items: [] })
    render(<MemoryRouter><AnswerQueue questionId={7} onChanged={() => {}} /></MemoryRouter>)
    await screen.findByRole('button', { name: '生成答案 (2)' })
    fireEvent.click(screen.getByRole('button', { name: 'DeepSeek' }))
    fireEvent.click(screen.getByRole('button', { name: 'OpenAI' }))
    expect(screen.getByRole('button', { name: '生成答案 (0)' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'OpenAI' }))
    fireEvent.click(screen.getByRole('button', { name: 'DeepSeek' }))
    fireEvent.click(screen.getByRole('button', { name: '生成答案 (2)' }))
    await screen.findByText('任务队列不可用，请稍后重试。')
    const first = vi.mocked(api.post).mock.calls[0][1]
    expect(first).toEqual({ request_id: expect.any(String), model_keys: ['b'.repeat(64), 'a'.repeat(64)] })
    fireEvent.click(screen.getByRole('button', { name: '生成答案 (2)' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.post).mock.calls[1][1]).toEqual(first)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('摘要点击进入独立答案页，直接路由包含完整首答和补充', async () => {
    const entry = { ...comment, question_id: 7, kind: 'answer', origin: 'ai', model_name: 'DeepSeek', model: 'deepseek', body: '摘要开头', turns: [
      { key: 'A42', id: null, body: '这是完整的首答', sequence: 1, revision: 1, created_at: comment.created_at },
      { key: 'A42T1', id: 1, body: '这是完整的补充', sequence: 2, revision: 1, created_at: comment.created_at },
    ] }
    vi.mocked(api.get).mockImplementation(async url => url === '/api/community/questions/7/answers/42' ? entry : { ...comment, id: 7, kind: 'question', title: '原问题' })
    render(<MemoryRouter initialEntries={['/summary']}><Routes><Route path="/summary" element={<ModelAnswerCard entry={entry} reload={() => {}} compact />} /><Route path="/share/discussions/:id/answers/:answerId" element={<DiscussionAnswerPage />} /></Routes></MemoryRouter>)
    expect(screen.queryByText('这是完整的补充')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: '查看 DeepSeek 的完整回答' }))
    await screen.findByText('这是完整的补充')
    expect(screen.getByText('这是完整的首答')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回问题' })).toHaveAttribute('href', '/share/discussions/7#entry-42')
  })
  it('独立答案无权访问时不显示内容', async () => {
    vi.mocked(api.get).mockRejectedValue({ code: 'content_unavailable', status: 404 })
    render(<MemoryRouter initialEntries={['/share/discussions/7/answers/42']}><Routes><Route path="/share/discussions/:id/answers/:answerId" element={<DiscussionAnswerPage />} /></Routes></MemoryRouter>)
    await screen.findByRole('alert')
    expect(screen.queryByText('初始回答')).not.toBeInTheDocument()
  })
  it('论文权限失败不显示历史内容或输入', async () => {
    vi.mocked(api.get).mockRejectedValue({ code: 'paper_forbidden', status: 403 })
    render(<MemoryRouter><CommentPanel target={{ paper_id: 7 }} /></MemoryRouter>)
    await screen.findByText('你目前无权访问这篇论文及其讨论。'); expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})
