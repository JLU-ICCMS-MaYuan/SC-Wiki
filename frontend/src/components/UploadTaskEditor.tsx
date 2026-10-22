import { createFieldDraftSaver, preserveRawNumbers } from '../lib/fieldDrafts'
import { currentEvidenceField, evidenceFieldsForStates } from '../lib/evidenceFields'
import { materialIdentityMissing } from '../lib/materialIdentity'
import { useEvidenceWorkflow, type EvidenceTarget } from './EvidenceWorkflow'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert, Autocomplete, Box, Button, Checkbox, Chip, CircularProgress,
  FormControl, FormHelperText, InputLabel, ListItemText, Menu, MenuItem, Select, TextField, Typography,
} from '@mui/material'
import { applyEvidencePatches } from '../lib/evidenceProposals'
import SaveIcon from '@mui/icons-material/Save'
import SendIcon from '@mui/icons-material/Send'
import { api, ApiError } from '../lib/api'
import {
  ClassificationCatalogs, ClassificationTerm, familyName, pendingSelection, selectionForTerm,
  loadClassificationCatalogs,
} from '../lib/classifications'
import { useLanguage } from '../context/LanguageContext'
import MaterialStatesEditor, { EvidenceNotes, SpaceGroupOption, ValidationIssue } from './MaterialStatesEditor'
import CitationExtractionPanel from './CitationExtractionPanel'
import PaperMetadataRow from './PaperMetadataRow'
import ReviewPaperTextField from './ReviewPaperTextField'
import {
  UploadDraft, normalizeUploadDraft, unwrapData,
} from '../lib/paperProcessing'
import { validateRecordClient, validateTcRecords } from '../lib/formDefinitions'
import EvidenceFieldMarkers, { readOnlyEvidenceFormSx } from './EvidenceFieldMarkers'
import PaperMaterialsSection from './PaperMaterialsSection'
import { researchMaterials } from '../lib/paperMaterials'
import PaperStructuralWorkspace from './PaperStructuralWorkspace'
import { mergeStructuralPreview } from '../lib/structuralRecords'

interface UploadTaskEditorProps {
  taskId: string
  onSubmitted: (paperId: number) => void
  draftOverride?: UploadDraft | null
  readOnly?: boolean
  statusNote?: string
  revisionPaperId?: number
}

interface RevisionDraftResponse {
  ok: boolean
  data: UploadDraft
  revision_id: string
  draft_version: number
  review_comment?: string
  warnings?: string[]
  conflict?: boolean
}

interface SubmitResponse {
  ok: boolean
  paper_id: number
  review_status: 'pending'
}

type AuthorRoleField = 'corresponding_authors' | 'co_first_authors'

// 枚举下拉不再携带中文 label：渲染时按 value 查 dict.enums.<组>.<value>（enums.ts）
const PAPER_TYPE_VALUES = ['theoretical', 'experimental', 'review', 'unknown'] as const
const SUPERCONDUCTOR_KIND_VALUES = ['conventional', 'unconventional', 'unknown'] as const

const toLines = (value: string[] | undefined) => (value || []).join('\n')
const fromLines = (value: string) => value.split(/[\n,，]/).map(item => item.trim()).filter(Boolean)

// 后端错误体为 FastAPI HTTPException：detail 可能是字符串或 {code, message} 对象。
// 提取具体原因；网络错误或无 detail 时返回 null，由调用方回退通用文案
const backendErrorReason = (reason: unknown): { message: string; code?: string } | null => {
  const detail = (reason as ApiError | null)?.detail
  if (typeof detail === 'string' && detail.trim()) return { message: detail }
  if (detail && typeof detail === 'object') {
    const { code, message } = detail as { code?: unknown; message?: unknown }
    if (typeof message === 'string' && message.trim()) {
      return { message, code: typeof code === 'string' && code ? code : undefined }
    }
    const nested = (detail as { detail?: unknown }).detail
    if (typeof nested === 'string' && nested.trim()) return { message: nested }
    if (nested && typeof nested === 'object') {
      const nestedMessage = (nested as { message?: unknown }).message
      const nestedCode = (nested as { code?: unknown }).code
      if (typeof nestedMessage === 'string' && nestedMessage.trim()) {
        return { message: nestedMessage, code: typeof nestedCode === 'string' ? nestedCode : undefined }
      }
    }
  }
  return null
}

// 保存/提交失败的横幅文案：优先展示后端具体原因（可附 code），否则回退通用文案
const failureMessage = (
  t: (key: string, vars?: Record<string, string | number>) => string,
  action: 'save' | 'submit',
  reason: unknown,
  fallback: string,
): string => {
  const reasonDetail = backendErrorReason(reason)
  if (!reasonDetail) return fallback
  return t('upload.failedWithDetail', {
    action: t(action === 'save' ? 'upload.saveAction' : 'upload.submitAction'),
    message: reasonDetail.message,
    code: reasonDetail.code ? t('upload.codeSuffix', { code: reasonDetail.code }) : '',
  })
}

// 后端部分校验规则前端没有（材料家族、压强区间、专用字段等），其 message 已写明
// 「第 N 个材料状态」。据此解析序号以便定位到卡片；解析不出时只显示横幅，不做定位。
// 该耦合依赖后端文案，由测试固定，文案变更时测试会立即失败。
const stateIndexFromMessage = (message: string): number | undefined => {
  const pathMatch = /material_states(?:\[|\.)(\d+)\]?/.exec(message)
  if (pathMatch) return Number(pathMatch[1])
  const ordinalMatch = /第\s*(\d+)\s*个材料状态/.exec(message)
  if (!ordinalMatch) return undefined
  const ordinal = Number(ordinalMatch[1])
  return Number.isSafeInteger(ordinal) && ordinal > 0 ? ordinal - 1 : undefined
}

