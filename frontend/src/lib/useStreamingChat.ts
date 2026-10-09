import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from './api'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import {
  createCloudConversation, deleteCloudConversation, getCloudConversation,
  importLocalConversation, listCloudConversations, type CloudConversation,
} from './ragConversations'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: Array<{ paper_id: number; source_kind?: string; attribution?: string }>
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  lastSequence: number
}

interface PaperInfo { title?: string; doi?: string; journal?: string; year?: number }
interface InspirationState {
  active: boolean; mode: string; modeLabel: string; statusMessage: string; sessionId: string; ideasCount: number
}
interface IdeaCard {
  title: string
  fragments: Array<{ paper_id: number; quoted_text: string; section: string }>
  reasoning_chain: string
  assumptions: string[]
  feasibility?: { overall: number; theory: number; synthesis: number; measurement: number }
}
interface ReviewVerdict {
  flaws: Array<{ severity: string; description: string }>
  feasibility_score: number
  revised_idea: string
  dimensions: { theory: number; synthesis: number; measurement: number }
}
interface SavedPaper { pid: string; info: PaperInfo }
interface CachedMeta {
  papers: Record<string, PaperInfo>; top10: any[]; inspiration: InspirationState | null
  ideas: IdeaCard[]; reviews: ReviewVerdict[]; savedPapers: SavedPaper[]
}

const emptyInspiration = (): InspirationState => ({ active: false, mode: '', modeLabel: '', statusMessage: '', sessionId: '', ideasCount: 0 })
const emptyMeta = (): CachedMeta => ({ papers: {}, top10: [], inspiration: null, ideas: [], reviews: [], savedPapers: [] })
const uid = () => crypto.randomUUID().replace(/-/g, '')

function loadLocal(): Conversation[] {
  try {
    const raw = JSON.parse(localStorage.getItem('rag_conversations') || '[]')
    if (!Array.isArray(raw)) return []
    return raw.filter(c => c && typeof c.id === 'string').map(c => ({
      ...c, lastSequence: Math.floor((c.messages || []).length / 2),
      messages: (c.messages || []).filter((m: ChatMessage) => m.role !== 'assistant' || m.content),
    }))
  } catch { return [] }
}
function saveLocal(list: Conversation[]) {
  try { localStorage.setItem('rag_conversations', JSON.stringify(list)) } catch { /* 本机存储不可用时保持当前页面 */ }
}
function loadMeta(id: string): CachedMeta {
  try { return { ...emptyMeta(), ...JSON.parse(localStorage.getItem(`rag_meta_${id}`) || '{}') } }
  catch { return emptyMeta() }
}
function saveMeta(id: string, meta: CachedMeta) {
  try { localStorage.setItem(`rag_meta_${id}`, JSON.stringify(meta)) } catch { /* 会话仍可继续 */ }
}
function fromCloud(row: CloudConversation): Conversation {
  return {
    id: row.id, title: row.title, createdAt: Date.parse(row.created_at),
    lastSequence: row.last_sequence,
    messages: (row.turns || []).flatMap(turn => [
      { role: 'user' as const, content: turn.question },
      { role: 'assistant' as const, content: turn.answer, citations: turn.citations },
    ]),
  }
}

