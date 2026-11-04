import type { ApiError } from './api'

export const handedOffMessage = '稿件已交出，当前账号没有编辑权。'
export function isHandedOff(error: unknown): boolean {
  return (error as ApiError | null)?.code === 'manuscript_handed_off'
}
