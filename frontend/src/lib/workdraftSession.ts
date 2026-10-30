import type { EvidenceTarget } from '../components/EvidenceWorkflow'

const epochs = new Map<string,string>()
const identity = (target: EvidenceTarget) => target.target + ':' + target.target_id
export const workdraftEpoch = (target: EvidenceTarget) => epochs.get(identity(target))
export const rememberWorkdraft = (target: EvidenceTarget, epoch?: string | null) => {
  if (epoch) epochs.set(identity(target),epoch)
}

/** 每个标签页保留打开时周期；不能在写旧稿时自动换成新的凭证。 */
export function workdraftHeaders(url: string, data?: any): Record<string,string> {
  let target: EvidenceTarget | undefined
  if (data?.target && data?.target_id) target = data
  else {
    const query = new URL(url,'http://isolated').searchParams
    if (query.get('target') && query.get('target_id')) target = {
      target:query.get('target') as EvidenceTarget['target'],target_id:query.get('target_id')!}
    const manual = url.match(/\/evidence\/(upload|paper|revision)\/([^/?]+)\/manual\//)
    if (manual) target = {target:manual[1] as EvidenceTarget['target'],target_id:decodeURIComponent(manual[2])}
    else if (url.includes('paper_id=') || data?.paper_id) {
      const id = data?.paper_id ?? new URL(url,'http://isolated').searchParams.get('paper_id')
      if (id) target = {target:'paper',target_id:String(id)}
    }
  }
  const epoch=target && workdraftEpoch(target)
  return epoch ? {'X-Workdraft-Epoch':epoch} : {}
}
