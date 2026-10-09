import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import RagPage from './RagPage'
import RagSourceDrawer from '../components/RagSourceDrawer'
import MarkdownMessage from '../components/MarkdownMessage'

const mocks = vi.hoisted(() => ({
  send: vi.fn(), post: vi.fn(), get: vi.fn(),
  messages: [] as Array<{ role: 'user' | 'assistant'; content: string }>,
}))

vi.mock('../lib/api', () => ({ api: { post: mocks.post, get: mocks.get } }))

vi.mock('../lib/useStreamingChat', () => ({
  useStreamingChat: () => ({
    convs: [], activeId: '', messages: mocks.messages, loading: false, papers: {}, top10: [],
    ideas: [], reviews: [], statusLog: [], savedPapers: [],
    inspiration: { active: false, statusMessage: '' }, cloud: false,
    syncState: 'local', syncError: '', legacyCount: 0,
    newConversation: vi.fn(), switchConversation: vi.fn(), deleteConversation: vi.fn(),
    importLegacy: vi.fn(), send: mocks.send,
  }),
}))

afterEach(() => { cleanup(); vi.clearAllMocks(); mocks.messages = [] })

describe('RAG 对话入口', () => {
  it('默认没有固定证据栏，空草稿不能润色', () => {
    render(<RagPage />)
    expect(screen.queryByText('证据面板')).toBeNull()
    expect(screen.getByRole('button', { name: '润色提示词' })).toHaveProperty('disabled', true)
    expect(screen.getByPlaceholderText('输入问题')).toBeTruthy()
  })

  it('润色可预览和取消，接受后仍不自动发送', async () => {
    mocks.post.mockResolvedValue({ ok: true, data: { suggestion: '请具体分析 LaH10 的 Tc。' } })
    render(<RagPage />)
    const input = screen.getByRole('textbox', { name: '输入问题' }) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'LaH10 Tc?' } })
    fireEvent.click(screen.getByRole('button', { name: '润色提示词' }))
    expect(await screen.findByText('请具体分析 LaH10 的 Tc。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(input.value).toBe('LaH10 Tc?')
    expect(mocks.send).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: '润色提示词' }))
    await screen.findByText('请具体分析 LaH10 的 Tc。')
    fireEvent.click(screen.getByRole('button', { name: '采用润色结果' }))
    expect(input.value).toBe('请具体分析 LaH10 的 Tc。')
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
    resolve({ ok: true, data: { suggestion: '过期的润色' } })
    await waitFor(() => expect(screen.getByRole('button', { name: '润色提示词' })).toHaveProperty('disabled', false))
    expect(screen.queryByText('过期的润色')).toBeNull()
    expect(input.value).toBe('改过的问题')
    fireEvent.click(screen.getByRole('button', { name: '润色提示词' }))
    await screen.findByText('润色失败，原问题已保留。')
    expect(input.value).toBe('改过的问题')
    expect(mocks.send).not.toHaveBeenCalled()
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
