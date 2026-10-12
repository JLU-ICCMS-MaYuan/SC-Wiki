import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import RagPage from './RagPage'
import RagSourceDrawer from '../components/RagSourceDrawer'
import MarkdownMessage from '../components/MarkdownMessage'

const mocks = vi.hoisted(() => ({
  send: vi.fn(), post: vi.fn(), get: vi.fn(),
  activeId: '', userId: null as number | null, token: null as string | null,
  newConversation: vi.fn(), switchConversation: vi.fn(),
  messages: [] as Array<{ role: 'user' | 'assistant'; content: string }>,
}))

vi.mock('../lib/api', () => ({ api: { post: mocks.post, get: mocks.get } }))
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({
  user: mocks.userId === null ? null : { id: mocks.userId }, token: mocks.token,
}) }))

vi.mock('../lib/useStreamingChat', () => ({
  useStreamingChat: () => ({
    convs: [{ id: 'a', title: '会话 A' }, { id: 'b', title: '会话 B' }], activeId: mocks.activeId,
    messages: mocks.messages, loading: false, papers: {}, top10: [],
    ideas: [], reviews: [], statusLog: [], savedPapers: [],
    inspiration: { active: false, statusMessage: '' }, cloud: false,
    syncState: 'local', syncError: '', legacyCount: 0,
    newConversation: mocks.newConversation, switchConversation: mocks.switchConversation, deleteConversation: vi.fn(),
    importLegacy: vi.fn(), send: mocks.send,
  }),
}))

