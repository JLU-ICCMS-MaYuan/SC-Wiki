import { api } from './api'

export interface CloudTurn {
  id: number
  sequence: number
  question: string
  answer: string
  citations: Array<{ paper_id: number; source_kind?: string; attribution?: string }>
  display_meta: Record<string, any>
}

export interface CloudConversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  last_sequence: number
  turns?: CloudTurn[]
}

type Wrapped<T> = { ok: boolean; data: T }

export async function listCloudConversations(offset = 0): Promise<CloudConversation[]> {
  const result = await api.get<Wrapped<CloudConversation[]>>(`/api/rag/conversations?limit=50&offset=${offset}`)
  return result.data
}

export async function getCloudConversation(id: string): Promise<CloudConversation> {
  const result = await api.get<Wrapped<CloudConversation>>(`/api/rag/conversations/${encodeURIComponent(id)}`)
  return result.data
}

export async function createCloudConversation(): Promise<CloudConversation> {
  const result = await api.post<Wrapped<CloudConversation>>('/api/rag/conversations', {})
  return result.data
}

export async function deleteCloudConversation(id: string): Promise<void> {
  await api.del(`/api/rag/conversations/${encodeURIComponent(id)}`)
}

export async function importLocalConversation(conversation: {
  id: string; title: string; messages: Array<{ role: 'user' | 'assistant'; content: string; citations?: unknown[] }>
}): Promise<CloudConversation> {
  const result = await api.post<Wrapped<CloudConversation>>('/api/rag/conversations/import', {
    source_local_id: conversation.id,
    title: conversation.title,
    messages: conversation.messages,
  })
  return result.data
}
