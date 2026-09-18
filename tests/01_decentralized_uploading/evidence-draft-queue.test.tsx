import { afterEach, expect, it, vi } from 'vitest'
import { createEvidenceDraftQueue } from '../../frontend/src/lib/evidenceDraftQueue'

afterEach(() => vi.useRealTimers())

it('连续输入合并为最新操作，保存失败暂停，显式重试提交最新输入', async () => {
  vi.useFakeTimers()
  const notify = vi.fn(), save = vi.fn().mockRejectedValueOnce(new Error('网络中断')).mockResolvedValue(undefined)
  const queue = createEvidenceDraftQueue(notify)
  for (const value of ['根', '根据', '根据物理定义']) queue.enqueue('field', () => save(value))
  await vi.advanceTimersByTimeAsync(500)
  expect(save).toHaveBeenCalledTimes(1)
  expect(save).toHaveBeenLastCalledWith('根据物理定义')
  for (const value of ['新的依据', '完整的新依据']) queue.enqueue('field', () => save(value))
  await vi.advanceTimersByTimeAsync(5000)
  expect(save).toHaveBeenCalledTimes(1)
  expect(notify.mock.calls.filter(([state]) => state.error)).toHaveLength(1)
  await queue.retry()
  expect(save).toHaveBeenCalledTimes(2)
  expect(save).toHaveBeenLastCalledWith('完整的新依据')
  expect(queue.hasPending()).toBe(false)
})

it('关闭或完成时刷新全部字段；在途请求后只发送最新值', async () => {
  let release!: () => void
  const save = vi.fn().mockImplementationOnce(() => new Promise<void>(resolve => { release = resolve })).mockResolvedValue(undefined)
  const queue = createEvidenceDraftQueue(() => {})
  queue.enqueue('a', () => save('a1'))
  const flush = queue.flush()
  queue.enqueue('a', () => save('a2'))
  queue.enqueue('a', () => save('a3'))
  queue.enqueue('b', () => save('b1'))
  release()
  await flush
  expect(save.mock.calls).toEqual([['a1'], ['a3'], ['b1']])
})

it('已丢弃旧版本请求的迟到失败不会阻塞下一次保存', async () => {
  let reject!: (error:Error) => void
  const notify = vi.fn(), save = vi.fn().mockResolvedValue(undefined)
  const queue = createEvidenceDraftQueue(notify)
  queue.enqueue('old', () => new Promise((_, fail) => {reject = fail}))
  const pending = queue.flush()
  queue.discard('old')
  reject(new Error('旧版本失效'))
  await pending
  expect(queue.error()).toBeUndefined()
  queue.enqueue('current',save)
  await queue.flush()
  expect(save).toHaveBeenCalledOnce()
})