afterEach(() => {
  cleanup(); vi.resetAllMocks(); mocks.messages = []
  mocks.activeId = ''; mocks.userId = null; mocks.token = null
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
const polishButton = () => screen.getByRole('button', { name: '润色提示词' })
const draftInput = () => screen.getByRole('textbox', { name: '输入问题' }) as HTMLTextAreaElement
const result = (suggestion: string) => ({ ok: true, data: { suggestion } })

describe('RAG 对话入口', () => {
  it('默认没有固定证据栏，空草稿不能润色', () => {
    render(<RagPage />)
    expect(screen.queryByText('证据面板')).toBeNull()
    expect(screen.getByRole('button', { name: '润色提示词' })).toHaveProperty('disabled', true)
    expect(screen.getByPlaceholderText('输入问题')).toBeTruthy()
  })

  it('成功直接回填且不自动发送，一次撤销逐字恢复空格和换行', async () => {
    mocks.post.mockResolvedValue(result('请具体分析 LaH10 的 Tc。'))
    render(<RagPage />)
    const original = '  LaH10 Tc?\n '
    fireEvent.change(draftInput(), { target: { value: original } })
    fireEvent.click(polishButton())
    await waitFor(() => expect(draftInput().value).toBe('请具体分析 LaH10 的 Tc。'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mocks.send).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '撤销润色' }))
    expect(draftInput().value).toBe(original)
    expect(screen.queryByRole('button', { name: '撤销润色' })).toBeNull()
    expect(mocks.send).not.toHaveBeenCalled()
  })

  it('润色失败或等待期间编辑都保留当前草稿', async () => {
    let resolve: (value: unknown) => void = () => {}
    mocks.post.mockImplementationOnce(() => new Promise(done => { resolve = done }))
      .mockRejectedValueOnce(new Error('model unavailable'))
    render(<RagPage />)
    const input = screen.getByRole('textbox', { name: '输入问题' }) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'LaH10 200 GPa Tc?' } })
    fireEvent.click(screen.getByRole('button', { name: '润色提示词' }))
    fireEvent.change(input, { target: { value: '改过的问题' } })
    await act(async () => resolve(result('过期的润色')))
    await waitFor(() => expect(screen.getByRole('button', { name: '润色提示词' })).toHaveProperty('disabled', false))
    expect(screen.queryByText('过期的润色')).toBeNull()
    expect(input.value).toBe('改过的问题')
    fireEvent.click(screen.getByRole('button', { name: '润色提示词' }))
    await screen.findByText('润色失败，原问题已保留。')
    expect(input.value).toBe('改过的问题')
    expect(mocks.send).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('同一请求重复点击不重复调用，编辑后恢复原文也拒绝旧响应', async () => {
    const pending = deferred<ReturnType<typeof result>>()
    mocks.post.mockReturnValue(pending.promise)
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '问题' } })
    fireEvent.click(polishButton()); fireEvent.click(polishButton())
    expect(mocks.post).toHaveBeenCalledTimes(1)
    fireEvent.change(draftInput(), { target: { value: '修改' } })
    fireEvent.change(draftInput(), { target: { value: '问题' } })
    await act(async () => pending.resolve(result('旧结果')))
    expect(draftInput().value).toBe('问题')
  })

  it('旧请求结束不清除新请求的忙碌状态或显示旧错误', async () => {
    const old = deferred<ReturnType<typeof result>>()
    const next = deferred<ReturnType<typeof result>>()
    mocks.post.mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise)
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '旧问题' } })
    fireEvent.click(polishButton())
    fireEvent.change(draftInput(), { target: { value: '新问题' } })
    fireEvent.click(polishButton())
    await act(async () => old.reject(new Error('旧请求失败')))
    expect(polishButton()).toHaveProperty('disabled', true)
    expect(screen.queryByText('润色失败，原问题已保留。')).toBeNull()
    await act(async () => next.resolve(result('新结果')))
    expect(draftInput().value).toBe('新结果')
  })

  it.each(['编辑', '新请求', '发送', '新会话'])('%s 使已回填的撤销失效', async action => {
    mocks.post.mockResolvedValueOnce(result('新结果')).mockRejectedValueOnce(new Error('失败'))
    mocks.send.mockResolvedValue(true)
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '原文' } })
    fireEvent.click(polishButton())
    await screen.findByRole('button', { name: '撤销润色' })
    if (action === '编辑') fireEvent.change(draftInput(), { target: { value: '编辑后' } })
    if (action === '新请求') { fireEvent.click(polishButton()); await screen.findByText('润色失败，原问题已保留。') }
    if (action === '发送') await act(async () => fireEvent.click(screen.getByRole('button', { name: '发送问题' })))
    if (action === '新会话') fireEvent.click(screen.getByRole('button', { name: '新对话' }))
    expect(screen.queryByRole('button', { name: '撤销润色' })).toBeNull()
  })

  it.each(['新会话', '切回原会话', '账号', '卸载'])('%s 后旧结果及错误失效', async action => {
    const pending = deferred<ReturnType<typeof result>>()
    mocks.post.mockReturnValue(pending.promise)
    const view = render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '原文' } })
    fireEvent.click(polishButton())
    if (action === '新会话') fireEvent.click(screen.getByRole('button', { name: '新对话' }))
    if (action === '切回原会话') {
      fireEvent.click(screen.getByRole('button', { name: '会话 B' }))
      fireEvent.click(screen.getByRole('button', { name: '会话 A' }))
    }
    if (action === '账号') { mocks.userId = 2; mocks.token = 'new-session'; view.rerender(<RagPage />) }
    if (action === '卸载') view.unmount()
    await act(async () => pending.resolve(result('不该出现')))
    expect(screen.queryByDisplayValue('不该出现')).toBeNull()
    expect(screen.queryByRole('button', { name: '撤销润色' })).toBeNull()
  })

  it('主动发送并失败恢复时旧润色不能覆盖草稿', async () => {
    const pending = deferred<ReturnType<typeof result>>()
    mocks.post.mockReturnValue(pending.promise)
    mocks.send.mockResolvedValue(false)
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '原文' } })
    fireEvent.click(polishButton())
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '发送问题' })))
    expect(mocks.send).toHaveBeenCalledWith('原文', false)
    await act(async () => pending.resolve(result('旧润色')))
    expect(draftInput().value).toBe('原文')
  })

  it('会话 ID 或登录会话变化后迟到错误不会显示', async () => {
    const first = deferred<ReturnType<typeof result>>()
    const second = deferred<ReturnType<typeof result>>()
    mocks.post.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const view = render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '问题' } })
    fireEvent.click(polishButton())
    mocks.activeId = 'b'; view.rerender(<RagPage />)
    await act(async () => first.reject(new Error('旧会话错误')))
    expect(screen.queryByText('润色失败，原问题已保留。')).toBeNull()
    fireEvent.click(polishButton())
    mocks.token = 'renewed'; view.rerender(<RagPage />)
    await act(async () => second.reject(new Error('旧登录错误')))
    expect(screen.queryByText('润色失败，原问题已保留。')).toBeNull()
    expect(draftInput().value).toBe('问题')
  })

  it('超长输入可编辑，但不能润色或发送', () => {
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '𠮷'.repeat(1001) } })
    expect(screen.getByText('问题不能超过 1000 个字符。')).toBeTruthy()
    expect(polishButton()).toHaveProperty('disabled', true)
    fireEvent.keyDown(draftInput(), { key: 'Enter' })
    expect(mocks.send).not.toHaveBeenCalled()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('发送失败在新会话中不恢复旧草稿', async () => {
    const sending = deferred<boolean>()
    mocks.send.mockReturnValue(sending.promise)
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '旧草稿' } })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))
    fireEvent.click(screen.getByRole('button', { name: '新对话' }))
    await act(async () => sending.resolve(false))
    expect(draftInput().value).toBe('')
  })

  it.each(['', '空'.repeat(1001)])('无效成功响应仍保留当前输入', async suggestion => {
    mocks.post.mockResolvedValue(result(suggestion))
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: '原文' } })
    fireEvent.click(polishButton())
    await screen.findByText('润色失败，原问题已保留。')
    expect(draftInput().value).toBe('原文')
  })

  it('相同结果不制造撤销，完整补充平面字符按码点计数', async () => {
    const original = '𠮷'.repeat(1000)
    mocks.post.mockResolvedValue(result(original))
    render(<RagPage />)
    fireEvent.change(draftInput(), { target: { value: original } })
    fireEvent.click(polishButton())
    await waitFor(() => expect(polishButton()).toHaveProperty('disabled', false))
    expect(draftInput().value).toBe(original)
    expect(screen.queryByRole('button', { name: '撤销润色' })).toBeNull()
  })

  it('来源抽屉按需加载当前文献片段', async () => {
    mocks.get.mockImplementation((url: string) => Promise.resolve({ ok: true, data: url.endsWith('/fragments')
      ? [{ id: 9, section: '结果', page: 3, preview: '原文摘要' }]
      : url.endsWith('/fragments/9') ? { id: 9, section: '结果', content: '论文原文片段' }
        : { id: 1, title: 'LaH10 论文', year: 2020 } }))
    render(<RagSourceDrawer target={{ term: '[PID_1]', kind: 'paper', paper_id: 1 }} onClose={vi.fn()} />)
    expect(await screen.findByText('LaH10 论文')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /结果.*原文摘要/ }))
    await waitFor(() => expect(screen.getByText('论文原文片段')).toBeTruthy())
  })

  it('只有服务端确认的引文和关键词可点击', async () => {
    mocks.post.mockResolvedValue({ ok: true, data: [
      { term: '[PID_1]', kind: 'paper', paper_id: 1 },
      { term: '带隙', kind: 'definition', definition_id: 10 },
    ] })
    const open = vi.fn()
    render(<MarkdownMessage content="带隙见 [PID_1]，无来源词。" papers={{ '1': { title: '论文' } }}
      paperSeqMap={{ '1': 1 }} onSourceOpen={open} />)
    fireEvent.click(await screen.findByRole('button', { name: '带隙' }))
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ definition_id: 10 }), expect.anything())
    fireEvent.click(screen.getByRole('button', { name: '[1]' }))
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ paper_id: 1 }), expect.anything())
    expect(screen.queryByRole('button', { name: '无来源词' })).toBeNull()
  })

  it('关闭临时详情后焦点回到回答内来源', async () => {
    mocks.messages = [{ role: 'assistant', content: '见 [PID_1]' }]
    mocks.post.mockResolvedValue({ ok: true, data: [{ term: '[PID_1]', kind: 'paper', paper_id: 1 }] })
    mocks.get.mockImplementation((url: string) => Promise.resolve({ ok: true, data: url.endsWith('/fragments')
      ? [] : { id: 1, title: '论文详情' } }))
    render(<RagPage />)
    const source = await screen.findByRole('button', { name: '[1]' })
    fireEvent.click(source)
    await screen.findByText('论文详情')
    fireEvent.click(screen.getByRole('button', { name: '关闭详情' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: '[1]' })))
  })
})
