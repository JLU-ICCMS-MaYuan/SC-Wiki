import type { UploadExtractionTiming } from './paperProcessing'

// 只接受服务端记录；缺少时间依据时不能从通用更新时间推算。
export function extractionElapsedSeconds(
  timing: UploadExtractionTiming | null | undefined,
  now: number,
): number | 'notStarted' | null {
  const seconds = (value: unknown): value is number =>
    typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
  if (!timing || !seconds(timing.elapsed_seconds) ||
      [timing.started_at, timing.running_since, timing.finished_at]
        .some(value => value !== null && !seconds(value))) return null
  if (timing.started_at === null) {
    return timing.elapsed_seconds === 0 && timing.running_since === null ? 'notStarted' : null
  }
  if (timing.finished_at !== null && timing.running_since !== null) return null
  const running = timing.running_since === null ? 0 : Math.max(0, Math.floor(now / 1000) - timing.running_since)
  return timing.elapsed_seconds + running
}
