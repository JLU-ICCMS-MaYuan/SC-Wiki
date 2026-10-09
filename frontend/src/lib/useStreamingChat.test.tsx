import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useStreamingChat } from './useStreamingChat'

const mocks = vi.hoisted(() => ({
  auth: { user: null as null | { id: number }, loading: false },
  list: vi.fn(), create: vi.fn(), get: vi.fn(), importLocal: vi.fn(), postStream: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({ useAuth: () => mocks.auth }))
vi.mock('./ragConversations', () => ({
  listCloudConversations: mocks.list,
  createCloudConversation: mocks.create,
  getCloudConversation: mocks.get,
  deleteCloudConversation: vi.fn(),
  importLocalConversation: mocks.importLocal,
}))
vi.mock('./api', () => ({ api: { postStream: mocks.postStream } }))

beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
    removeItem: (key: string) => { values.delete(key) },
    clear: () => { values.clear() },
  })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
  mocks.auth.user = null
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('RAG 会话状态', () => {
  it('登录和登出不会把账号历史写入访客本机历史', async () => {
    localStorage.setItem('rag_conversations', JSON.stringify([{ id: 'local-1', title: '本机会话',
      createdAt: 1, messages: [{ role: 'user', content: '本机问题' }, { role: 'assistant', content: '本机回答' }] }]))
    mocks.list.mockResolvedValue([{ id: 'cloud-1', title: '云端会话', created_at: '2026-10-09T00:00:00Z',
      updated_at: '2026-10-09T00:00:00Z', last_sequence: 0 }])
    mocks.get.mockResolvedValue({ id: 'cloud-1', title: '云端会话', created_at: '2026-10-09T00:00:00Z',
      updated_at: '2026-10-09T00:00:00Z', last_sequence: 0, turns: [] })
    const { result, rerender } = renderHook(() => useStreamingChat())
    await waitFor(() => expect(result.current.convs[0]?.id).toBe('local-1'))
    mocks.auth.user = { id: 1 }
    rerender()
    await waitFor(() => expect(result.current.convs[0]?.id).toBe('cloud-1'))
    expect(JSON.parse(localStorage.getItem('rag_conversations') || '[]')[0].id).toBe('local-1')
    mocks.auth.user = null
    rerender()
    await waitFor(() => expect(result.current.convs[0]?.id).toBe('local-1'))
  })

  it('登录后的提问仅发送会话标识，并显示服务端已完成答案', async () => {
    mocks.auth.user = { id: 1 }
    mocks.list.mockResolvedValue([])
    mocks.create.mockResolvedValue({ id: 'cloud-1', title: '新对话', created_at: '2026-10-09T00:00:00Z',
      updated_at: '2026-10-09T00:00:00Z', last_sequence: 0 })
    vi.stubGlobal('crypto', { randomUUID: () => '12345678-1234-1234-1234-123456789012' })
    const stream = 'event: token\ndata: "答"\n\nevent: done\ndata: {"answer":"答案","sequence":1,"citations":[]}\n\n'
    let read = false
    mocks.postStream.mockResolvedValue({ ok: true, body: { getReader: () => ({
      read: async () => read ? { done: true } : (read = true, { done: false, value: new TextEncoder().encode(stream) }),
    }) } })
    const { result } = renderHook(() => useStreamingChat())
    await waitFor(() => expect(result.current.syncState).toBe('saved'))
    let ok = false
    await act(async () => { ok = await result.current.send('研究问题') })
    expect(ok).toBe(true)
    expect(mocks.postStream.mock.calls[0][1]).toMatchObject({
      question: '研究问题', conversation_id: 'cloud-1', expected_last_sequence: 0,
    })
    expect(mocks.postStream.mock.calls[0][1]).not.toHaveProperty('history')
    expect(result.current.messages.at(-1)?.content).toBe('答案')
    expect(result.current.syncState).toBe('saved')
  })

  it('旧本地历史只在显式导入后上传且重复入口被隐藏', async () => {
    localStorage.setItem('rag_conversations', JSON.stringify([{ id: 'old-1', title: '旧会话',
      createdAt: 1, messages: [{ role: 'user', content: '旧问题' }, { role: 'assistant', content: '旧答案' }] }]))
    mocks.auth.user = { id: 1 }
    mocks.list.mockResolvedValue([])
    mocks.importLocal.mockResolvedValue({ id: 'cloud-1' })
    const { result } = renderHook(() => useStreamingChat())
    await waitFor(() => expect(result.current.syncState).toBe('saved'))
    expect(mocks.importLocal).not.toHaveBeenCalled()
    expect(result.current.legacyCount).toBe(1)
    await act(async () => { await result.current.importLegacy() })
    expect(mocks.importLocal).toHaveBeenCalledTimes(1)
    expect(result.current.legacyCount).toBe(0)
    expect(JSON.parse(localStorage.getItem('rag_conversations') || '[]')[0].id).toBe('old-1')
  })
})
