import { api } from './api'

interface BatchProgress { total_batches?: number; completed_batches?: number }

export function evidencePercent(job: BatchProgress): number {
  const total = job.total_batches || 0
  const done = Math.min(total, Math.max(0, job.completed_batches || 0))
  // 全部批次返回后仍须保存结果并检查最终版本，不能提前显示100%。
  return total > 0 ? 20 + Math.floor(75 * done / total) : 20
}

export function startEvidencePreparation<T>(path: string, body: object, onProgress: (percent: number) => void) {
  const identity = crypto.randomUUID().replaceAll('-', '')
  const progressPath = `/api/rag/evidence/preparations/${identity}`
  let stopped = false
  let cancelled = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let deadline: ReturnType<typeof setTimeout> | undefined
  let rejectCancellation!: (error: Error) => void
  const cancellation = new Promise<never>((_, reject) => { rejectCancellation = reject })
  const stop = () => { stopped = true; clearTimeout(timer); clearTimeout(deadline) }
  const cancel = (code = 'evidence_preparation_cancelled') => {
    cancelled = true
    stop()
    void api.del(progressPath).catch(() => undefined)
    rejectCancellation(Object.assign(new Error(code), { code }))
  }
  const poll = async () => {
    try {
      const state = await api.get<{ percent: number; cancelled: boolean }>(progressPath)
      if (!stopped && !state.cancelled && Number.isFinite(state.percent)) onProgress(state.percent)
    } catch { /* 请求尚未注册或进度查询暂时失败时保持最后值；主请求负责报告错误。 */ }
    if (!stopped) timer = setTimeout(() => void poll(), 1000)
  }
  timer = setTimeout(() => void poll(), 1000)
  const response = api.post<T>(path, { ...body, progress_id: identity }).then(async result => {
    // 即使取消比服务端注册更早、或排队发生在最后一次检查之后，也清理迟到任务。
    const job = result as { id?: string; status?: string }
    if (cancelled && job.id && job.status !== 'completed') {
      await api.del(`/api/rag/evidence/jobs/${job.id}`).catch(() => undefined)
    }
    return result
  })
  deadline = setTimeout(() => cancel('evidence_preparation_timeout'), 1800 * 1000)
  const result = Promise.race([response, cancellation]).finally(stop)
  return {
    result,
    cancel: () => cancel(),
  }
}
