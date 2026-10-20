import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type ApiError } from './api'
import { useAuth } from '../context/AuthContext'

export const COMMUNITY_API = '/api/community'
export interface CommunityTarget { question_id?: number; answer_id?: number; paper_id?: number; system_key?: string }
export interface CommunityAuthor { username: string; avatar_url?: string; banned?: boolean; deactivated?: boolean }
export interface CommunityTurn {
  key: string; id: number | null; body: string; sequence: number; revision: number; human_edited?: boolean; created_at: string; sources_available?: boolean
  citations?: Array<{ id: string; paper_id: number; paper_revision: number; title: string }>
  replies?: Array<{ key: string; model_name: string; sequence: number }>
}
export interface CommunityEntry extends CommunityTarget {
  id: number; kind: 'question' | 'answer' | 'comment'; title: string; body: string
  status: 'visible' | 'deleted' | 'hidden'; author: CommunityAuthor | null
  parent_id: number | null; reply_to_id: number | null; votes: number; voted: boolean; answer_count: number
  turns?: CommunityTurn[]; model_count?: number; response_count?: number
  origin?: 'human' | 'ai'; category?: string; model_id?: string; model_name?: string; model?: string; model_order?: number
  revision?: number; human_edited?: boolean; sources_available?: boolean
  citations?: Array<{ id: string; paper_id: number; paper_revision: number; title: string }>
  generation_tasks?: CommunityAITask[]
  can_edit: boolean; can_delete: boolean; can_reply: boolean; created_at: string; updated_at: string; url: string
}
export interface CommunityAITask { id: number; batch_id?: string; model_id: string; model_name: string; model: string; model_order: number; state: string; error: string; answer_id: number | null }
export interface CommunityAIBatch { id: string; question_id: number | null; state: string; error: string; category: string; can_retry: boolean; tasks: CommunityAITask[] }
export interface CommunityList<T> { items: T[]; total: number; offset?: number; context?: T[] }
export function targetQuery(target: CommunityTarget): string {
  return new URLSearchParams(Object.entries(target).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString()
}
export function communityErrorKey(error: unknown): string {
  const code = (error as ApiError)?.code
  const known = ['workflow_changed', 'context_too_long', 'community_read_only', 'community_revision_conflict', 'community_ai_unavailable', 'no_models', 'request_conflict', 'superadmin_required', 'model_config_changed', 'sources_changed', 'preparation_failed', 'queue_unavailable', 'retry_model_separately', 'invalid_community_input', 'content_unavailable', 'verified_account_required', 'paper_forbidden', 'not_content_author', 'community_rate_limited', 'community_rate_limit_unavailable', 'community_unavailable', 'invalid_moderation_transition']
  return `community.errors.${code && known.includes(code) ? code : 'generic'}`
}
export function useCommunityLoad<T>(path: string | null) {
  const { token } = useAuth()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const loadedKey = useRef('')
  const reload = useCallback(() => setVersion(v => v + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    const key = `${path}\0${token}`
    const sameTarget = loadedKey.current === key
    loadedKey.current = key
    if (!sameTarget) setData(null)
    setError(''); setLoading(Boolean(path) && !sameTarget)
    if (path) void api.get<T>(COMMUNITY_API + path, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setData(value) })
      .catch(reason => { if (!controller.signal.aborted) { if ([401, 403, 404].includes(reason?.status)) setData(null); setError(communityErrorKey(reason)) } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [path, token, version])
  return { data, error, loading, reload }
}
export function focusedEntry(): number | undefined {
  const raw = new URLSearchParams(window.location.search).get('focus')
  return raw && /^\d+$/.test(raw) && Number(raw) > 0 ? Number(raw) : undefined
}
export function notifyCommunityChanged() { window.dispatchEvent(new Event('community-notifications-changed')) }

// 稳定独立答案地址；跨答案回应不会受问题列表分页影响。
export function answerPath(questionId: number | string, answerId: number | string, turnKey?: string): string {
  return `/share/discussions/${questionId}/answers/${answerId}${turnKey ? `#answer-${turnKey}` : ''}`
}

export function answerExcerpt(body: string): string {
  return body.replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]*>/g, '').replace(/[#*`>]/g, '').replace(/\s+/g, ' ').trim().slice(0, 300)
}
