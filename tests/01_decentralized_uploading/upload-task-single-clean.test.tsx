import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import UploadTaskCenter from '../../frontend/src/components/UploadTaskCenter'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

const failedTask = {
  task_id: 'a'.repeat(32),
  filename: '失败任务.pdf',
  status: 'failed',
  stage: 'failed',
  completed_chunks: 1,
  total_chunks: 2,
  files: [],
}

const renderCenter = () =>
  render(
    <LanguageProvider>
      <UploadTaskCenter onToggle={vi.fn()} />
    </LanguageProvider>,
  )

const stubFetch = (handler: (url: string, init?: RequestInit) => Response | undefined) =>
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const handled = handler(String(input), init)
    if (handled) return handled
    return new Response(JSON.stringify({ ok: true }), { status: 200 })
  }))

describe('上传解析记录单条清理', () => {
  it('失败记录显示清理按钮，点击后调用单条删除接口并刷新列表', async () => {
    const deletes: string[] = []
    stubFetch((url, init) => {
      if (url === '/api/upload-tasks') {
        return new Response(JSON.stringify({ ok: true, data: deletes.length ? [] : [failedTask] }), { status: 200 })
      }
      if (url === `/api/upload-tasks/${failedTask.task_id}` && init?.method === 'DELETE') {
        deletes.push(url)
        return new Response(JSON.stringify({ ok: true }), { status: 200 })
      }
      return undefined
    })
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByText('清理'))
    await waitFor(() => expect(deletes).toHaveLength(1))
    await waitFor(() => expect(screen.queryByText('失败任务.pdf')).not.toBeInTheDocument())
  })

  it('清理被后端拒绝时展示失败原因，而不是静默失败', async () => {
    stubFetch((url, init) => {
      if (url === '/api/upload-tasks') {
        return new Response(JSON.stringify({ ok: true, data: [failedTask] }), { status: 200 })
      }
      if (init?.method === 'DELETE') {
        return new Response(JSON.stringify({
          detail: { code: 'UPLOAD_TASK_PERSISTED', message: '任务已经生成正式论文，不能删除文件' },
        }), { status: 409 })
      }
      return undefined
    })
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByText('清理'))
    expect(await screen.findByText('任务已经生成正式论文，不能删除文件')).toBeInTheDocument()
  })
})
