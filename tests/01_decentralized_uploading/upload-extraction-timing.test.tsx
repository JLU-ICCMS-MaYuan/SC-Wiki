import React from 'react'
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import UploadTaskCenter from '../../frontend/src/components/UploadTaskCenter'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'

const start = 1800000000
const task = (status = 'extracting', timing: unknown = {
  elapsed_seconds: 0, started_at: start, running_since: start, finished_at: null,
}) => ({ task_id: 'a'.repeat(32), filename: 'paper.pdf', status, stage: status,
  stage_index: 2, stage_total: 5, processing_status: 'processing',
  completed_chunks: 0, total_chunks: 0, extraction_timing: timing })
const response = (data: unknown) => new Response(JSON.stringify({ ok: true, data }), { status: 200 })
const mount = async () => {
  let view!: ReturnType<typeof render>
  await act(async () => { view = render(<LanguageProvider><UploadTaskCenter /></LanguageProvider>) })
  return view
}
const advance = async (seconds: number) => act(async () => { await vi.advanceTimersByTimeAsync(seconds * 1000) })

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime((start + 205) * 1000) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear() })

describe('上传记录提取用时', () => {
  it('按秒显示，自动读到终态后固定，重开仍恢复同一结果', async () => {
    let current = task()
    const fetcher = vi.fn(async () => response([current]))
    vi.stubGlobal('fetch', fetcher)
    let view = await mount()
    expect(screen.getByText('提取内容用时：3 分 25 秒')).toBeInTheDocument()
    await advance(1)
    expect(screen.getByText('提取内容用时：3 分 26 秒')).toBeInTheDocument()
    current = task('ready', { elapsed_seconds: 207, started_at: start, running_since: null, finished_at: start + 207 })
    await advance(2)
    expect(screen.getByText('提取内容用时：3 分 27 秒')).toBeInTheDocument()
    const calls = fetcher.mock.calls.length
    await advance(15)
    expect(fetcher).toHaveBeenCalledTimes(calls)
    expect(screen.getByText('提取内容用时：3 分 27 秒')).toBeInTheDocument()
    view.unmount()
    view = await mount()
    expect(screen.getByText('提取内容用时：3 分 27 秒')).toBeInTheDocument()
  })

  it('等待角色确认时暂停，后台恢复后只累计新运行区间', async () => {
    let current = task('needs_role_review', { elapsed_seconds: 30, started_at: start, running_since: null, finished_at: null })
    vi.stubGlobal('fetch', vi.fn(async () => response([current])))
    await mount()
    await advance(6)
    expect(screen.getByText('提取内容用时：0 分 30 秒')).toBeInTheDocument()
    current = task('extracting', { elapsed_seconds: 30, started_at: start, running_since: start + 211, finished_at: null })
    await advance(3)
    expect(screen.getByText('提取内容用时：0 分 33 秒')).toBeInTheDocument()
  })

  it('失败重试先显示尚未开始，再从新一轮计时', async () => {
    let current = task('failed', { elapsed_seconds: 100, started_at: start, running_since: null, finished_at: start + 100 })
    vi.stubGlobal('fetch', vi.fn(async () => response([current])))
    await mount()
    current = task('queued', { elapsed_seconds: 0, started_at: null, running_since: null, finished_at: null })
    await act(async () => { fireEvent.focus(window) })
    expect(screen.getByText('提取内容用时：尚未开始')).toBeInTheDocument()
    current = task('extracting', { elapsed_seconds: 0, started_at: start + 205, running_since: start + 205, finished_at: null })
    await advance(3)
    expect(screen.getByText('提取内容用时：0 分 3 秒')).toBeInTheDocument()
  })

  it.each([undefined, null, {}, { elapsed_seconds: -1, started_at: start, running_since: null, finished_at: start + 1 },
    { elapsed_seconds: 12, started_at: null, running_since: start, finished_at: null }])('缺失或损坏记录不编造用时：%s', async timing => {
    vi.stubGlobal('fetch', vi.fn(async () => response([{ ...task('ready'), extraction_timing: timing }])))
    await mount()
    expect(screen.getByText('提取内容用时：未记录')).toBeInTheDocument()
  })

  it('采用最新请求结果，迟到的运行中响应不覆盖终态', async () => {
    let resolveOld!: (value: Response) => void
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response([task()]))
      .mockImplementationOnce(() => new Promise<Response>(resolve => { resolveOld = resolve }))
      .mockResolvedValueOnce(response([task('ready', { elapsed_seconds: 207, started_at: start, running_since: null, finished_at: start + 207 })]))
    vi.stubGlobal('fetch', fetcher)
    await mount()
    await advance(3)
    await act(async () => { fireEvent.focus(window) })
    await act(async () => { resolveOld(response([task()])) })
    await advance(5)
    expect(screen.getByText('提取内容用时：3 分 27 秒')).toBeInTheDocument()
  })

  it('英文显示且保留文件链接与选择操作', async () => {
    localStorage.setItem('sc-wiki.language', 'en')
    vi.stubGlobal('fetch', vi.fn(async () => response([task()])))
    await mount()
    expect(screen.getByText('Extraction time: 3m 25s')).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('target', '_blank')
    fireEvent.click(screen.getAllByRole('checkbox')[1])
    expect(screen.getAllByRole('checkbox')[1]).toBeChecked()
  })
})