export function useStreamingChat() {
  const { t } = useLanguage()
  const tRef = useRef(t)
  tRef.current = t
  const { user, loading: authLoading } = useAuth()
  const cloud = Boolean(user)
  const [convs, setConvs] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncState, setSyncState] = useState<'local' | 'loading' | 'saved' | 'error'>('local')
  const [syncError, setSyncError] = useState('')
  const [loadedIdentity, setLoadedIdentity] = useState<string | null>(null)
  const [importedIds, setImportedIds] = useState<string[]>([])
  const [legacyCount, setLegacyCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [papers, setPapers] = useState<Record<string, PaperInfo>>({})
  const [top10, setTop10] = useState<any[]>([])
  const [inspiration, setInspiration] = useState<InspirationState>(emptyInspiration)
  const [ideas, setIdeas] = useState<IdeaCard[]>([])
  const [reviews, setReviews] = useState<ReviewVerdict[]>([])
  const [savedPapers, setSavedPapers] = useState<SavedPaper[]>([])
  const [statusLog, setStatusLog] = useState<string[]>([])
  const streamRef = useRef<HTMLDivElement | null>(null)
  const selectionRef = useRef(0)
  const authEpochRef = useRef(0)
  const identity = user ? `user:${user.id}` : 'guest'
  const messages = convs.find(c => c.id === activeId)?.messages || []

  const applyMeta = useCallback((meta: CachedMeta) => {
    setPapers(meta.papers || {})
    setTop10(meta.top10 || [])
    setInspiration(meta.inspiration || emptyInspiration())
    setIdeas(meta.ideas || [])
    setReviews(meta.reviews || [])
    setSavedPapers(meta.savedPapers || [])
    setStatusLog([])
  }, [])

  useEffect(() => {
    if (authLoading) return
    authEpochRef.current += 1
    const token = ++selectionRef.current
    setLoadedIdentity(null)
    setConvs([])
    setHasMore(false)
    setActiveId('')
    applyMeta(emptyMeta())
    if (!user) {
      const local = loadLocal()
      setConvs(local)
      if (local[0]) { setActiveId(local[0].id); applyMeta(loadMeta(local[0].id)) }
      setSyncState('local')
      setLegacyCount(0)
      setSyncError('')
      setLoadedIdentity('guest')
      return
    }
    let imported: string[] = []
    try {
      const stored = JSON.parse(localStorage.getItem(`rag_imported_${user.id}`) || '[]')
      imported = Array.isArray(stored) ? stored.filter((id): id is string => typeof id === 'string') : []
    }
    catch { /* 标记损坏时允许重新导入，服务端保持幂等 */ }
    setImportedIds(imported)
    setLegacyCount(loadLocal().filter(c => c.messages.length > 0 && !imported.includes(c.id)).length)
    setSyncState('loading')
    listCloudConversations().then(rows => {
      if (selectionRef.current !== token) return
      setConvs(rows.map(fromCloud))
      setHasMore(rows.length === 50)
      setLoadedIdentity(`user:${user.id}`)
      setSyncState('saved')
      setSyncError('')
      if (rows[0]) {
        setActiveId(rows[0].id)
        void getCloudConversation(rows[0].id).then(detail => {
          if (selectionRef.current === token) {
            setConvs(prev => prev.map(c => c.id === detail.id ? fromCloud(detail) : c))
            applyMeta(detail.turns?.at(-1)?.display_meta as CachedMeta || emptyMeta())
          }
        }).catch(() => { if (selectionRef.current === token) setSyncState('error') })
      }
    }).catch(() => {
      if (selectionRef.current === token) {
        setSyncState('error')
        setSyncError(tRef.current('rag.syncFailed'))
        setLoadedIdentity(`user:${user.id}`)
      }
    })
    return () => { selectionRef.current += 1 }
  }, [user?.id, authLoading, applyMeta])

  useEffect(() => {
    if (!authLoading && identity === 'guest' && loadedIdentity === 'guest') saveLocal(convs)
  }, [convs, identity, loadedIdentity, authLoading])

  const newConversation = useCallback(() => {
    if (loading) return
    applyMeta(emptyMeta())
    if (cloud) { setActiveId(''); return }
    const c: Conversation = { id: uid(), title: t('rag.newConversation'), messages: [], createdAt: Date.now(), lastSequence: 0 }
    setConvs(prev => [c, ...prev])
    setActiveId(c.id)
  }, [applyMeta, cloud, loading, t])

  const switchConversation = useCallback(async (id: string) => {
    if (loading) return
    const token = ++selectionRef.current
    setActiveId(id)
    applyMeta(cloud ? emptyMeta() : loadMeta(id))
    if (!cloud) return
    setSyncState('loading')
    try {
      const detail = await getCloudConversation(id)
      if (selectionRef.current !== token) return
      setConvs(prev => prev.map(c => c.id === id ? fromCloud(detail) : c))
      applyMeta(detail.turns?.at(-1)?.display_meta as CachedMeta || emptyMeta())
      setSyncState('saved')
      setSyncError('')
    } catch {
      if (selectionRef.current === token) { setSyncState('error'); setSyncError(t('rag.syncFailed')) }
    }
  }, [applyMeta, cloud, loading, t])

  const deleteConversation = useCallback(async (id: string) => {
    if (loading) return
    try {
      if (cloud) await deleteCloudConversation(id)
      else localStorage.removeItem(`rag_meta_${id}`)
      const next = convs.filter(c => c.id !== id)
      setConvs(next)
      if (activeId === id) {
        setActiveId(next[0]?.id || '')
        applyMeta(next[0] && !cloud ? loadMeta(next[0].id) : emptyMeta())
        if (cloud && next[0]) void switchConversation(next[0].id)
      }
    } catch {
      setSyncState('error')
      setSyncError(t('rag.syncFailed'))
    }
  }, [activeId, applyMeta, cloud, convs, loading, switchConversation, t])

  const importLegacy = useCallback(async () => {
    if (!cloud || loading) return
    setSyncState('loading')
    try {
      const pending = loadLocal().filter(c => c.messages.length > 0 && !importedIds.includes(c.id))
      for (const local of pending) {
        await importLocalConversation(local)
      }
      const nextIds = [...new Set([...importedIds, ...pending.map(c => c.id)])]
      localStorage.setItem(`rag_imported_${user!.id}`, JSON.stringify(nextIds))
      setImportedIds(nextIds)
      setLegacyCount(0)
      const rows = await listCloudConversations()
      setConvs(rows.map(fromCloud))
      setHasMore(rows.length === 50)
      setSyncState('saved')
      setSyncError('')
    } catch {
      setSyncState('error')
      setSyncError(t('rag.importFailed'))
    }
  }, [cloud, importedIds, loading, t, user])

  const loadMore = useCallback(async () => {
    if (!cloud || !hasMore || loading) return
    try {
      const rows = await listCloudConversations(convs.length)
      setConvs(prev => {
        const seen = new Set(prev.map(c => c.id))
        return [...prev, ...rows.filter(row => !seen.has(row.id)).map(fromCloud)]
      })
      setHasMore(rows.length === 50)
    } catch { setSyncState('error'); setSyncError(t('rag.syncFailed')) }
  }, [cloud, convs.length, hasMore, loading, t])

  const send = useCallback(async (question: string, explore = false): Promise<boolean> => {
    const q = question.trim()
    if (!q || loading) return false
    const epoch = authEpochRef.current
    let cid = activeId
    let current = convs.find(c => c.id === cid)
    try {
      if (!cid) {
        if (cloud) {
          const row = await createCloudConversation()
          current = fromCloud(row)
        } else {
          current = { id: uid(), title: t('rag.newConversation'), messages: [], createdAt: Date.now(), lastSequence: 0 }
        }
        cid = current.id
        if (authEpochRef.current !== epoch) return false
        setConvs(prev => [current!, ...prev])
        setActiveId(cid)
      }
      if (!current) return false
    } catch {
      if (authEpochRef.current !== epoch) return false
      setSyncState('error')
      setSyncError(t('rag.syncFailed'))
      return false
    }
    const prior = current.messages
    const history = prior.filter(m => m.content && !m.content.startsWith('❌'))
    const requestId = uid()
    setLoading(true)
    setSyncState(cloud ? 'loading' : 'local')
    setSyncError('')
    setStatusLog([])
    if (explore) {
      setInspiration({ ...emptyInspiration(), active: true, modeLabel: t('rag.exploreMode'), statusMessage: t('rag.analyzingQuestion') })
      setIdeas([]); setReviews([])
    }
    setConvs(prev => prev.map(c => c.id === cid ? {
      ...c, title: c.messages.length === 0 ? q.slice(0, 80) : c.title,
      messages: [...prior, { role: 'user', content: q }, { role: 'assistant', content: '' }],
    } : c))

    let answer = ''
    let doneData: any = null
    let receivedIdeas: IdeaCard[] = []
    let receivedReviews: ReviewVerdict[] = []
    try {
      const response = await api.postStream('/api/rag/chat/stream', {
        question: q, top_k: 15, rerank_top_k: 5, explore,
        ...(cloud ? { conversation_id: cid, request_id: requestId, expected_last_sequence: current.lastSequence }
          : { history }),
      })
      if (!response.ok || !response.body) {
        let message = `HTTP ${response.status}`
        try { message = (await response.json()).detail?.message || message } catch { /* 维持状态码 */ }
        throw new Error(message)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const part = await reader.read()
        if (authEpochRef.current !== epoch) { await reader.cancel(); return false }
        if (part.done) break
        buffer += decoder.decode(part.value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''
        for (const raw of events) {
          const eventType = raw.split('\n').find(line => line.startsWith('event:'))?.slice(6).trim() || 'message'
          const payload = raw.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n')
          if (!payload) continue
          let data: any
          try { data = JSON.parse(payload) } catch { continue }
          if (eventType === 'error') throw new Error(data?.message || t('rag.aiError'))
          if (eventType === 'token') {
            answer += typeof data === 'string' ? data : String(data || '')
            const partial = answer
            setConvs(prev => prev.map(c => c.id === cid ? {
              ...c, messages: c.messages.map((m, i) => i === c.messages.length - 1 ? { ...m, content: partial } : m),
            } : c))
          } else if (eventType === 'done') {
            doneData = data
            answer = String(data.answer || answer)
            if (Array.isArray(data.ideas)) receivedIdeas = data.ideas
            if (data.papers) setPapers(data.papers)
            if (data.top10) setTop10(data.top10)
          } else if (eventType === 'evidence_card') {
            receivedIdeas.push(data); setIdeas(prev => [...prev, data])
          } else if (eventType === 'review_verdict') {
            receivedReviews.push(data); setReviews(prev => [...prev, data])
          } else if (eventType === 'status' || eventType === 'tool_start' || eventType === 'tool_end') {
            const status = data.message || data.name || ''
            if (status) setStatusLog(prev => [...prev, status])
            setInspiration(prev => prev.active ? { ...prev, statusMessage: status } : prev)
          } else if (eventType === 'inspire_enter') {
            setInspiration(prev => ({ ...prev, active: true, mode: data.mode, modeLabel: data.mode_label, sessionId: data.session_id }))
          } else if (eventType === 'inspire_exit') {
            setInspiration(emptyInspiration())
          }
        }
      }
      if (!doneData || !answer.trim()) throw new Error(t('rag.aiError'))
      const citations = Array.isArray(doneData.citations) ? doneData.citations : []
      setConvs(prev => prev.map(c => c.id === cid ? {
        ...c, lastSequence: cloud ? doneData.sequence : c.lastSequence + 1,
        messages: c.messages.map((m, i) => i === c.messages.length - 1 ? { ...m, content: answer, citations } : m),
      } : c))
      setIdeas(receivedIdeas)
      setReviews(receivedReviews)
      const meta: CachedMeta = {
        papers: doneData.papers || {}, top10: doneData.top10 || [],
        inspiration: doneData.inspiration || null, ideas: receivedIdeas, reviews: receivedReviews,
        savedPapers: Object.entries(doneData.papers || {}).map(([pid, info]) => ({ pid, info: info as PaperInfo })),
      }
      setSavedPapers(meta.savedPapers)
      if (!cloud) saveMeta(cid, meta)
      setSyncState(cloud ? 'saved' : 'local')
      return true
    } catch (error) {
      if (authEpochRef.current !== epoch) return false
      if (cloud) {
        try {
          const remote = await getCloudConversation(cid)
          if (authEpochRef.current !== epoch) return false
          setConvs(prev => prev.map(c => c.id === cid ? fromCloud(remote) : c))
          applyMeta(remote.turns?.at(-1)?.display_meta as CachedMeta || emptyMeta())
          if (remote.last_sequence > current.lastSequence && remote.turns?.at(-1)?.question === q) {
            setSyncState('saved')
            setSyncError('')
            return true
          }
          setSyncState('error')
          setSyncError(remote.last_sequence > current.lastSequence
            ? t('rag.conversationUpdated') : error instanceof Error ? error.message : t('rag.aiError'))
          return false
        } catch { /* 云端不可用时仍保留原问题供重试 */ }
      }
      setConvs(prev => prev.map(c => c.id === cid ? { ...c, messages: prior } : c))
      setSyncState('error')
      setSyncError(error instanceof Error ? error.message : t('rag.aiError'))
      return false
    } finally {
      setLoading(false)
    }
  }, [activeId, applyMeta, cloud, convs, loading, t])

  return {
    convs, activeId, messages, loading, papers, top10, ideas, reviews, statusLog,
    savedPapers, inspiration, streamRef, cloud, syncState, syncError, legacyCount, hasMore,
    newConversation, switchConversation, deleteConversation, importLegacy, loadMore, send,
  }
}