const normalizeIssueField = (field: string): string => field.replace(
  /\.([0-9]+)(?=\.|$)/g,
  '[$1]',
)

const UploadTaskEditor: React.FC<UploadTaskEditorProps> = ({
  taskId, onSubmitted, draftOverride, readOnly = false, statusNote, revisionPaperId,
}) => {
  const { t, lang, dict } = useLanguage()
  const [draft, setDraft] = useState<UploadDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [revision, setRevision] = useState<RevisionDraftResponse | null>(null)
  const revisionMeta = useRef<RevisionDraftResponse | null>(null)
  const draftUrl = revisionPaperId ? `/api/rag/papers/${revisionPaperId}/revision-draft` : `/api/rag/upload-tasks/${taskId}/draft`
  const submitUrl = revisionPaperId ? `${draftUrl}/submit` : `/api/rag/upload-tasks/${taskId}/submit`
  const evidenceTarget: EvidenceTarget | undefined = readOnly ? undefined : revisionPaperId
    ? revision ? { target: 'revision', target_id: revision.revision_id } : undefined
    : { target: 'upload', target_id: taskId }
  const evidenceWorkflow = useEvidenceWorkflow({ target: evidenceTarget,
    readOnly,
    getCurrentValue: record => draft ? currentEvidenceField(record, { ...draft.paper }, draft.material_states) : undefined,
    saveCurrent: () => saveDraft(false, false),
  })
  const revisionIdentity = () => revisionMeta.current
    ? { revision_id: revisionMeta.current.revision_id, draft_version: revisionMeta.current.draft_version } : {}
  const fieldSaver = useRef<ReturnType<typeof createFieldDraftSaver> | null>(null)
  const persistDraft = useCallback(async (value: UploadDraft, _preparationId?: string) => {
    if (!fieldSaver.current) throw new Error(t('upload.draftMissing'))
    const result = await fieldSaver.current.save(value)
    if (revisionMeta.current && result.draft_version !== undefined) {
      revisionMeta.current = { ...revisionMeta.current, draft_version: result.draft_version }
      setRevision(revisionMeta.current)
    }
  }, [t])
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [error, setError] = useState('')
  // 本次提交发现的校验问题；驱动字段错误态与定位，提交成功或重新加载草稿时清空
  const [validationIssues, setIssues] = useState<ValidationIssue[]>([])
  const issues = validationIssues
  const reviewFields = evidenceFieldsForStates(evidenceWorkflow.issues, draft?.material_states || [])
  const [authorMenu, setAuthorMenu] = useState<{ author: string; anchorEl: HTMLElement } | null>(null)
  const [authorInput, setAuthorInput] = useState('')
  const [catalogs, setCatalogs] = useState<ClassificationCatalogs | null>(null)
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState('')
  const [spaceGroups, setSpaceGroups] = useState<SpaceGroupOption[]>([])
  const revisionRef = useRef(0)
  const currentEditor = useRef({ draft, loading, dirty, saving, submitting })
  currentEditor.current = { draft, loading, dirty, saving, submitting }
  const refreshEvidence = useRef(evidenceWorkflow.restore)
  refreshEvidence.current = evidenceWorkflow.restore

  useEffect(() => {
    let active = true
    setCatalogLoading(true)
    loadClassificationCatalogs()
      .then(value => {
        if (!active) return
        setCatalogs(value)
        setCatalogError('')
      })
      .catch((reason: Error) => {
        if (active) setCatalogError(reason.message || t('upload.catalogLoadFailed'))
      })
      .finally(() => {
        if (active) setCatalogLoading(false)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    api.get<{ space_groups?: SpaceGroupOption[] }>('/api/rag/space-groups')
      .then(response => {
        if (active) setSpaceGroups(Array.isArray(response?.space_groups) ? response.space_groups : [])
      })
      .catch(() => {
        // 空间群标准表不可用时降级为纯自由输入，不阻塞校对
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (draftOverride !== undefined) {
      const normalized = normalizeUploadDraft(draftOverride)
      if (revisionMeta.current || !revisionPaperId) { fieldSaver.current = createFieldDraftSaver(revisionMeta.current ? {target: 'revision', target_id: revisionMeta.current.revision_id} : {target: 'upload', target_id: taskId}); fieldSaver.current.initialize(normalized) }
      setDraft(normalized)
      setLoading(false)
      setDirty(false)
      setError('')
      setIssues([])
      return undefined
    }
    const controller = new AbortController()
    let cancelled = false
    setLoading(true)
    setDraft(null)
    revisionMeta.current = null
    setRevision(null)
    const request = revisionPaperId
      ? api.post<RevisionDraftResponse>(draftUrl)
      : api.get<{ ok: boolean; data: UploadDraft }>(draftUrl, { signal: controller.signal })
    request.then(response => {
      if (cancelled) return
      if (revisionPaperId) {
        revisionMeta.current = response as RevisionDraftResponse
        setRevision(response as RevisionDraftResponse)
      }
      const normalized = preserveRawNumbers(unwrapData(response), normalizeUploadDraft(unwrapData(response)))
      if (revisionMeta.current || !revisionPaperId) { fieldSaver.current = createFieldDraftSaver(revisionMeta.current ? {target: 'revision', target_id: revisionMeta.current.revision_id} : {target: 'upload', target_id: taskId}); fieldSaver.current.initialize(normalized) }
      setDraft(normalized)
      setDirty(false)
      setError('')
    }).catch((reason: Error) => {
      if (!cancelled && reason.name !== 'AbortError') setError(reason.message || t('upload.draftLoadFailed'))
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true; controller.abort() }
  }, [taskId, draftOverride, draftUrl, revisionPaperId])

  useEffect(() => {
    if (draftOverride !== undefined || readOnly || revisionPaperId) return undefined
    let disposed = false
    let refreshing = false
    let controller: AbortController | null = null
    const refresh = async () => {
      const editor = currentEditor.current
      if (document.visibilityState === 'hidden' || refreshing || !editor.draft || editor.loading
        || editor.dirty || editor.saving || editor.submitting || evidenceWorkflow.hasManualDrafts()) return
      const editVersion = revisionRef.current
      controller = new AbortController()
      refreshing = true
      try {
        const response = await api.get<{ ok: boolean; data: UploadDraft }>(draftUrl, { signal: controller.signal })
        const latest = currentEditor.current
        if (disposed || editVersion !== revisionRef.current || latest.dirty || latest.saving || latest.submitting || evidenceWorkflow.hasManualDrafts()) return
        const next = preserveRawNumbers(unwrapData(response), normalizeUploadDraft(unwrapData(response)))
        if (JSON.stringify(next) !== JSON.stringify(latest.draft)) {
          fieldSaver.current = createFieldDraftSaver({target: 'upload', target_id: taskId})
          fieldSaver.current.initialize(next)
          setDraft(next)
          setIssues([])
          setError('')
          setLastSavedAt(null)
        }
        void refreshEvidence.current({ target: 'upload', target_id: taskId })
      } catch {
        // 失焦后刷新失败时保留当前草稿，下一次获得焦点仍可重试。
      } finally {
        refreshing = false
      }
    }
    const onVisible = () => { if (document.visibilityState === 'visible') void refresh() }
    const onFocus = () => { void refresh() }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      disposed = true
      controller?.abort()
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [draftOverride, draftUrl, readOnly, revisionPaperId, taskId])

  const changeDraft = useCallback((updater: (current: UploadDraft) => UploadDraft) => {
    setDraft(current => current ? updater(current) : current)
    revisionRef.current += 1
    setDirty(true)
    setError('')
  }, [])

  const setPaperField = (field: keyof UploadDraft['paper'], value: unknown) => {
    evidenceWorkflow.invalidate(`paper.${field}`)
    changeDraft(current => ({ ...current,
      ...(field === 'material_families' ? { material_family_error: null } : {}),
      ...(field === 'research_motivation' ? { research_motivation_error: null } : {}),
      ...(field === 'summary' ? { summary_error: null } : {}),
      generation_issues: (current.generation_issues || []).filter(issue => issue.field !== `paper.${field}`),
      paper: { ...current.paper, [field]: value } }))
  }

  const setAuthors = (values: string[]) => {
    const authors = values.map(value => value.trim()).filter((value, index, all) => value && all.indexOf(value) === index)
    changeDraft(current => ({
      ...current,
      paper: {
        ...current.paper,
        authors,
        corresponding_authors: (current.paper.corresponding_authors || []).filter(author => authors.includes(author)),
        co_first_authors: (current.paper.co_first_authors || []).filter(author => authors.includes(author)),
      },
    }))
    if (authorMenu && !authors.includes(authorMenu.author)) setAuthorMenu(null)
  }

  const commitAuthorInput = (raw = authorInput) => {
    const author = raw.trim().replace(/[，,]+/g, '').trim()
    if (!author) { setAuthorInput(''); return }
    const authors = draft?.paper.authors || []
    if (!authors.includes(author)) setAuthors([...authors, author])
    setAuthorInput('')
  }

  const toggleAuthorRole = (field: AuthorRoleField, author: string) => {
    changeDraft(current => {
      const selected = current.paper[field] || []
      return {
        ...current,
        paper: {
          ...current.paper,
          [field]: selected.includes(author)
            ? selected.filter(item => item !== author)
            : [...selected, author],
        },
      }
    })
  }

  const setDraftField = (field: keyof UploadDraft, value: unknown) => {
    if (field === 'material_states' && JSON.stringify(researchMaterials(draft?.material_states || [])) !== JSON.stringify(researchMaterials(value as UploadDraft['material_states']))) evidenceWorkflow.invalidate('paper.research_materials')
    changeDraft(current => ({ ...current, [field]: value, ...(field === 'material_states' ? { paper: { ...current.paper, research_materials: researchMaterials(value as UploadDraft['material_states']) } } : {}) }))
  }

  const saveDraft = useCallback(async (showResult = false, _syncEvidence = true, reportFailure = false): Promise<boolean> => {
    if (!draft || saving || readOnly || revision?.conflict) return false
    if (!dirty) return true
    const editVersion = revisionRef.current
    setSaving(true)
    try {
      await persistDraft(draft)
      if (editVersion === revisionRef.current) setDirty(false)
      setLastSavedAt(new Date().toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' }))
      if (showResult) setError('')
      return true
    } catch (reason) {
      const message = failureMessage(t, 'save', reason, t('upload.draftSaveFailed'))
      setError(message)
      if (reportFailure) throw new Error(message)
      return false
    } finally {
      setSaving(false)
    }
  }, [dirty, draft, saving, readOnly, t, lang, persistDraft, revision?.conflict])

  useEffect(() => {
    if (!dirty || !draft || saving || submitting || revision?.conflict) return
    const timer = window.setTimeout(() => { void saveDraft(false) }, 5000)
    return () => window.clearTimeout(timer)
  }, [dirty, draft, saveDraft, saving, submitting, revision?.conflict])

  // 详情会在独立标签页中打开；关闭、刷新或返回前保护尚未完成保存的主表单。
  useEffect(() => {
    if (readOnly || (!dirty && !saving && !submitting)) return
    const protect = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [readOnly, dirty, saving, submitting])

  // 返回全部问题而不是遇到第一条就退出：用户需要一次看清所有待补字段，
  // 而不是每修一条再提交一次才发现下一条
  const validate = (): ValidationIssue[] => {
    if (!draft) return []
    const issues: ValidationIssue[] = []
    if (!draft.paper.title?.trim()) {
      issues.push({ field: 'paper.title', message: t('upload.titleRequired') })
    }
    if (draft.paper.doi && !/^10\.\d{4,9}\/\S+$/i.test(draft.paper.doi.trim())) {
      issues.push({ field: 'paper.doi', message: t('upload.doiInvalid') })
    }
    if (!draft.paper.paper_type || draft.paper.paper_type === 'unknown') {
      issues.push({ field: 'paper.paper_type', message: t('upload.paperTypeRequired') })
    }
    if (draft.paper.paper_type === 'theoretical' && !draft.paper.theoretical_subtype) {
      issues.push({ field: 'paper.theoretical_subtype', message: t('upload.theoreticalSubtypeRequired') })
    }
    if (!draft.paper.material_families?.length) {
      issues.push({ field: 'paper.material_families', message: t('upload.materialFamilyRequired') })
    }
    if (draft.paper.paper_type !== 'review' && draft.material_states.length === 0) {
      issues.push({ field: 'material_states', message: t('upload.materialStateRequired') })
    }
    draft.material_states.forEach((state, stateIndex) => {
      const label = t('upload.materialStateLabel', { index: stateIndex + 1 })
      if (materialIdentityMissing(state)) {
        issues.push({ stateIndex, field: `material_states[${stateIndex}].material_name`, message: t('upload.missingMaterial', { label }) })
      }
      if (state.reported_space_group_number != null &&
        (state.reported_space_group_number < 1 || state.reported_space_group_number > 230)) {
        issues.push({
          stateIndex,
          field: `material_states[${stateIndex}].reported_space_group_number`,
          message: t('upload.spaceGroupRangeInvalid', { label }),
        })
      }
      if ([state.calculation_context?.lambda_ep, state.calculation_context?.omega_log_k, state.calculation_context?.mu_star]
        .some(value => value != null && value < 0)) {
        issues.push({
          stateIndex,
          field: `material_states[${stateIndex}].calculation_context`,
          message: t('upload.negativeCalcParam', { label }),
        })
      }
      const invalidTc = (state.tc_results || []).findIndex(item =>
        !item.value_raw?.trim() && item.tc_value_k == null && (item.tc_min_k == null || item.tc_max_k == null))
      if (invalidTc >= 0) {
        issues.push({
          stateIndex,
          field: `material_states[${stateIndex}].tc_results`,
          message: t('upload.tcMissingValue', { label, n: invalidTc + 1 }),
        })
      }
      const invalidProperty = (state.properties || []).findIndex(item =>
        !String(item.name || item.name_raw || '').trim() ||
        (!item.value_raw?.trim() && item.value == null && item.value_min == null && item.value_max == null))
      if (invalidProperty >= 0) {
        issues.push({
          stateIndex,
          field: `material_states[${stateIndex}].properties`,
          message: t('upload.propertyIncomplete', { label, n: invalidProperty + 1 }),
        })
      }
      for (const [moduleIndex, module] of (state.property_modules || []).entries()) {
        for (const [recordIndex, record] of module.records.entries()) {
          for (const issue of validateRecordClient(record)) {
            issues.push({
              stateIndex,
              field: `material_states[${stateIndex}].property_modules[${moduleIndex}].records[${recordIndex}].${issue.field}`,
              message: issue.message,
            })
          }
        }
      }
    })
    return issues
  }

  // 把出错位置暴露给用户：展开可能被折叠的卡片（MaterialStatesEditor 收到 issues 后展开），
  // 再滚动并聚焦到第一个出错字段
  const revealIssues = (nextIssues: ValidationIssue[]) => {
    setIssues(nextIssues)
    const first = nextIssues[0]
    if (!first) return
    // 等展开后的 DOM 就绪再定位，否则折叠中的字段无法滚动到位
    window.setTimeout(() => {
      const anchor = document.querySelector<HTMLElement>(`[data-issue-field="${first.field}"]`)
      if (!anchor) return
      // 少数旧浏览器与内嵌 WebView 没有 scrollIntoView；缺失时仅聚焦，不能让定位逻辑抛错
      anchor.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
      const focusable = anchor.matches('input,textarea,select')
        ? anchor
        : anchor.querySelector<HTMLElement>('input,textarea,select,[tabindex]')
      focusable?.focus()
    }, 0)
  }

  const submit = async () => {
    if (!evidenceTarget) return
    const validationIssues = validate()
    if (validationIssues.length > 0) {
      setError(validationIssues.map(item => item.message).join(t('upload.sentenceSeparator')))
      revealIssues(validationIssues)
      return
    }
    setIssues([])
    setSubmitting(true)
    try {
      if (!(await saveDraft(false))) return
      const evidencePayload = await evidenceWorkflow.gate(evidenceTarget)
      if (!evidencePayload) return
      let response: SubmitResponse | { data: SubmitResponse }
      try {
        response = await api.post<SubmitResponse | { data: SubmitResponse }>(submitUrl, { ...evidencePayload, ...revisionIdentity() })
      } catch (reason) {
        const apiError = reason as ApiError
        if (apiError.code !== 'consistency_ack_required' || !window.confirm(t('upload.consistencyConfirm'))) throw reason
        response = await api.post<SubmitResponse | { data: SubmitResponse }>(
          submitUrl,
          { ...evidencePayload, ...revisionIdentity(), consistency_acknowledged: true },
        )
      }
      onSubmitted(unwrapData(response).paper_id)
    } catch (reason) {
      const apiError = reason as ApiError
      if (apiError.status === 409 && apiError.existingPaperId) {
        setError(t('upload.doiExists', { id: apiError.existingPaperId }))
      } else {
        const issueMessages = apiError.issues?.map(issue => issue.message).filter(Boolean) || []
        const feedbackReason = issueMessages.length > 0
          ? { detail: { code: apiError.code, message: issueMessages.join(t('upload.sentenceSeparator')) } }
          : reason
        setError(failureMessage(t, 'submit', feedbackReason, t('upload.submitReviewFailed')))
        if (apiError.issues?.length) {
          const normalizedIssues = apiError.issues.map(issue => ({
            field: normalizeIssueField(issue.field),
            stateIndex: stateIndexFromMessage(issue.field),
            message: issue.message,
          }))
          revealIssues(normalizedIssues)
          return
        }
        // 后端独有的校验规则（材料家族、压强区间等）也要能定位到卡片
        const backendReason = apiError.status === 400 ? backendErrorReason(reason) : null
        const backendStateIndex = backendReason ? stateIndexFromMessage(backendReason.message) : undefined
        if (backendStateIndex != null) {
          revealIssues([{
            stateIndex: backendStateIndex,
            field: `material_states[${backendStateIndex}].material`,
            message: backendReason!.message,
          }])
        }
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}><CircularProgress /></Box>
  }
  if (!draft) return <Alert severity="error">{error || t('upload.draftMissing')}</Alert>

  // 统一给出错字段加定位锚点、错误态与说明文字，避免每处重复拼装
  const issueOf = (field: string) => issues.find(item => item.field === field)
  const hasIssue = (field: string) => Boolean(issueOf(field))
  const issueProps = (field: string) => {
    const issue = issueOf(field)
    return {
      'data-issue-field': field,
      error: Boolean(issue),
      helperText: issue?.message,
    }
  }
  // Select/复合区域用不了 TextField 的 helperText，单独渲染说明文字
  const IssueText: React.FC<{ field: string }> = ({ field }) => {
    const issue = issueOf(field)
    if (!issue) return null
    return <FormHelperText error>{issue.message}</FormHelperText>
  }
  const classificationEvidence = draft.classification_evidence || []

  return (
    <Box component="fieldset" data-evidence-scope="upload-editor" disabled={submitting || Boolean(revision?.conflict)} sx={{ mt: 3, border: 0, p: 0, minWidth: 0 }}>
      {!!draft.parsing_conflicts?.length && <Alert severity="warning" sx={{ mb: 2 }}>
        {t('upload.parsingDifferences', { count: draft.parsing_conflicts.length })}
        <details><summary>{t('upload.viewParsingDifferences')}</summary>
          {draft.parsing_conflicts.map((item, index) => <Box key={index} sx={{ mt: 1, overflowWrap: 'anywhere' }}>
            <Typography variant="caption">{item.file_id} · {t('upload.sourcePage', { page: item.pdf_page })}</Typography>
            {item.engine && <Typography variant="caption">{item.engine}</Typography>}
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{item.selected_text}</Typography>
            {item.alternatives.map((alternative, i) => <Box key={i}>
              {alternative.engine && <Typography variant="caption">{alternative.engine}</Typography>}
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: 'text.secondary' }}>{alternative.text}</Typography>
            </Box>)}
          </Box>)}
        </details>
      </Alert>}
      {!!draft.bibliography_conflicts?.length && <Alert severity="info" sx={{ mb: 2 }}>
        <details><summary>{t('upload.bibliographyDifferences')}</summary>
          {draft.bibliography_conflicts.map((item, index) => <Box key={index} sx={{ mt: 1, overflowWrap: 'anywhere' }}>
            <Typography variant="caption">{item.field}</Typography>
            <Typography variant="body2">GROBID: {JSON.stringify(item.grobid_value)}</Typography>
            <Typography variant="body2">{t('upload.extractedCandidate')}: {JSON.stringify(item.extracted_value)}</Typography>
          </Box>)}
        </details>
      </Alert>}
      {revision && <Alert severity="info" sx={{ mb: 2 }}>{t('paperDetail.revisionNotice')}</Alert>}
      {revision?.review_comment && <Alert severity="warning" sx={{ mb: 2 }}>{revision.review_comment}</Alert>}
      {revision?.warnings?.map(warning => <Alert key={warning} severity="warning" sx={{ mb: 2 }}>{warning}</Alert>)}
      {revision?.conflict && <Alert severity="error" sx={{ mb: 2 }}>{t('paperDetail.revisionConflict')}</Alert>}
      {evidenceWorkflow.dialog}
      <EvidenceFieldMarkers records={evidenceWorkflow.records} scope="upload-editor" onOpen={evidenceWorkflow.openIssue} onChange={evidenceWorkflow.invalidate} />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h6" fontWeight={700}>{revisionPaperId ? t('paperDetail.revisionTitle') : readOnly ? t('upload.aiDraftTitle') : t('upload.checkAiDraftTitle')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {readOnly ? (statusNote || t('upload.defaultNote')) : t('upload.editorSubtitle')}
          </Typography>
        </Box>
        {readOnly ? (
          <Chip size="small" color="info" label={t('upload.readOnlyBadge')} />
        ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="caption" color={error ? 'error' : 'text.secondary'}>
            {saving ? t('common.saving') : dirty ? t('upload.autoSaveHint') : lastSavedAt ? t('upload.savedAt', { time: lastSavedAt }) : t('upload.draftLoaded')}
          </Typography>
          {evidenceWorkflow.automaticView?.phase === 'error' && (
            <Button variant="outlined" disabled={saving || submitting || Boolean(revision?.conflict)} onClick={evidenceWorkflow.showResults}>{t('evidence.viewResults')}</Button>
          )}
          <Button variant="outlined" startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
            disabled={saving || submitting || Boolean(revision?.conflict)} onClick={() => void saveDraft(true)}>{t('upload.saveNow')}</Button>
          <Button variant="contained" startIcon={submitting ? <CircularProgress size={16} /> : <SendIcon />}
            disabled={saving || submitting || Boolean(revision?.conflict)} onClick={() => void submit()}>{revisionPaperId ? t('paperDetail.resubmit') : t('upload.submitReview')}</Button>
        </Box>
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {evidenceWorkflow.automaticView && <Alert severity={evidenceWorkflow.automaticView.phase === 'error' ? 'warning' : 'info'} role="status" sx={{ mb: 2 }}>
        {evidenceWorkflow.automaticView.phase === 'error'
          ? t('upload.evidenceCheckFailed', { message: evidenceWorkflow.automaticView.message || '' })
          : evidenceWorkflow.automaticView.message || t('evidence.checking')}
      </Alert>}
      {draft.field_suggestions_error && evidenceWorkflow.records.some(r => r.status === 'unchecked') && <Alert severity="warning" sx={{ mb: 2 }}>{t('evidence.generationFailed')}</Alert>}
      {Boolean(draft.generation_issues?.length) && <Alert severity="warning" sx={{ mb: 2 }}>
        <strong>{t('upload.generationIssuesTitle')}</strong>
        <Box component="ul" sx={{ my: 0.5, pl: 2 }}>
          {draft.generation_issues?.map((issue, index) => <li key={`${issue.field}:${issue.code}:${index}`}>
            {issue.field}: {issue.message}
            {issue.candidate != null && <Box component="div" sx={{ whiteSpace: 'pre-wrap', maxHeight: 180, overflow: 'auto' }}>
              {t('upload.generationPendingCandidate')}: {typeof issue.candidate === 'string'
                ? issue.candidate : JSON.stringify(issue.candidate)}
            </Box>}
          </li>)}
        </Box>
      </Alert>}

      {draft.citation_extraction && <CitationExtractionPanel extraction={draft.citation_extraction} />}

      <Box sx={readOnly ? readOnlyEvidenceFormSx : undefined}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, '& > *': { minWidth: 0 } }}>
        <Box sx={{ gridColumn: '1 / -1' }}>
          <ReviewPaperTextField fullWidth label={t('upload.title')} value={draft.paper.title || ''} readOnly={readOnly} disabled={submitting || Boolean(revision?.conflict)}
            {...issueProps('paper.title')}
            onValueChange={value => setPaperField('title', value)} />
        </Box>
        <Box sx={{ gridColumn: '1 / -1' }}>
          <Autocomplete
            multiple
            freeSolo
            forcePopupIcon={false}
            options={draft.paper.authors || []}
            value={draft.paper.authors || []}
            inputValue={authorInput}
            onInputChange={(_, value, reason) => { if (reason !== 'reset') setAuthorInput(value) }}
            onClose={(_, reason) => { if (reason === 'blur') commitAuthorInput() }}
            onChange={(_, values) => { setAuthors(values); setAuthorInput('') }}
            renderTags={(values, getTagProps) => values.map((author, index) => {
              const { key, ...tagProps } = getTagProps({ index })
              const roles = [
                draft.paper.corresponding_authors?.includes(author) ? t('upload.correspondingAuthor') : '',
                draft.paper.co_first_authors?.includes(author) ? t('upload.coFirstAuthor') : '',
              ].filter(Boolean)
              return (
                <Chip
                  {...tagProps}
                  key={key}
                  label={[author, ...roles].join(' · ')}
                  title={t('upload.setAuthorRoleTitle')}
                  onClick={event => setAuthorMenu({ author, anchorEl: event.currentTarget })}
                  onDelete={() => setAuthors(values.filter(item => item !== author))}
                />
              )
            })}
            renderInput={params => (
              <TextField {...params} data-issue-field="paper.authors" label={t('upload.authorsField')} placeholder={(draft.paper.authors || []).length ? '' : t('upload.authorPlaceholder')} onKeyDown={event => { if ((event.key === 'Enter' || event.key === ',' || event.key === '，') && authorInput.trim()) { event.preventDefault(); commitAuthorInput() } }} />
            )}
            sx={{
              '& .MuiOutlinedInput-root': {
                flexWrap: 'nowrap',
                overflowX: 'auto',
                overflowY: 'hidden',
                scrollbarWidth: 'thin',
              },
              '& .MuiAutocomplete-tag': { flexShrink: 0 },
              '& .MuiAutocomplete-input': { minWidth: '10ch !important' },
            }}
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            {(['corresponding_authors', 'co_first_authors'] as const).map(field => {
              const record = evidenceWorkflow.records.find(r => r.field === `paper.${field}`)
              return record ? <Button key={field} size="small" onClick={() => evidenceWorkflow.openIssue(record.key)}>{field === 'corresponding_authors' ? '通讯作者' : '共同第一作者'} · 来源核对</Button> : null
            })}
          </Box>
          <Menu anchorEl={authorMenu?.anchorEl} open={Boolean(authorMenu)} onClose={() => setAuthorMenu(null)}>
            {authorMenu && ([
              ['corresponding_authors', t('upload.correspondingAuthor')],
              ['co_first_authors', t('upload.coFirstAuthor')],
            ] as const).map(([field, label]) => (
              <MenuItem key={field} onClick={() => toggleAuthorRole(field, authorMenu.author)}>
                <Checkbox checked={(draft.paper[field] || []).includes(authorMenu.author)} />
                <ListItemText primary={label} />
              </MenuItem>
            ))}
          </Menu>
        </Box>
        <PaperMetadataRow
          journal={<TextField data-issue-field="paper.journal" label={t('upload.journal')} value={draft.paper.journal || ''}
            onChange={event => setPaperField('journal', event.target.value)} />}
          year={<TextField data-issue-field="paper.year" label={t('upload.year')} type="number" value={draft.paper.year ?? ''}
            onChange={event => setPaperField('year', event.target.value ? Number(event.target.value) : null)} />}
          issueNumber={<TextField label={t('upload.issueNumber')} value={draft.paper.issue_number || ''}
            {...issueProps('paper.issue_number')}
            slotProps={{ htmlInput: { maxLength: 100 } }}
            onChange={event => setPaperField('issue_number', event.target.value)} />}
          volume={<TextField data-issue-field="paper.volume" label={t('upload.volume')} value={draft.paper.volume || ''}
            onChange={event => setPaperField('volume', event.target.value)} />}
          pages={<TextField data-issue-field="paper.pages" label={t('upload.pages')} value={draft.paper.pages || ''}
            onChange={event => setPaperField('pages', event.target.value)} />}
          doi={<TextField label="DOI" value={draft.paper.doi || ''}
            {...issueProps('paper.doi')}
            onChange={event => setPaperField('doi', event.target.value.trim())} />}
        />
      </Box>

      <PaperMaterialsSection states={draft.material_states} historicalMaterials={draft.paper.research_materials} />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mt: 2, '& > *': { minWidth: 0 } }}>
        <FormControl fullWidth error={hasIssue('paper.paper_type')} data-issue-field="paper.paper_type">
          <InputLabel>{t('upload.paperTypeField')}</InputLabel>
          <Select label={t('upload.paperTypeField')} value={draft.paper.paper_type || 'unknown'}
            onChange={event => setPaperField('paper_type', event.target.value)}>
            {PAPER_TYPE_VALUES.map(value => <MenuItem key={value} value={value}>{dict.enums.paperType[value]}</MenuItem>)}
          </Select>
          <IssueText field="paper.paper_type" />
          <EvidenceNotes evidence={classificationEvidence} />
        </FormControl>
        <FormControl fullWidth disabled={draft.paper.paper_type !== 'theoretical'}
          error={hasIssue('paper.theoretical_subtype')} data-issue-field="paper.theoretical_subtype">
          <InputLabel>{t('upload.theoreticalSubtypeField')}</InputLabel>
          <Select label={t('upload.theoreticalSubtypeField')} value={draft.paper.theoretical_subtype || ''}
            onChange={event => setPaperField('theoretical_subtype', event.target.value || null)}>
            <MenuItem value="calculation">{dict.enums.theoreticalSubtype.calculation}</MenuItem>
            <MenuItem value="method">{dict.enums.theoreticalSubtype.method}</MenuItem>
            <MenuItem value="theory">{dict.enums.theoreticalSubtype.theory}</MenuItem>
          </Select>
          <IssueText field="paper.theoretical_subtype" />
          {draft.paper.paper_type === 'theoretical' && !draft.paper.theoretical_subtype && draft.theoretical_subtype_assessment?.status !== 'completed' &&
            <FormHelperText>{draft.theoretical_subtype_assessment?.reason || t('upload.subtypeAssessmentMissing')}</FormHelperText>}
          {draft.paper.paper_type === 'theoretical' && draft.theoretical_subtype_assessment?.status === 'completed' &&
            draft.paper.theoretical_subtype !== draft.theoretical_subtype_assessment.value &&
            <FormHelperText>{t('upload.subtypeAssessmentConflict', { value: dict.enums.theoreticalSubtype[draft.theoretical_subtype_assessment.value as 'calculation' | 'method' | 'theory'] || draft.theoretical_subtype_assessment.value || '' })}</FormHelperText>}
        </FormControl>
        <FormControl fullWidth data-issue-field="paper.superconductor_kind">
          <InputLabel id="paper-superconductor-kind-label">{t('upload.superconductorKindField')}</InputLabel>
          <Select labelId="paper-superconductor-kind-label" label={t('upload.superconductorKindField')} value={draft.paper.superconductor_kind || 'unknown'}
            onChange={event => setPaperField('superconductor_kind', event.target.value)}>
            {SUPERCONDUCTOR_KIND_VALUES.map(value => (
              <MenuItem key={value} value={value}>{dict.enums.superconductorKind[value]}</MenuItem>
            ))}
          </Select>
          <EvidenceNotes evidence={classificationEvidence} />
        </FormControl>
        <Box data-issue-field="paper.material_families">
          <Autocomplete<ClassificationTerm | string, true, false, true>
            multiple
            freeSolo
            options={catalogs?.material_families || []}
            loading={catalogLoading}
            value={(draft.paper.material_families || []).map(selection => {
              if (selection.id == null) return selection.name
              return catalogs?.material_families?.find(item => item.id === selection.id) || selection.name
            })}
            getOptionLabel={option => typeof option === 'string' ? option : familyName(option, lang)}
            isOptionEqualToValue={(option, value) => (
              typeof option !== 'string' && typeof value !== 'string' && option.id === value.id
            )}
            onChange={(_, values) => setPaperField('material_families', values.map(value => (
              typeof value === 'string' ? pendingSelection(value) : selectionForTerm(value)
            )).filter(Boolean))}
            renderInput={params => (
              <TextField
                {...params}
                label={t('upload.materialFamilyField')}
                error={hasIssue('paper.material_families') || Boolean(catalogError || draft.material_family_error)}
                helperText={catalogError || (draft.material_family_error === 'catalog_unavailable'
                  ? t('upload.materialFamilyCatalogUnavailable')
                  : draft.material_family_error === 'classification_failed'
                    ? t('upload.materialFamilyInferenceFailed')
                    : draft.material_family_error === 'insufficient_evidence'
                      ? t('upload.materialFamilyEvidenceInsufficient')
                      : issues.find(item => item.field === 'paper.material_families')?.message) || undefined}
              />
            )}
          />
          <EvidenceNotes evidence={classificationEvidence} />
        </Box>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mt: 2, '& > *': { minWidth: 0 } }}>
        {[
          ['keywords_tags', t('upload.keywordsLabel')],
          ['methodology', t('upload.methodologyLabel')],
        ].map(([field, label]) => (
          <Box key={field}>
            <ReviewPaperTextField fullWidth label={label} multiline rows={15} data-issue-field={`paper.${field}`} readOnly={readOnly} disabled={submitting || Boolean(revision?.conflict)}
              value={toLines(draft.paper[field as keyof UploadDraft['paper']] as string[] | undefined)}
              onValueChange={value => setPaperField(field as keyof UploadDraft['paper'], fromLines(value))}
              helperText={field === 'keywords_tags'
                ? draft.paper.keywords_tags?.length
                  ? draft.keyword_assessment?.kind === 'author_list' && JSON.stringify(draft.keyword_assessment.values) === JSON.stringify(draft.paper.keywords_tags)
                    ? t('upload.keywordsAuthorHint') : t('upload.keywordsAiHint')
                  : draft.keyword_assessment?.reason || t('upload.keywordsMissingHint')
                : undefined} />
            <EvidenceNotes
              evidence={draft.field_evidence?.[field]}
            />
          </Box>
        ))}
      </Box>

      {[
        ['abstract', t('upload.abstractLabel'), 4],
        ['summary', t('upload.summaryLabel'), 3],
        ['key_finding', t('upload.keyFindingLabel'), 3],
      ].map(([field, label, rows]) => (
        <Box key={String(field)} sx={{ mt: 2 }}>
          <ReviewPaperTextField fullWidth label={String(label)} multiline minRows={Number(rows)} data-issue-field={`paper.${field}`} readOnly={readOnly} disabled={submitting || Boolean(revision?.conflict)}
            value={String(draft.paper[field as keyof UploadDraft['paper']] || '')}
            onValueChange={value => setPaperField(field as keyof UploadDraft['paper'], value)}
            helperText={field === 'summary' && (!draft.paper.summary || draft.summary_error)
              ? t('upload.summaryReviewHint') : undefined} />
        </Box>
      ))}

      <Box sx={{ mt: 2 }}>
        <ReviewPaperTextField fullWidth label={t('upload.researchMotivationLabel')} multiline minRows={3} data-issue-field="paper.research_motivation" readOnly={readOnly} disabled={submitting || Boolean(revision?.conflict)}
          value={draft.paper.research_motivation || ''}
          onValueChange={value => setPaperField('research_motivation', value)}
          helperText={draft.research_motivation_error
            ? t('upload.researchMotivationReviewHint') : undefined} />
        <EvidenceNotes evidence={classificationEvidence} />
      </Box>

      <MaterialStatesEditor
        independentStructureWorkspace
        propertySpectra={{ target: revisionPaperId && revisionMeta.current
          ? { target: 'revision', target_id: revisionMeta.current.revision_id }
          : { target: 'upload', target_id: taskId }, beforeNavigate: async () => {
            if (readOnly) return true
            if (evidenceWorkflow.hasManualDrafts()) throw new Error('请先保存或处理来源核对中的人工修改草稿，再打开谱详情。')
            if (!dirty && !saving && !submitting) return true
            const version = revisionRef.current
            const saved = await saveDraft(true, true, true)
            return saved && version === revisionRef.current
          } }}
        spectrumTarget={revisionPaperId && revisionMeta.current
          ? { target: 'revision', target_id: revisionMeta.current.revision_id }
          : { target: 'upload', target_id: taskId }}
        beforeSpectrumEdit={() => saveDraft(false)}
        onScientificEdit={evidenceWorkflow.invalidate}
        states={draft.material_states}
        onChange={nextStates => setDraftField('material_states', nextStates)}
        catalogs={catalogs}
        catalogLoading={catalogLoading}
        catalogError={catalogError}
        readOnly={readOnly || submitting}
        issues={issues}
        reviewFields={reviewFields}
        structureCandidates={draft.structure_candidates || []}
        onStructureCandidatesChange={next => setDraftField('structure_candidates', next)}
        spaceGroups={spaceGroups}
        taskId={taskId}
        onUploadStructure={revisionPaperId ? async (index, file) => {
          if (!draft || !(await saveDraft(false)) || !revisionMeta.current) return
          const body = new FormData()
          body.append('file', file)
          body.append('material_state_index', String(index))
          body.append('revision_id', revisionMeta.current.revision_id)
          const result = await api.post<{ ok: boolean; data: import('../lib/paperProcessing').StructureCandidate }>(`${draftUrl}/structure-candidates`, body)
          changeDraft(current => ({ ...current, structure_candidates: [...(current.structure_candidates || []), unwrapData(result)] }))
        } : undefined}
        paperType={draft.paper.paper_type}
        superconductorKind={draft.paper.superconductor_kind}
        onError={setError}
      />
      <PaperStructuralWorkspace candidates={draft.structure_candidates || []} observations={draft.structural_observations || []}
        readOnly={readOnly || submitting} issues={draft.structural_extraction_issues || []}
        onCandidates={values => setDraftField('structure_candidates', values)}
        onObservations={values => setDraftField('structural_observations', values)}
        onReextract={readOnly ? undefined : async () => {
          if (evidenceWorkflow.hasManualDrafts()) throw new Error('请先保存来源核对中的人工修改，再读取结构资料。')
          if (!(await saveDraft(true, true, true))) throw new Error('主表单尚未保存，请稍后重试。')
          const version = revisionRef.current
          const result = await api.post<any>('/api/rag/structural-records/reextract', revisionPaperId && revisionMeta.current
            ? { target: 'revision', target_id: revisionMeta.current.revision_id } : { target: 'upload', target_id: taskId })
          return { ...result, editor_version: version }
        }}
        onApplyPreview={value => {
          if (value.editor_version !== revisionRef.current) throw new Error('表单在读取期间已变化，请重新读取；当前输入已保留。')
          changeDraft(current => ({ ...current,
            structure_candidates: mergeStructuralPreview(current.structure_candidates || [], value.structure_candidates),
            structural_observations: mergeStructuralPreview(current.structural_observations || [], value.structural_observations),
            structural_extraction_issues: value.structural_extraction_issues,
            structural_extraction_version: value.structural_extraction_version,
          }))
        }} />
    </Box>
    </Box>
  )
}

export default UploadTaskEditor
