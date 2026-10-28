import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'
import { startEvidencePreparation } from '../../frontend/src/lib/evidenceProgress'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
const done = vi.fn()
let flow: ReturnType<typeof useEvidenceWorkflow>
function Harness({ target = 'upload' }: { target?: 'upload' | 'paper' | 'revision' }) {
  flow = useEvidenceWorkflow()
  return <><button onClick={() => void flow.gate({ target, target_id: 'test' }).then(done)}>提交</button>{flow.dialog}</>
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const tick = (ms = 1000) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const start = () => act(async () => { fireEvent.click(screen.getByText('提交')) })
const percent = (value: number) => expect(screen.getByRole('progressbar', { name: '原文核对进度' })).toHaveAttribute('aria-valuenow', String(value))
beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  vi.mocked(api.del).mockResolvedValue({})
})
afterEach(() => { cleanup(); vi.useRealTimers() })

it.each(['upload', 'paper', 'revision'] as const)('%s 显示真实准备步骤、2/5组50%、整理95%及最终100%', async target => {
  const request = deferred<any>()
  let preparation = 0
  let job: any = { id: 'job', status: 'queued' }
  vi.mocked(api.post).mockReturnValue(request.promise)
  vi.mocked(api.get).mockImplementation(async path => path.includes('/preparations/') ? { percent: preparation, cancelled: false } : job)
  render(<Harness target={target} />)
  await start()
  percent(0)
  preparation = 5
  await tick(); percent(5)
  expect(screen.getByRole('status')).toHaveTextContent('正在准备来源')
  preparation = 10
  await tick(); percent(10)
  expect(screen.getByRole('status')).toHaveTextContent('正在准备核对任务')
  await act(async () => request.resolve(job))
  percent(20)
  await tick(3000); percent(20)
  expect(screen.getByText('已等待 0 分 5 秒')).toBeInTheDocument()
  job = { id: 'job', status: 'running', total_batches: 5, completed_batches: 2, current_batch: 3 }
  await tick(); percent(50)
  expect(screen.getByText('已核对 2/5 组原文 · 50%')).toBeInTheDocument()
  job = { ...job, completed_batches: 1 }
  await tick(); percent(50) // 迟到计数不使同次流程倒退。
  job = { ...job, completed_batches: 5 }
  await tick(); percent(95)
  expect(done).not.toHaveBeenCalled()
  expect(screen.getByRole('status')).toHaveTextContent('正在整理核对结果并检查版本')
  job = { ...job, status: 'completed', version: 'v1', records: [] }
  await tick(); percent(100)
  expect(done).not.toHaveBeenCalled()
  await tick(400)
  expect(done).toHaveBeenCalledWith({ evidence_job_id: 'job', expected_evidence_version: 'v1', evidence_resolutions: {} })
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})

it('取消未返回的准备立即结束等待，新请求不被旧响应关闭或覆盖', async () => {
  const first = deferred<any>(), second = deferred<any>()
  vi.mocked(api.post).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  vi.mocked(api.get).mockResolvedValue({ percent: 5, cancelled: false })
  render(<Harness />)
  await start(); await tick(); percent(5)
  await act(async () => fireEvent.click(screen.getByText('取消')))
  expect(done).toHaveBeenCalledWith(null)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  await start(); percent(0)
  await act(async () => first.resolve({ id: 'late', status: 'queued' }))
  expect(api.del).toHaveBeenCalledWith('/api/rag/evidence/jobs/late')
  percent(0)
  await tick(); percent(5)
  await act(async () => second.reject(new Error('来源读取失败')))
  expect(screen.getByText('来源读取失败')).toBeInTheDocument()
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})

it.each(['failed', 'cancelled', 'stale'])('%s 不显示100%，取消不会继续提交', async status => {
  vi.mocked(api.post).mockResolvedValue({ id: 'job', status: 'queued' })
  vi.mocked(api.get).mockImplementation(async () => {
    if (status === 'stale') throw new Error('内容已变化')
    return { id: 'job', status, error: { message: '核对未完成' } } as never
  })
  render(<Harness />)
  await start(); percent(20)
  await tick()
  expect(done).toHaveBeenCalledWith(null)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  expect(screen.queryByText('本次核对已完成')).not.toBeInTheDocument()
})

it('准备进度查询失败保持原值，主请求失败才结束等待；重试从0开始', async () => {
  const first = deferred<any>(), second = deferred<any>()
  vi.mocked(api.post).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  vi.mocked(api.get).mockResolvedValueOnce({ percent: 10, cancelled: false }).mockRejectedValue(new Error('网络错误'))
  render(<Harness />)
  await start(); await tick(); percent(10)
  await tick(3000); percent(10)
  await act(async () => first.reject(new Error('来源准备失败')))
  expect(screen.getByText('来源准备失败')).toBeInTheDocument()
  await start(); percent(0)
  await act(async () => second.resolve({ status: 'completed', records: [], version: 'v2' }))
  percent(100)
  await tick(400)
  expect(done).toHaveBeenLastCalledWith(expect.objectContaining({ expected_evidence_version: 'v2' }))
})

it('程序检查不通过不显示流程完成', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'completed', program_issues: [{ field: 'paper.title', message: '缺少标题' }] })
  render(<Harness />)
  await start()
  expect(screen.getByText('程序检查：缺少标题')).toBeInTheDocument()
  expect(done).toHaveBeenCalledWith(null)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})

it('取消卡住的任务状态读取立即结束，保留取消语义而不误报超时', async () => {
  vi.mocked(api.post).mockResolvedValue({ id: 'job', status: 'queued' })
  vi.mocked(api.get).mockImplementation((_path, init) => new Promise((_, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }))
  render(<Harness />)
  await start(); await tick(); percent(20)
  await act(async () => fireEvent.click(screen.getByText('取消')))
  expect(done).toHaveBeenCalledWith(null)
  expect(api.del).toHaveBeenCalledWith('/api/rag/evidence/jobs/job')
  expect(screen.queryByText(/后台核对等待超时/)).not.toBeInTheDocument()
})

it('准备超时写取消墓碑并清理迟到任务，查询不重叠', async () => {
  const request = deferred<any>(), poll = deferred<any>()
  vi.mocked(api.post).mockReturnValue(request.promise)
  vi.mocked(api.get).mockReturnValue(poll.promise)
  const progress = vi.fn()
  const preparation = startEvidencePreparation('/api/rag/evidence/jobs', {}, progress)
  const error = preparation.result.catch(e => e)
  await tick(1800 * 1000)
  expect((await error).code).toBe('evidence_preparation_timeout')
  expect(api.get).toHaveBeenCalledTimes(1)
  expect(api.del).toHaveBeenCalledWith(expect.stringContaining('/preparations/'))
  await act(async () => { request.resolve({ id: 'late', status: 'queued' }); poll.resolve({ percent: 10 }) })
  expect(api.del).toHaveBeenCalledWith('/api/rag/evidence/jobs/late')
  expect(progress).not.toHaveBeenCalled()
})
