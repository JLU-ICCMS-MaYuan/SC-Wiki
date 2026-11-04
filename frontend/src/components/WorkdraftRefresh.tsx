import { useEffect, useRef, useState } from 'react'
import { Alert, Button } from '@mui/material'
import { api } from '../lib/api'
import { rememberWorkdraft } from '../lib/workdraftSession'
import type { EvidenceTarget } from './EvidenceWorkflow'

type Metadata = { revision: number | null; write_epoch: string | null }
/** 仅焦点检查小型修订号。整稿响应先暂存，宿主验证没有新输入后才采用。 */
export function useWorkdraftRefresh(target: EvidenceTarget | undefined, options: {
  onAccessError?: (error: unknown) => boolean
  enabled: boolean; busy: () => boolean; dirty: () => boolean; editVersion: () => unknown
  apply: (draft: any, fieldState?: any, spectra?: any) => Promise<void> | void
}) {
  const current = useRef(options); current.current = options
  const [available, setAvailable] = useState(false), [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const metadata = useRef<Metadata | undefined>(undefined), generation = useRef(0)
  const identity = target ? target.target + ':' + target.target_id : ''
  useEffect(() => {
    const epoch = ++generation.current
    metadata.current = undefined; setAvailable(false); setError('')
    if (!target || !options.enabled) return
    let running = false, lastCheck = 0
    const initial = target.target === 'paper'
      ? api.post<Metadata>('/api/rag/evidence/open-workdraft', target)
      : api.get<Metadata>('/api/rag/evidence/draft-revision?' + new URLSearchParams({target:target.target,target_id:target.target_id}))
    void initial.then(result => {
      if (epoch === generation.current) {
        metadata.current = result; rememberWorkdraft(target,result.write_epoch)
        window.dispatchEvent(new CustomEvent('workdraft-opened',{detail:target}))
      }
    }).catch(reason => { if (epoch === generation.current && !current.current.onAccessError?.(reason)) setError(reason.message) })
    const check = async () => {
      if (document.visibilityState === 'hidden' || running || !metadata.current || Date.now()-lastCheck<100) return
      running = true; lastCheck = Date.now()
      try {
        const result = await api.get<Metadata>('/api/rag/evidence/draft-revision?target=' +
          target.target + '&target_id=' + encodeURIComponent(target.target_id))
        if (epoch !== generation.current) return
        if (metadata.current.write_epoch && result.write_epoch !== metadata.current.write_epoch) {
          const failure = Object.assign(new Error('当前工作稿已交出或归属已变化，请重新打开稿件。'), { code: 'manuscript_handed_off' })
          if (!current.current.onAccessError?.(failure)) setError(failure.message)
          return
        }
        if (!metadata.current.write_epoch) {
          metadata.current = {...metadata.current,write_epoch:result.write_epoch}
          rememberWorkdraft(target,result.write_epoch)
        }
        if (result.revision !== metadata.current.revision) setAvailable(true)
      } catch (reason) { if (epoch === generation.current && !current.current.onAccessError?.(reason)) setError((reason as Error).message) }
      finally { running = false }
    }
    const visible = () => { if (document.visibilityState === 'visible') void check() }
    const saved = (event: Event) => {
      const data = (event as CustomEvent).detail
      if (data.target.target + ':' + data.target.target_id === identity && data.write_epoch === metadata.current?.write_epoch) metadata.current = data
    }
    window.addEventListener('workdraft-saved',saved)
    window.addEventListener('focus', check); document.addEventListener('visibilitychange', visible)
    return () => { ++generation.current; window.removeEventListener('workdraft-saved',saved); window.removeEventListener('focus', check); document.removeEventListener('visibilitychange', visible) }
  }, [identity, options.enabled])
  const load = async () => {
    if (!target || loading || current.current.busy()) return
    if (current.current.dirty() && !window.confirm('载入最新稿会替换本页未保存的字段、理由和证据，是否继续？')) return
    const epoch = generation.current, version = current.current.editVersion()
    setLoading(true); setError('')
    try {
      const result = await api.get<{ draft: any; field_state?: any; spectra?: any; revision: number; write_epoch: string }>(
        '/api/rag/evidence/draft-state?include_fields=true&target=' + target.target + '&target_id=' + encodeURIComponent(target.target_id))
      if (epoch !== generation.current || version !== current.current.editVersion() || current.current.busy()) return
      if (result.write_epoch !== metadata.current?.write_epoch) throw new Error('工作稿周期已变化，请重新打开稿件。')
      await current.current.apply(result.draft,result.field_state,result.spectra)
      metadata.current = result; setAvailable(false)
    } catch (reason) { if (epoch === generation.current && !current.current.onAccessError?.(reason)) setError((reason as Error).message) }
    finally { if (epoch === generation.current) setLoading(false) }
  }
  return { available, loading, error, load }
}

export default function WorkdraftRefresh({ state, busy }: {
  state: ReturnType<typeof useWorkdraftRefresh>; busy: boolean
}) {
  return <>{state.error && <Alert severity="warning">{state.error}</Alert>}
    {state.available && <Alert severity="info" action={<Button disabled={busy || state.loading} onClick={() => void state.load()}>
      {state.loading ? '载入中…' : '载入最新稿'}</Button>}>其他页面已保存更新，本页内容暂时保留。</Alert>}</>
}
