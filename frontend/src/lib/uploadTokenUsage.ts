import type { UploadTaskState } from './paperProcessing'

const count = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0

export function uploadTokenUsage(task: UploadTaskState) {
  const usage = task.extraction_token_usage
  if (!usage || !usage.run_id ||
      ![usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.request_count, usage.recorded_requests].every(count) ||
      usage.total_tokens !== usage.input_tokens + usage.output_tokens ||
      usage.recorded_requests > usage.request_count ||
      (usage.recorded_requests === 0 && usage.total_tokens !== 0)) return null
  if (usage.request_count > 0 && usage.recorded_requests === 0) return null
  if (usage.request_count === 0 && task.extraction_timing?.started_at === null &&
      ['uploading', 'queued'].includes(task.status || '')) return 'notStarted'
  return { ...usage, incomplete: usage.recorded_requests < usage.request_count }
}
