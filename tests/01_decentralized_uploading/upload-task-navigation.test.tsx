import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { AuthProvider } from '../../frontend/src/context/AuthContext'
import UploadTaskPage from '../../frontend/src/pages/UploadTaskPage'

// 隔离下层表单，任务地址和安全边界仍调用真实 api 客户端，不伪造任务页状态。
vi.mock('../../frontend/src/components/UploadParsingDetail', () => ({
  default: ({ taskId, onSubmitted }: { taskId: string; onSubmitted: (id: number) => void }) =>
    <div data-testid="task-editor">{taskId}<button onClick={() => onSubmitted(29)}>完成测试提交</button></div>,
}))

const user = { id: 7, role: 'user', email: 'test@example.com', username: 'tester', is_approved: true }
const a = 'a'.repeat(32)
const b = 'b'.repeat(32)
const task = (id: string) => ({ task_id: id, filename: `${id[0]}.pdf`, status: 'ready', stage: 'ready',
  stage_index: 5, stage_total: 5, processing_status: 'succeeded', completed_chunks: 6, total_chunks: 6 })
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const seed = () => {
  localStorage.setItem('auth_token', 'fixture')
  localStorage.setItem('auth_user', JSON.stringify(user))
  localStorage.setItem('scwiki_active_upload_task:7', b)
}
const SwitchTask = () => { const navigate = useNavigate(); return <button onClick={() => navigate(`/upload/tasks/${b}`)}>切换测试任务</button> }
const mount = () => render(<MemoryRouter initialEntries={[`/upload/tasks/${a}`]}><AuthProvider>
  <SwitchTask /><Routes><Route path="/upload/tasks/:taskId" element={<UploadTaskPage />} />
    <Route path="/papers/:id" element={<div>正式论文</div>} /></Routes>
</AuthProvider></MemoryRouter>)

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('上传任务详情地址', () => {
  it('地址任务优先于旧活动任务缓存，直达和重新挂载恢复同一任务', async () => {
    seed()
    const requests: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input); requests.push(url)
      return response(url === '/api/auth/me' ? { user } : url === `/api/upload-tasks/${a}` ? { ok: true, data: task(a) } : { ok: true })
    }))
    const first = mount()
    expect(await screen.findByText('a.pdf')).toBeVisible()
    expect(screen.getByTestId('task-editor')).toHaveTextContent(a)
    expect(screen.getByRole('link', { name: '返回上传记录' })).toHaveAttribute('href', '/upload')
    expect(screen.queryByLabelText('拖拽或选择论文文件')).not.toBeInTheDocument()
    expect(requests).not.toContain(`/api/upload-tasks/${b}`)
    first.unmount(); mount()
    expect(await screen.findByText('a.pdf')).toBeVisible()
  })

  it.each([401, 403, 404])('详情读取 %s 时没有旧表单，提供返回入口', async status => {
    seed()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => response(String(input) === '/api/auth/me'
      ? { user } : String(input).endsWith('/activity') ? { ok: true } : { detail: { message: '不可访问此任务' } },
      String(input).includes(`/api/upload-tasks/${a}`) && !String(input).endsWith('/activity') ? status : 200)))
    mount()
    expect(await screen.findByRole('alert')).toHaveTextContent(status === 404 ? '该解析任务已过期或被清理' : '不可访问此任务')
    expect(screen.queryByTestId('task-editor')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回上传记录' })).toBeVisible()
  })

  it('切换任务后迟到的旧响应不能覆盖新任务', async () => {
    seed()
    let finishA: ((value: Response) => void) | undefined
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === `/api/upload-tasks/${a}`) return new Promise<Response>(resolve => { finishA = resolve })
      return Promise.resolve(response(url === '/api/auth/me' ? { user } : url === `/api/upload-tasks/${b}` ? { ok: true, data: task(b) } : { ok: true }))
    }))
    mount()
    await waitFor(() => expect(finishA).toBeDefined())
    fireEvent.click(screen.getByRole('button', { name: '切换测试任务' }))
    expect(await screen.findByText('b.pdf')).toBeVisible()
    finishA!(response({ ok: true, data: task(a) }))
    await waitFor(() => expect(screen.getByTestId('task-editor')).toHaveTextContent(b))
    expect(screen.queryByText('a.pdf')).not.toBeInTheDocument()
  })

  it('原有正式提交回调仍进入正式论文页面', async () => {
    seed()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => response(String(input) === '/api/auth/me' ? { user }
      : String(input) === `/api/upload-tasks/${a}` ? { ok: true, data: task(a) } : { ok: true })))
    mount()
    fireEvent.click(await screen.findByRole('button', { name: '完成测试提交' }))
    expect(await screen.findByText('正式论文')).toBeVisible()
  })
})
