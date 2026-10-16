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

const record = (id: string, filename: string, status: string) => ({
  task_id: id,
  filename,
  status,
  stage: status,
  completed_chunks: 0,
  total_chunks: 0,
  files: [],
})

const failedTask = record('a'.repeat(32), '失败任务.pdf', 'failed')
const cancelledTask = record('b'.repeat(32), '取消任务.pdf', 'cancelled')

const renderCenter = () =>
  render(
    <LanguageProvider>
      <UploadTaskCenter />
    </LanguageProvider>,
  )

const stubList = () =>
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/api/upload-tasks') {
      return new Response(JSON.stringify({ ok: true, data: [failedTask, cancelledTask] }), { status: 200 })
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 })
  }))

describe('上传解析记录批量删除', () => {
  it('未选中时不显示批量删除按钮', async () => {
    stubList()
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())
    expect(screen.queryByText('批量删除')).not.toBeInTheDocument()
  })

  it('勾选记录后显示计数与批量删除按钮，确认后调用批量接口并刷新列表', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const posts: { url: string; body: unknown }[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/upload-tasks') {
        return new Response(JSON.stringify({ ok: true, data: [failedTask, cancelledTask] }), { status: 200 })
      }
      if (url === '/api/upload-tasks/batch-delete') {
        posts.push({ url, body: JSON.parse(String(init?.body)) })
        return new Response(JSON.stringify({
          ok: true,
          deleted: [{ task_id: failedTask.task_id }],
          failed: [],
        }), { status: 200 })
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    }))
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('checkbox', { name: '选择 失败任务.pdf 的解析记录' }))
    expect(screen.getByText('已选 1 条')).toBeInTheDocument()

    fireEvent.click(screen.getByText('批量删除'))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0].body).toEqual({ task_ids: [failedTask.task_id] })
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('1 条'))
    expect(await screen.findByText('已删除 1 条解析记录')).toBeInTheDocument()
  })

  it('全选后一次删除全部选中记录，部分失败时展示原因', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/upload-tasks') {
        return new Response(JSON.stringify({ ok: true, data: [failedTask, cancelledTask] }), { status: 200 })
      }
      if (url === '/api/upload-tasks/batch-delete') {
        return new Response(JSON.stringify({
          ok: true,
          deleted: [{ task_id: failedTask.task_id }],
          failed: [{ task_id: cancelledTask.task_id, reason: '任务正被其他请求处理，请稍后重试' }],
        }), { status: 200 })
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    }))
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('checkbox', { name: '全选' }))
    expect(screen.getByText('已选 2 条')).toBeInTheDocument()

    fireEvent.click(screen.getByText('批量删除'))
    expect(await screen.findByText(/部分失败：任务正被其他请求处理/)).toBeInTheDocument()
  })

  it('取消确认弹窗时不发起删除请求', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const batchPosts: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/upload-tasks') {
        return new Response(JSON.stringify({ ok: true, data: [failedTask, cancelledTask] }), { status: 200 })
      }
      if (url === '/api/upload-tasks/batch-delete') {
        batchPosts.push(JSON.parse(String(init?.body)))
        return new Response(JSON.stringify({ ok: true, deleted: [], failed: [] }), { status: 200 })
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    }))
    renderCenter()
    await waitFor(() => expect(screen.getByText('失败任务.pdf')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('checkbox', { name: '选择 失败任务.pdf 的解析记录' }))
    fireEvent.click(screen.getByText('批量删除'))

    await waitFor(() => expect(confirm).toHaveBeenCalled())
    expect(batchPosts).toHaveLength(0)
  })
})
