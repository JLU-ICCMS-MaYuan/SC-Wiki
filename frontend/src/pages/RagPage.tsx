import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Drawer, IconButton, Stack, TextField, Tooltip, Typography,
} from '@mui/material'
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import MenuIcon from '@mui/icons-material/Menu'
import AddIcon from '@mui/icons-material/Add'
import SendIcon from '@mui/icons-material/Send'
import { api } from '../lib/api'
import { useStreamingChat } from '../lib/useStreamingChat'
import MarkdownMessage from '../components/MarkdownMessage'
import RagSourceDrawer, { type SourceTarget } from '../components/RagSourceDrawer'
import EvidenceCard from '../components/EvidenceCard'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'

const RagPage: React.FC = () => {
  const { t } = useLanguage()
  const { user, token } = useAuth()
  const suggestions = [t('rag.suggestion1'), t('rag.suggestion2'), t('rag.suggestion3')]
  const {
    convs, activeId, messages, loading, papers, top10, ideas, reviews, statusLog,
    savedPapers, inspiration, cloud, syncState, syncError, legacyCount, hasMore,
    newConversation, switchConversation, deleteConversation, importLegacy, loadMore, send,
  } = useStreamingChat()
  const [input, setInput] = useState('')
  const [exploreMode, setExploreMode] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [target, setTarget] = useState<SourceTarget | null>(null)
  const [polishing, setPolishing] = useState(false)
  const [polishError, setPolishError] = useState('')
  const [undoPolish, setUndoPolish] = useState<{ text: string; revision: number } | null>(null)
  const revisionRef = useRef(0)
  const requestRef = useRef(0)
  const pendingRef = useRef<number | null>(null)
  const sendContextRef = useRef(0)
  const triggerRef = useRef<{ element: HTMLElement; index: number } | null>(null)
  const chatBoxRef = useRef<HTMLDivElement>(null)

  const invalidatePolish = () => {
    revisionRef.current += 1
    requestRef.current += 1
    pendingRef.current = null
    setPolishing(false)
    setPolishError('')
    setUndoPolish(null)
  }
  // 布局副作用在异步响应回调前使已切换的上下文失效，卸载后同样不再回填。
  useLayoutEffect(() => {
    invalidatePolish()
    setTarget(null)
    return () => { requestRef.current += 1; pendingRef.current = null }
  }, [activeId, user?.id, token])
  useLayoutEffect(() => {
    sendContextRef.current += 1
    return () => { sendContextRef.current += 1 }
  }, [user?.id, token])
  useEffect(() => {
    if (target || !triggerRef.current) return
    const restore = () => {
      if (document.querySelector('[data-rag-source-drawer]')) return false
      focusSource()
      return true
    }
    if (restore()) return
    const observer = new MutationObserver(() => { if (restore()) observer.disconnect() })
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [target])
  const focusSource = () => {
    const saved = triggerRef.current
    if (!saved) return
    const trigger = saved.element.isConnected ? saved.element
      : document.querySelectorAll<HTMLElement>('.rag-source-link')[saved.index]
    trigger?.focus({ preventScroll: true })
  }
  useEffect(() => {
    const box = chatBoxRef.current
    if (box?.scrollTo) box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' })
  }, [messages.length, loading, ideas.length])

  const paperSeqMap = useMemo(() => {
    const map: Record<string, number> = {}
    const ids = savedPapers.length ? savedPapers.map(item => item.pid) : Object.keys(papers)
    ids.forEach((pid, index) => { map[pid] = index + 1 })
    return map
  }, [papers, savedPapers])

  const changeInput = (value: string) => {
    invalidatePolish()
    setInput(value)
  }
  const inputTooLong = Array.from(input).length > 1000
  const handleSend = async () => {
    const question = input.trim()
    if (!question || loading || inputTooLong) return
    changeInput('')
    const context = sendContextRef.current
    const ok = await send(question, exploreMode)
    // 自动创建会话不妨碍失败恢复；显式导航或切换账号则不能恢复到新上下文。
    if (!ok && context === sendContextRef.current) {
      invalidatePolish()
      setInput(current => current || question)
    }
  }
  const handlePolish = async () => {
    const text = input.trim()
    if (!text || pendingRef.current !== null || loading || inputTooLong) return
    const origin = { text: input, revision: revisionRef.current }
    const request = ++requestRef.current
    pendingRef.current = request
    setUndoPolish(null)
    setPolishError('')
    setPolishing(true)
    try {
      const result = await api.post<{ ok: boolean; data: { suggestion: string } }>('/api/rag/prompts/polish', { draft: text })
      if (requestRef.current !== request || revisionRef.current !== origin.revision) return
      const suggestion = result.data?.suggestion
      if (!result.ok || typeof suggestion !== 'string' || !suggestion.trim() || Array.from(suggestion).length > 1000) {
        throw new Error('Invalid polish response')
      }
      if (suggestion !== origin.text) {
        revisionRef.current += 1
        setInput(suggestion)
        setUndoPolish({ text: origin.text, revision: revisionRef.current })
      }
    } catch {
      if (requestRef.current === request && revisionRef.current === origin.revision) setPolishError(t('rag.polishFailed'))
    } finally {
      if (requestRef.current === request) { pendingRef.current = null; setPolishing(false) }
    }
  }
  const restorePolish = () => {
    if (undoPolish && revisionRef.current === undoPolish.revision) changeInput(undoPolish.text)
  }
  const leaveDraftContext = () => {
    sendContextRef.current += 1
    invalidatePolish()
  }
  const openSource = (source: SourceTarget, trigger: HTMLElement) => {
    triggerRef.current = {
      element: trigger,
      index: Array.from(document.querySelectorAll('.rag-source-link')).indexOf(trigger),
    }
    setTarget(source)
  }
  const closeSource = () => {
    setTarget(null)
  }
  const chooseConversation = (id: string) => {
    leaveDraftContext()
    void switchConversation(id)
    setHistoryOpen(false)
  }

  const history = <Stack spacing={0.5} sx={{ height: '100%', p: 1.5, overflowY: 'auto' }}>
    <Button onClick={() => { leaveDraftContext(); newConversation(); setHistoryOpen(false) }} startIcon={<AddIcon />}
      disabled={loading}
      variant="text" sx={{ justifyContent: 'flex-start', color: 'text.primary', fontWeight: 600, mb: 2 }}>
      {t('rag.newConversation')}
    </Button>
    <Typography variant="overline" color="text.secondary" sx={{ px: 1.5 }}>
      {t('rag.conversations')}
    </Typography>
    {convs.length === 0 && <Typography variant="body2" color="text.secondary" sx={{ px: 1.5 }}>
      {t('rag.noConversations')}
    </Typography>}
    {convs.map(conversation => <Box key={conversation.id} sx={{ display: 'flex', alignItems: 'center',
      borderRadius: 2, bgcolor: conversation.id === activeId ? 'action.selected' : 'transparent',
      '&:hover': { bgcolor: 'action.hover' } }}>
      <Button onClick={() => chooseConversation(conversation.id)} disabled={loading}
        sx={{ flex: 1, minWidth: 0, color: 'text.primary', justifyContent: 'flex-start', textTransform: 'none',
          overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', px: 1.5 }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{conversation.title}</span>
      </Button>
      <Tooltip title={t('rag.deleteConversation')}>
        <IconButton size="small" aria-label={`${t('rag.deleteConversation')}: ${conversation.title}`}
          onClick={() => { if (conversation.id === activeId) leaveDraftContext(); void deleteConversation(conversation.id) }} disabled={loading}>
          <DeleteOutlineIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>)}
    {hasMore && <Button size="small" onClick={() => void loadMore()} disabled={loading}>
      {t('rag.loadMoreHistory')}
    </Button>}
    {cloud && legacyCount > 0 && <Button size="small" onClick={() => void importLegacy()} disabled={loading}
      sx={{ mt: 2, justifyContent: 'flex-start' }}>
      {t('rag.importHistory', { count: legacyCount })}
    </Button>}
  </Stack>

  return <Box sx={{ m: { xs: -2, md: -4 }, height: '100dvh', display: 'flex',
    bgcolor: 'background.default', overflow: 'hidden' }}>
    <Box component="aside" aria-label={t('rag.conversations')} sx={{ display: { xs: 'none', md: 'block' },
      width: 248, flexShrink: 0, borderRight: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
      {history}
    </Box>
    <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} anchor="left"
      PaperProps={{ sx: { width: 280, maxWidth: '85vw' } }}>
      {history}
    </Drawer>
    <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ height: 58, px: { xs: 2, md: 4 }, flexShrink: 0, display: 'flex', alignItems: 'center',
        gap: 1.5, borderBottom: 1, borderColor: 'divider' }}>
        <IconButton aria-label={t('rag.openHistory')} onClick={() => setHistoryOpen(true)}
          sx={{ display: { md: 'none' } }}><MenuIcon /></IconButton>
        <Typography fontWeight={600}>{t('rag.workspaceTitle')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
          {cloud ? (syncState === 'saved' ? t('rag.cloudSaved') : syncState === 'loading'
            ? t('rag.cloudSaving') : t('rag.cloudError')) : t('rag.localOnly')}
        </Typography>
      </Box>
      {syncError && <Alert severity="warning" sx={{ mx: { xs: 2, md: 4 }, mt: 1 }}>{syncError}</Alert>}
      <Box ref={chatBoxRef} sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: { xs: 2, md: 4 } }}>
        <Box sx={{ maxWidth: 820, mx: 'auto', py: 3 }}>
          {messages.length === 0 && <Box sx={{ textAlign: 'center', pt: { xs: 7, md: 12 }, pb: 5 }}>
            <Typography variant="h4" fontWeight={600} sx={{ mb: 1 }}>{t('rag.emptyTitle')}</Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>{t('rag.emptyHint')}</Typography>
            <Stack direction="row" flexWrap="wrap" justifyContent="center" gap={1}>
              {suggestions.map(item => <Chip key={item} label={item} onClick={() => changeInput(item)} />)}
            </Stack>
          </Box>}
          {messages.map((message, index) => {
            const userMessage = message.role === 'user'
            const streaming = loading && index === messages.length - 1 && !userMessage
            return <Box key={index} sx={{ display: 'flex', justifyContent: userMessage ? 'flex-end' : 'flex-start', mb: 3 }}>
              {userMessage ? <Box sx={{ bgcolor: 'action.hover', px: 2.25, py: 1.4, maxWidth: '82%',
                borderRadius: 3, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{message.content}</Box>
                : <Box sx={{ width: '100%', minWidth: 0, lineHeight: 1.8 }}>
                  {streaming ? <Typography sx={{ whiteSpace: 'pre-wrap' }}>{message.content ||
                    (statusLog.at(-1) || t('rag.waitingResponse'))}</Typography>
                    : message.content && <MarkdownMessage content={message.content} papers={papers}
                      paperSeqMap={paperSeqMap} onSourceOpen={openSource} />}
                  {message.citations?.filter(citation => citation.attribution).map((citation, i) =>
                    <Typography key={i} variant="caption" display="block" color="text.secondary" sx={{ mt: 1 }}>
                      {citation.attribution}
                    </Typography>)}
                  {index === messages.length - 1 && top10.length > 0 && <Box component="details" sx={{ mt: 2 }}>
                    <Box component="summary" sx={{ cursor: 'pointer', color: 'text.secondary' }}>{t('rag.retrievalEvidence')}</Box>
                    {top10.map((item: any, i) => <Typography key={i} variant="body2" sx={{ my: 0.5 }}>
                      {item.subject}: {item.object}
                    </Typography>)}
                  </Box>}
                  {index === messages.length - 1 && ideas.map((idea, i) =>
                    <EvidenceCard key={i} idea={idea} review={reviews[i]} paperSeqMap={paperSeqMap} />)}
                </Box>}
            </Box>
          })}
          {inspiration.active && inspiration.statusMessage && <Typography variant="body2" color="text.secondary">
            {inspiration.statusMessage}
          </Typography>}
        </Box>
      </Box>
      <Box sx={{ px: { xs: 2, md: 4 }, pt: 1.5, pb: { xs: 2, md: 3 }, flexShrink: 0 }}>
        <Box sx={{ maxWidth: 820, mx: 'auto', bgcolor: 'background.paper', border: 1, borderColor: 'divider',
          borderRadius: 3, boxShadow: '0 4px 18px rgba(15,23,42,.07)', px: 2, pt: 1.5, pb: 1 }}>
          <TextField fullWidth multiline minRows={2} maxRows={6} variant="standard"
            InputProps={{ disableUnderline: true }} inputProps={{ 'aria-label': t('rag.inputPlaceholder') }}
            error={inputTooLong} helperText={inputTooLong ? t('rag.promptTooLong') : undefined}
            placeholder={exploreMode ? t('rag.inputPlaceholderExplore') : t('rag.inputPlaceholder')}
            value={input} onChange={event => changeInput(event.target.value)} disabled={loading}
            onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void handleSend() } }} />
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, gap: 1 }}>
            <Button size="small" variant={exploreMode ? 'contained' : 'text'}
              onClick={() => setExploreMode(value => !value)} disabled={loading}>
              {t('rag.explore')}
            </Button>
            {undoPolish && <Button size="small" onClick={restorePolish}>{t('rag.undoPolish')}</Button>}
            <Box sx={{ flex: 1 }} />
            <Tooltip title={input.trim() ? t('rag.polishPrompt') : t('rag.polishNeedsText')}>
              <span><IconButton aria-label={t('rag.polishPrompt')} onClick={() => void handlePolish()}
                disabled={!input.trim() || inputTooLong || loading || polishing}>
                {polishing ? <CircularProgress size={20} /> : <AutoAwesomeOutlinedIcon />}
              </IconButton></span>
            </Tooltip>
            <IconButton aria-label={t('rag.send')} onClick={() => void handleSend()}
              disabled={!input.trim() || inputTooLong || loading} sx={{ bgcolor: 'primary.main', color: 'primary.contrastText',
                width: 38, height: 38, '&:hover': { bgcolor: 'primary.dark' },
                '&.Mui-disabled': { opacity: 0.35 } }}><SendIcon fontSize="small" /></IconButton>
          </Box>
          {polishError && <Alert severity="error" sx={{ mt: 1 }}>{polishError}</Alert>}
        </Box>
      </Box>
    </Box>
    <RagSourceDrawer target={target} onClose={closeSource}
      onExited={focusSource} />
  </Box>
}

export default RagPage
