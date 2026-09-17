/** 合并同一字段的连续输入；失败后保留最新操作，等待用户显式重试。 */
export function createEvidenceDraftQueue(notify: (state: { saving: boolean; error?: Error }) => void, delay = 500) {
  const pending = new Map<string, () => Promise<void>>()
  let timer: ReturnType<typeof setTimeout> | undefined
  let running: Promise<void> | undefined
  let failure: Error | undefined
  const flush = (): Promise<void> => {
    clearTimeout(timer)
    if (running) return running
    if (failure) return Promise.reject(failure)
    running = (async () => {
      notify({ saving: true })
      while (pending.size) {
        const [key, operation] = pending.entries().next().value!
        try {
          await operation()
          if (pending.get(key) === operation) pending.delete(key)
        } catch (error) {
          // 已失效并移除的请求不能用迟到错误阻塞新版本草稿。
          if (!pending.has(key)) continue
          failure = error instanceof Error ? error : new Error(String(error))
          notify({ saving: false, error: failure })
          throw failure
        }
      }
      notify({ saving: false })
    })().finally(() => { running = undefined })
    return running
  }
  return {
    enqueue(key: string, operation: () => Promise<void>) {
      pending.set(key, operation)
      clearTimeout(timer)
      if (!failure && !running) timer = setTimeout(() => { void flush().catch(() => undefined) }, delay)
    },
    flush,
    discard(key: string) {
      pending.delete(key)
      if (!pending.size) { clearTimeout(timer); failure = undefined }
    },
    async retry() {
      if (running) await running.catch(() => undefined)
      failure = undefined
      return flush()
    },
    hasPending: () => pending.size > 0,
    error: () => failure,
  }
}
