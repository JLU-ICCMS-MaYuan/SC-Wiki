import { createFieldDraftSaver } from '../lib/fieldDrafts'
import { currentEvidenceField, evidenceFieldsForStates } from '../lib/evidenceFields'
import { materialIdentityMissing } from '../lib/materialIdentity'
import { materialStateFromDetail, candidateFromStructureModel, remapScientificIdentities, type ScientificIdentityMap } from '../lib/paperEditing'
import { applyEvidencePatches, type EvidencePatch } from '../lib/evidenceProposals'
import EvidenceFieldMarkers from '../components/EvidenceFieldMarkers'
import PaperMaterialsSection from '../components/PaperMaterialsSection'
import { researchMaterials } from '../lib/paperMaterials'
import { useEvidenceWorkflow } from '../components/EvidenceWorkflow'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Autocomplete, Box, Button, Checkbox, Chip, CircularProgress, Container, FormControl, FormControlLabel, IconButton,
  InputLabel, MenuItem, Select, Snackbar, TextField, Typography,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import { useNavigate, useParams } from 'react-router-dom'
import PaperReviewStatusSelect from '../components/PaperReviewStatusSelect'
import { initialPaperReviewStatus, loadPaperReviewSource, resolveReviewClassifications, paperReviewPayload, type ReviewClassifications } from '../lib/paperReview'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import {
  ClassificationCatalogs, ClassificationTerm, FamilySelection, familyName,
  loadClassificationCatalogs, pendingSelection, selectionForTerm,
} from '../lib/classifications'
import { DraftMaterialState, StructureCandidate, unwrapData } from '../lib/paperProcessing'
import MaterialStatesEditor, { SpaceGroupOption } from '../components/MaterialStatesEditor'
import PaperStructuralWorkspace from '../components/PaperStructuralWorkspace'
import type { LatticeObservation } from '../lib/structuralRecords'
import PaperMetadataRow from '../components/PaperMetadataRow'
import ReviewPaperTextField from '../components/ReviewPaperTextField'
import { useLanguage } from '../context/LanguageContext'
import { convertLegacyPropertyModules, PROPERTY_SCHEMA_VERSION } from '../lib/propertyModules'
import { validateTcRecords } from '../lib/formDefinitions'
import { textLinesToList, toTextList } from '../lib/paperTextLists'

const SUPERCONDUCTOR_KIND_VALUES = ['conventional', 'unconventional', 'unknown'] as const

const appendAuthor = (authors: string[], input: string): string[] => {
  const name = input.trim()
  return name && !authors.includes(name) ? [...authors, name] : authors
}

/**
 * 管理端论文编辑独立页（Issue #78，路由 /admin/papers/:id/edit）。
 * 由原 AdminPage 编辑弹窗迁移而来：论文级字段、科学数据（MaterialStatesEditor）、
 * 审核区与两段保存全部保留，容器从 Dialog 改为页面；
 * 并新增已落库结构的完整表示加载（晶胞/格式切换与下载，FR-004/FR-005/FR-006）。
 */
const AdminPaperEditPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { t, lang, dict } = useLanguage()
  const locale = lang === 'zh' ? 'zh-CN' : 'en-US'
  const paperId = Number(id)
  const workspacePath = user?.role === 'superadmin' ? '/superadmin' : '/admin'

  /* ── 论文级字段 ─────────────────────────────── */
  const [editForm, setEditForm] = useState<Record<string, any>>({})
  const [authorInput, setAuthorInput] = useState('')
  const [editListText, setEditListText] = useState<Partial<Record<'keywords_tags' | 'methodology', string>>>({})
  const changeListText = (field: 'keywords_tags' | 'methodology', value: string) => {
    setEditListText(current => ({ ...current, [field]: value }))
    setEditForm(current => ({ ...current, [field]: textLinesToList(value) }))
  }
  const editAuthors = useMemo(() => toTextList(editForm.authors), [editForm.authors])
  const commitAuthorInput = () => {
    if (authorInput.trim()) {
      setEditForm(current => ({
        ...current, authors: JSON.stringify(appendAuthor(toTextList(current.authors), authorInput)),
      }))
    }
    setAuthorInput('')
  }
  const [editLoading, setEditLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  /* ── 审核区（论文级 family 与状态级标签均可在本页确认后批准）─ */
  const [editReviewStatus, setEditReviewStatus] = useState('')
  const [editReviewComment, setEditReviewComment] = useState('')
  const [editReviewSaving, setEditReviewSaving] = useState(false)

  /* ── 科学数据（Issue #76）：材料状态与结构候选受控于共享编辑器，保存时随 C1 提交 ─ */
  const [editMaterialStates, setEditMaterialStates] = useState<DraftMaterialState[]>([])
  const [editMaterialFamilies, setEditMaterialFamilies] = useState<FamilySelection[]>([])
  const evidenceWorkflow = useEvidenceWorkflow({
    target: paperId ? { target: 'paper', target_id: String(paperId) } : undefined,
    getCurrentValue: record => currentEvidenceField(record, {...editForm, material_families: editMaterialFamilies}, editMaterialStates),
    saveCurrent: () => handleEditSave([], undefined, undefined, false),
  })
  const [editStructureCandidates, setEditStructureCandidates] = useState<StructureCandidate[]>([])
  const [editStructuralObservations, setEditStructuralObservations] = useState<LatticeObservation[]>([])
  const [structuralLoadError, setStructuralLoadError] = useState('')
  const scientificIdentityMap = useRef<ScientificIdentityMap>({})
  const [editSpaceGroups, setEditSpaceGroups] = useState<SpaceGroupOption[]>([])
  // 论文原本是否有科学数据：有才在保存时走科学数据段（契约 C4 第二步）
  const [editHadScientificData, setEditHadScientificData] = useState(false)
  // 结构表示生成失败降级提示（Issue #78，FR-007）
  const [representationLoadFailed, setRepresentationLoadFailed] = useState(false)

  /* ── 分类目录与通用提示 ─────────────────────── */
  const [classificationCatalogs, setClassificationCatalogs] = useState<ClassificationCatalogs | null>(null)
  const [classificationCatalogError, setClassificationCatalogError] = useState('')
  const [snackbar, setSnackbar] = useState('')

  useEffect(() => {
    loadClassificationCatalogs()
      .then(setClassificationCatalogs)
      .catch((reason: Error) => setClassificationCatalogError(reason.message || t('admin.catalogLoadFailed')))
  }, [])

  // 空间群标准表加载（与上传页同一端点；失败降级为纯自由输入，不阻塞编辑）
  useEffect(() => {
    api.get<{ space_groups?: SpaceGroupOption[] }>('/api/rag/space-groups')
      .then(response => { if (Array.isArray(response?.space_groups)) setEditSpaceGroups(response.space_groups) })
      .catch(() => { /* 空间群表不可用时降级为自由输入，不阻塞编辑 */ })
  }, [])

  /**
   * 结构表示加载（Issue #78 核心，FR-004/FR-007）：详情加载后为每个已落库结构
   * 调用表示端点，把返回的完整 representations（primitive/conventional × cif/poscar）
   * 合并进对应候选，使 StructureCandidatePanel 的晶胞/格式切换与下载可用；
   * 端点失败时保留候选自带的落库惯用胞 CIF（降级，不阻塞编辑）。
   */
  const loadStructureRepresentations = async (detailStates: Array<Record<string, any>>) => {
    await Promise.all(detailStates.flatMap((state) =>
      (state.structures || []).map(async (model: any) => {
        const structureId: number = model.id
        try {
          const response = await api.get<{ ok: boolean; data: { representations?: StructureCandidate['representations']; validation?: StructureCandidate['validation'] } }>(
            `/api/rag/papers/${paperId}/structures/${structureId}/representations`,
          )
          const representations = response?.data?.representations
          if (representations) {
            setEditStructureCandidates(current => current.map(candidate =>
              candidate.candidate_id === `structure_${structureId}`
                ? { ...candidate, validation: { ...candidate.validation, ...response.data.validation }, representations: { ...candidate.representations, ...representations } }
                : candidate))
          }
        } catch {
          // 表示生成服务不可用：保留落库 CIF（候选转换自带），轻提示但不阻塞编辑
          setRepresentationLoadFailed(true)
        }
      }),
    ))
  }

  // 详情加载：论文级字段 + 科学数据转共享编辑器形态 + 已落库结构并入候选
  useEffect(() => {
    const loadDetail = async () => {
      scientificIdentityMap.current = {}
      setEditLoading(true)
      fieldSaver.current = null
      try {
        const { detail, pendingValues } = await loadPaperReviewSource(paperId)
        const classifications = resolveReviewClassifications(detail, pendingValues)
        setAuthorInput('')
        setEditListText({})
        setEditForm({
          ...detail,
          key_properties: [],
          superconductor_kind: classifications.superconductorKind,
        })
        setEditMaterialFamilies(classifications.materialFamilies)
        // 已通过论文重新编辑时默认退回待审核，避免无修改地重复批准。
        setEditReviewStatus(initialPaperReviewStatus(detail.review_status))
        setEditReviewComment(detail.review_comment || '')
        // 科学数据：Go 详情行转成共享编辑器形态；既有结构并入候选（整体替换语义，T020）
        const detailStates: Array<Record<string, any>> = detail.material_states || []
        // 科学值与永久 Evidence 以数据库详情为准，不能被上传时的旧快照覆盖。
        const materialStates = detailStates.map((state, index) =>
          materialStateFromDetail(state, classifications.materialStates[index]))
        const structureCandidates = detailStates.flatMap((state, index) =>
          (state.structures || []).map((model: any) =>
            candidateFromStructureModel(model, `material_states[${index}]`)))
        setEditMaterialStates(materialStates)
        setEditStructureCandidates(structureCandidates)
        try {
          const collection = await api.get<any>(`/api/rag/structural-records/paper/${paperId}`)
          const models = (collection.items || []).filter((item: any) => item.kind === 'model' || item.kind === 'issue' && item.data?.candidate_id)
          const candidates = [...structureCandidates]
          for (const item of models) {
            const index = materialStates.findIndex(state => state.state_key === item.state_key)
            const ref = index >= 0 ? `material_states[${index}]` : 'unassigned:paper'
            const adopted = index >= 0 ? candidates.find(c => c.material_state_ref === ref) : undefined
            if (adopted) Object.assign(adopted, { retention: item.retention, structural_record: item.data })
            else candidates.push({ ...item.data, retention: item.retention, material_state_ref: ref })
          }
          setEditStructureCandidates(candidates)
          setEditStructuralObservations((collection.items || []).filter((item: any) => item.kind === 'lattice').map((item: any) => ({ ...item.data, retention: item.retention })))
          setStructuralLoadError('')
        } catch (error: any) {
          // 未迁移的旧环境仍可编辑原字段；服务端保存会保护未加载的结构资料。
          setStructuralLoadError(error.message || '结构资料读取失败')
        }
        setEditHadScientificData(
          materialStates.length > 0 || structureCandidates.length > 0 || classifications.materialFamilies.length > 0,
        )
        const staged = await api.get<{ staged: boolean; draft: any }>(`/api/rag/evidence/draft-state?target=paper&target_id=${paperId}`)
        if (staged.staged) {
          setEditForm(staged.draft.paper)
          setEditMaterialFamilies(staged.draft.paper.material_families || [])
          setEditMaterialStates(staged.draft.material_states || [])
          setEditStructureCandidates(staged.draft.structure_candidates || [])
          setEditStructuralObservations(staged.draft.structural_observations || [])
        } else if (staged.draft?.paper) {
          // Go 详情的列表为 JSON 文本；保存前值必须与草稿接口的实际数组一致。
          const canonicalPaper = staged.draft.paper
          setEditForm(current => ({ ...current, ...Object.fromEntries(
            (['keywords_tags', 'methodology'] as const).filter(field => field in canonicalPaper).map(field => [field, canonicalPaper[field]]),
          ) }))
        }
        // 已落库结构表示：异步拉取完整表示并入候选，不阻塞表单渲染
        void loadStructureRepresentations(detailStates)
      } catch (e: unknown) {
        setLoadError(t('admin.loadFailedReason', { reason: (e as Error).message }))
      } finally {
        setEditLoading(false)
      }
    }
    void loadDetail()
  }, [paperId])

  // 编辑页内提交审核；批准时由后端校验当前论文级 family 和状态分类完整性。
  const handleEditReview = async () => {
    setEditReviewSaving(true)
    try {
      if (editReviewStatus === 'approved' && evidenceWorkflow.hasUnsavedChanges() && !(await handleEditSave())) return
      const payload = editReviewStatus === 'approved'
        ? { status: editReviewStatus, comment: editReviewComment, review_request_id: crypto.randomUUID() }
        : paperReviewPayload(editReviewStatus, editReviewComment)
      const evidence = editReviewStatus === 'approved' ? await evidenceWorkflow.gate({ target: 'paper', target_id: String(paperId) }) : {}
      if (!evidence) return
      await api.post(editReviewStatus === 'approved' ? '/api/rag/evidence/review-commit' : `/api/admin/papers/${paperId}/review`, { ...payload, ...evidence, paper_id: Number(paperId) })
      navigate(workspacePath)
    } catch (e: unknown) {
      setSnackbar(t('admin.reviewFailed', { reason: (e as Error).message }))
    } finally { setEditReviewSaving(false) }
  }

  // 两段保存（契约 C4）：先论文级（Go，低风险），后科学数据（Python，整体替换）。
  // 科学数据段仅当论文原本有科学数据或当前编辑区有内容时执行——纯论文级编辑
  // （如无材料状态的综述）不需要触发整体替换。
  const fieldSaver = useRef<ReturnType<typeof createFieldDraftSaver> | null>(null)
  const editableDraft = () => ({ paper: { ...editForm, material_families: editMaterialFamilies },
    material_states: editMaterialStates, structure_candidates: editStructureCandidates,
    structural_observations: editStructuralObservations })
  useEffect(() => {
    if (!editLoading && !fieldSaver.current && paperId) {
      fieldSaver.current = createFieldDraftSaver({target: 'paper', target_id: String(paperId)})
      fieldSaver.current.initialize(editableDraft())
    }
  }, [editLoading, paperId])
  const handleEditSave = async (_patches: EvidencePatch[] = [], _preparationId?: string, _resumeStage?: 'scientific' | 'finalize', _refreshEvidence = true) => {
    try {
      if (!fieldSaver.current) return false
      await fieldSaver.current.save(editableDraft())
      setSnackbar(t('common.saved'))
      return true
    } catch (error) { setSnackbar(t('admin.saveFailedReason', { reason: (error as Error).message })); return false }
  }

  // 论文结构补传（契约 C2）：只产出并校验候选、不落库；成功后并入本地候选，
  // 由保存时的 C1 structure_candidates 字段一并提交（T034）。
  const handleUploadStructure = async (stateIndex: number, file: File) => {
    const body = new FormData()
    body.append('material_state_index', String(stateIndex))
    body.append('file', file)
    const response = await api.post<{ ok: boolean; data: Record<string, any> }>(
      `/api/rag/papers/${paperId}/structure-candidates`, body,
    )
    const data = unwrapData(response)
    const candidate: StructureCandidate = {
      candidate_id: String(data.candidate_id),
      material_state_ref: `material_states[${stateIndex}]`,
      source_kind: 'attachment',
      status: data.status || 'needs_review',
      confirmation: 'unreviewed',
      original_format: data.structure_format || null,
      validation: data.validation,
      representations: data.representations,
      sources: [{ file_id: String(data.candidate_id), filename: file.name, role: 'attachment' }],
    }
    setEditStructureCandidates(current => [
      ...current.filter(item => item.candidate_id !== candidate.candidate_id),
      candidate,
    ])
  }

  return (
    <Container component="fieldset" disabled={editReviewSaving} maxWidth={false} disableGutters sx={{ py: 3, border: 0, minWidth: 0 }}>
      {/* 标题栏 + 返回列表 */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <IconButton aria-label={t('admin.editBackToList')} onClick={() => navigate(workspacePath)}>
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Typography variant="h5" fontWeight={700}>{t('admin.editPaperTitle')}</Typography>
        {editLoading && <CircularProgress size={20} />}
      </Box>

      {loadError && <Alert severity="error" sx={{ mb: 2 }}>{loadError}</Alert>}
      {representationLoadFailed && (
        <Alert severity="warning" sx={{ mb: 2 }}>{t('admin.representationsLoadFailed')}</Alert>
      )}

      {editForm.id != null ? (
        <Box data-evidence-scope="paper-edit" sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {/* 核对提示和审核操作随页面滚动，避免遮挡下方表单。 */}
          <Box sx={{
            bgcolor: 'background.paper',
            pb: 1.5, mb: 0.5, borderBottom: '1px solid', borderColor: 'divider',
          }}>
            {evidenceWorkflow.dialog}
            <EvidenceFieldMarkers records={evidenceWorkflow.records} scope="paper-edit" onOpen={evidenceWorkflow.openIssue} onChange={evidenceWorkflow.invalidate} />
            <Box data-evidence-ignore><Typography variant="subtitle2" fontWeight={700} gutterBottom>{t('admin.editReviewSection')}</Typography>
            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <Button variant="outlined" disabled={editReviewSaving || evidenceWorkflow.busy} onClick={evidenceWorkflow.showResults}>{t('evidence.viewResults')}</Button>
          <Box sx={{ minWidth: 170 }}>
                <PaperReviewStatusSelect id="edit-review-status" value={editReviewStatus}
                  onChange={setEditReviewStatus} disabled={editReviewSaving} />
              </Box>
              <TextField label={t('admin.reviewComment')} size="small" multiline rows={2} sx={{ flex: 1, minWidth: 180 }}
                disabled={editReviewSaving} value={editReviewComment} onChange={e => setEditReviewComment(e.target.value)} />
              <Button variant="contained" size="small" disabled={editReviewSaving}
                onClick={handleEditReview} sx={{ mt: 0.5 }}>
                {t('admin.submitReview')}
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              {t('admin.editReviewHint')}
            </Typography></Box>
          </Box>

          <ReviewPaperTextField data-issue-field="paper.title" label={t('admin.fieldTitle')} size="small" fullWidth multiline rows={2} disabled={editReviewSaving}
            value={editForm.title || ''} onValueChange={value => setEditForm(current => ({ ...current, title: value }))} />
          <PaperMetadataRow
            journal={<TextField data-issue-field="paper.journal" label={t('admin.fieldJournal')} size="small" value={editForm.journal || ''}
              onChange={e => setEditForm({ ...editForm, journal: e.target.value })} />}
            year={<TextField data-issue-field="paper.year" label={t('admin.fieldYear')} size="small" type="number" value={editForm.year ?? ''}
              onChange={e => setEditForm({ ...editForm, year: e.target.value ? Number(e.target.value) : null })} />}
            issueNumber={<TextField data-issue-field="paper.issue_number" label={t('admin.fieldIssueNumber')} size="small" value={editForm.issue_number || ''}
              slotProps={{ htmlInput: { maxLength: 100 } }}
              onChange={e => setEditForm({ ...editForm, issue_number: e.target.value })} />}
            volume={<TextField data-issue-field="paper.volume" label={t('admin.fieldVolume')} size="small" value={editForm.volume || ''}
              onChange={e => setEditForm({ ...editForm, volume: e.target.value })} />}
            pages={<TextField data-issue-field="paper.pages" label={t('admin.fieldPages')} size="small" value={editForm.pages || ''}
              onChange={e => setEditForm({ ...editForm, pages: e.target.value })} />}
            doi={<TextField data-issue-field="paper.doi" label={t('admin.fieldDoi')} size="small" value={editForm.doi || ''}
              onChange={e => setEditForm({ ...editForm, doi: e.target.value })} />}
          />
          <Autocomplete
            multiple freeSolo forcePopupIcon={false} options={[] as string[]}
            value={editAuthors}
            inputValue={authorInput}
            onInputChange={(_, value) => setAuthorInput(value)}
            onBlur={commitAuthorInput}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.defaultMuiPrevented = true
                if (event.nativeEvent.isComposing || event.keyCode === 229) return
                event.preventDefault()
                commitAuthorInput()
              }
            }}
            onChange={(_, values) => {
              setEditForm(current => ({
                ...current,
                authors: JSON.stringify(values.reduce<string[]>((items, name) => appendAuthor(items, name), [])),
              }))
              setAuthorInput('')
            }}
            renderInput={params => (
              <TextField {...params} data-issue-field="paper.authors" label={t('admin.fieldAuthors')} size="small"
                placeholder={t('upload.authorPlaceholder')} />
            )}
          />
          <PaperMaterialsSection states={editMaterialStates} historicalMaterials={editForm.research_materials} />
          <ReviewPaperTextField label={t('admin.fieldAbstract')} size="small" fullWidth multiline rows={3} disabled={editReviewSaving}
            data-issue-field="paper.abstract" value={editForm.abstract || ''} onValueChange={value => setEditForm(current => ({ ...current, abstract: value }))} />
          <ReviewPaperTextField label={t('admin.fieldLlmSummary')} size="small" fullWidth multiline rows={2} disabled={editReviewSaving}
            data-issue-field="paper.summary" value={editForm.summary || ''} onValueChange={value => setEditForm(current => ({ ...current, summary: value }))} />
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(3, minmax(0, 1fr))' }, gap: 1.5 }}>
            <TextField label={t('admin.fieldPaperType')} size="small" data-issue-field="paper.paper_type" value={editForm.paper_type || ''}
              onChange={e => { evidenceWorkflow.invalidate('paper.paper_type'); evidenceWorkflow.invalidate('paper.theoretical_subtype'); setEditForm({ ...editForm, paper_type: e.target.value, theoretical_subtype: e.target.value === 'theoretical' ? editForm.theoretical_subtype : null }) }} />
            <FormControl size="small" disabled={editForm.paper_type !== 'theoretical'} data-issue-field="paper.theoretical_subtype">
              <InputLabel id="admin-theoretical-subtype-label">{t('upload.theoreticalSubtypeField')}</InputLabel>
              <Select labelId="admin-theoretical-subtype-label" label={t('upload.theoreticalSubtypeField')} value={editForm.theoretical_subtype || ''}
                onChange={e => { evidenceWorkflow.invalidate('paper.theoretical_subtype'); setEditForm({ ...editForm, theoretical_subtype: e.target.value || null }) }}>
                <MenuItem value="calculation">{dict.enums.theoreticalSubtype.calculation}</MenuItem>
                <MenuItem value="method">{dict.enums.theoreticalSubtype.method}</MenuItem>
                <MenuItem value="theory">{dict.enums.theoreticalSubtype.theory}</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" data-issue-field="paper.superconductor_kind">
              <InputLabel id="paper-superconductor-kind-label">{t('upload.superconductorKindField')}</InputLabel>
              <Select labelId="paper-superconductor-kind-label" label={t('upload.superconductorKindField')} value={editForm.superconductor_kind || 'unknown'}
                onChange={e => { evidenceWorkflow.invalidate('paper.superconductor_kind'); setEditForm({ ...editForm, superconductor_kind: e.target.value }) }}>
                {SUPERCONDUCTOR_KIND_VALUES.map(value => (
                  <MenuItem key={value} value={value}>{value === 'unknown' ? dict.enums.superconductorKind.unknown : dict.enums.superconductorKind[value]}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Autocomplete<ClassificationTerm | string, true, false, true> data-issue-field="paper.material_families"
              multiple
              freeSolo
              options={classificationCatalogs?.material_families || []}
              loading={!classificationCatalogs && !classificationCatalogError}
              value={editMaterialFamilies.map(selection => {
                if (selection.id == null) return selection.name
                return classificationCatalogs?.material_families?.find(item => item.id === selection.id) || selection.name
              })}
              getOptionLabel={option => typeof option === 'string' ? option : familyName(option, lang)}
              isOptionEqualToValue={(option, value) => (
                typeof option !== 'string' && typeof value !== 'string' && option.id === value.id
              )}
              onChange={(_, values) => { evidenceWorkflow.invalidate('paper.material_families'); setEditMaterialFamilies(values.map(value => (
                typeof value === 'string' ? pendingSelection(value) : selectionForTerm(value)
              )).filter((value): value is FamilySelection => Boolean(value))) }}
              renderInput={params => (
                <TextField
                  {...params}
                  size="small"
                  label={t('upload.materialFamilyField')}
                  error={Boolean(classificationCatalogError)}
                  helperText={classificationCatalogError || undefined}
                />
              )}
            />
            <TextField label={t('admin.fieldSourceFilePath')} size="small" value={editForm.source_file_path || ''}
              onChange={e => setEditForm({ ...editForm, source_file_path: e.target.value })} />
          </Box>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5 }}>
            {(['keywords_tags', 'methodology'] as const).map(field => (
              <ReviewPaperTextField key={field} data-issue-field={`paper.${field}`} disabled={editReviewSaving}
                label={t(field === 'keywords_tags' ? 'admin.fieldKeywordsTags' : 'admin.fieldMethodology')}
                size="small" fullWidth multiline minRows={3}
                helperText={t('admin.listOnePerLine')}
                value={editListText[field] ?? toTextList(editForm[field]).join('\n')}
                onValueChange={value => changeListText(field, value)} />
            ))}
          </Box>
          <ReviewPaperTextField label={t('admin.fieldKeyFinding')} size="small" fullWidth multiline rows={2} disabled={editReviewSaving}
            data-issue-field="paper.key_finding" value={editForm.key_finding || ''} onValueChange={value => setEditForm(current => ({ ...current, key_finding: value }))} />
          <ReviewPaperTextField label={t('admin.fieldResearchMotivation')} size="small" fullWidth multiline rows={2} disabled={editReviewSaving}
            data-issue-field="paper.research_motivation" value={editForm.research_motivation || ''} onValueChange={value => setEditForm(current => ({ ...current, research_motivation: value }))} />
          {/* 知识图谱标题：单栏英文输入，随 editForm 一并提交（T046）。 */}
          <TextField data-issue-field="paper.knowledge_graph_title" label={t('admin.fieldKnowledgeGraphTitle')} size="small" fullWidth
            value={editForm.knowledge_graph_title || ''} onChange={e => setEditForm({ ...editForm, knowledge_graph_title: e.target.value })} />
          {/* 非编辑元数据 */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
            <Chip size="small" label={t('admin.idChip', { value: editForm.id || '-' })} variant="outlined" />
            <Chip size="small" label={t('admin.createdChip', { value: editForm.created_at ? new Date(editForm.created_at).toLocaleString(locale) : '-' })} />
            {(editForm.materials || []).map((m: string) => (
              <Chip key={m} size="small" label={m} color="primary" variant="outlined" />
            ))}
          </Box>

          {/* Key Properties */}
          {(editForm.key_properties || []).length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                {t('admin.keyPropertiesHeader', { n: editForm.key_properties.length })}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, maxHeight: 480, overflow: 'auto' }}>
                {(editForm.key_properties || []).map((kp: any, i: number) => {
                  const setKp = (f: string, v: any) => {
                    const n = [...(editForm.key_properties || [])]
                    n[i] = { ...n[i], [f]: v }
                    setEditForm({ ...editForm, key_properties: n })
                  }
                  return (
                    <Box key={kp.id || i} sx={{
                      p: 1.5, borderRadius: 1, bgcolor: kp.is_primary ? '#eef2ff' : 'grey.50',
                      border: '1px solid', borderColor: kp.is_primary ? '#818cf8' : 'divider',
                    }}>
                      {/* KP header */}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Chip size="small" label={`#${i + 1}`} variant="outlined" />
                        {kp.is_primary && <Chip size="small" label={t('admin.primaryProperty')} color="primary" />}
                        <Typography variant="caption" color="text.secondary">
                          ID: {kp.id} · source: {kp.name_raw || '-'}
                        </Typography>
                      </Box>
                      {/* Row 1: 核心数值 */}
                      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(4, minmax(0, 1fr))' }, gap: 1 }}>
                        <TextField label={t('admin.fieldMaterial')} size="small" value={kp.material || ''}
                          onChange={e => setKp('material', e.target.value)} />
                        <TextField label={t('admin.fieldPropertyName')} size="small" value={kp.name || ''}
                          onChange={e => setKp('name', e.target.value)} />
                        <FormControlLabel control={
                          <Checkbox checked={!!kp.is_primary} size="small"
                            onChange={e => setKp('is_primary', e.target.checked)} />
                        } label={t('admin.primaryProperty')} sx={{ m: 0 }} />
                        <FormControl size="small">
                          <InputLabel>{t('admin.nameNoteLabel')}</InputLabel>
                          <Select value={kp.name_note || ''} label={t('admin.nameNoteLabel')}
                            onChange={e => setKp('name_note', e.target.value)}>
                            <MenuItem value="">-</MenuItem>
                            <MenuItem value="temperature/position dependent">{t('admin.nameNoteTemperaturePositionDependent')}</MenuItem>
                            <MenuItem value="pressure dependent">{t('admin.nameNotePressureDependent')}</MenuItem>
                            <MenuItem value="doping dependent">{t('admin.nameNoteDopingDependent')}</MenuItem>
                            <MenuItem value="dynamically stable">{t('admin.nameNoteDynamicallyStable')}</MenuItem>
                            <MenuItem value="thermodynamically stable">{t('admin.nameNoteThermodynamicallyStable')}</MenuItem>
                          </Select>
                        </FormControl>
                      </Box>
                      {/* Row 2: 数值 */}
                      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(5, minmax(0, 1fr))' }, gap: 1, mt: 1 }}>
                        <TextField label={t('admin.fieldValueMin')} size="small" type="number"
                          value={kp.value_min ?? ''} onChange={e => setKp('value_min', e.target.value ? Number(e.target.value) : null)} />
                        <TextField label={t('admin.fieldValueMax')} size="small" type="number"
                          value={kp.value_max ?? ''} onChange={e => setKp('value_max', e.target.value ? Number(e.target.value) : null)} />
                        <TextField label={t('admin.fieldValueRaw')} size="small"
                          value={kp.value_raw || ''} onChange={e => setKp('value_raw', e.target.value)} />
                        <TextField label={t('admin.fieldUnit')} size="small"
                          value={kp.unit || ''} onChange={e => setKp('unit', e.target.value)} />
                        <TextField label={t('admin.fieldNameRaw')} size="small"
                          value={kp.name_raw || ''} onChange={e => setKp('name_raw', e.target.value)} />
                      </Box>
                      {/* Row 3: 条件与分类 */}
                      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(3, minmax(0, 1fr))' }, gap: 1, mt: 1 }}>
                        <TextField label={t('admin.fieldPressure')} size="small" type="number"
                          value={kp.pressure_gpa ?? ''} onChange={e => setKp('pressure_gpa', e.target.value ? Number(e.target.value) : null)} />
                        <TextField label={t('admin.fieldTemperature')} size="small" type="number"
                          value={kp.temperature_k ?? ''} onChange={e => setKp('temperature_k', e.target.value ? Number(e.target.value) : null)} />
                        <FormControl size="small">
                          <InputLabel>{t('admin.fieldArticleType')}</InputLabel>
                          <Select value={kp.article_type || ''} label={t('admin.fieldArticleType')}
                            onChange={e => setKp('article_type', e.target.value)}>
                            <MenuItem value="">-</MenuItem>
                            <MenuItem value="e">{t('admin.articleTypeExperimental')}</MenuItem>
                            <MenuItem value="t">{t('admin.articleTypeTheoretical')}</MenuItem>
                          </Select>
                        </FormControl>
                      </Box>
                      {/* Row 4: notes */}
                      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))' }, gap: 1, mt: 1 }}>
                        <TextField label={t('admin.fieldConditionNote')} size="small"
                          value={kp.condition_note || ''} onChange={e => setKp('condition_note', e.target.value)} />
                        <TextField label={t('admin.fieldNameNote')} size="small"
                          value={kp.name_note || ''} onChange={e => setKp('name_note', e.target.value)} />
                      </Box>
                    </Box>
                  )
                })}
              </Box>
            </Box>
          )}

          {/* 升版警告：编辑已通过论文时提示保存科学数据将递增版本并退回待审核（T044） */}
          {editForm.review_status === 'approved' && (
            <Alert severity="warning">{t('admin.revisionBumpWarning')}</Alert>
          )}
          {/* 科学数据编辑区（Issue #76）：材料状态、物性模块、结构候选与补传。
              数据来自 /api/admin/papers/:id 的 material_states（含 property_modules/structures），
              编辑结果随保存时的 C1 请求整体替换（T020/T030/T034）。 */}
          <MaterialStatesEditor
            independentStructureWorkspace
            propertySpectra={{ target: { target: 'paper', target_id: String(paperId) }, beforeNavigate: async () => {
              if (evidenceWorkflow.hasManualDrafts()) throw new Error('请先保存或处理来源核对中的人工修改草稿，再打开谱详情。')
              const version = evidenceWorkflow.getEditRevision()
              const saved = await handleEditSave()
              return saved && version === evidenceWorkflow.getEditRevision()
            } }}
            spectrumTarget={{ target: 'paper', target_id: String(paperId) }}
            beforeSpectrumEdit={() => handleEditSave()}
            onScientificEdit={evidenceWorkflow.invalidate}
            reviewFields={evidenceFieldsForStates(evidenceWorkflow.issues, editMaterialStates)}
            states={editMaterialStates}
            onChange={states => {
              if (JSON.stringify(researchMaterials(editMaterialStates)) !== JSON.stringify(researchMaterials(states))) evidenceWorkflow.invalidate('paper.research_materials')
              setEditMaterialStates(states)
              setEditForm(current => ({ ...current, research_materials: researchMaterials(states) }))
            }}
            catalogs={classificationCatalogs}
            catalogLoading={!classificationCatalogs && !classificationCatalogError}
            catalogError={classificationCatalogError}
            structureCandidates={editStructureCandidates}
            onStructureCandidatesChange={setEditStructureCandidates}
            spaceGroups={editSpaceGroups}
            paperType={editForm.paper_type}
            superconductorKind={editForm.superconductor_kind}
            onUploadStructure={handleUploadStructure}
            onError={setSnackbar}
          />
          {structuralLoadError && <Alert severity="warning">论文独立结构资料暂不可读取：{structuralLoadError}。当前未加载的资料会由服务端保留。</Alert>}
          <PaperStructuralWorkspace candidates={editStructureCandidates} observations={editStructuralObservations}
            onCandidates={setEditStructureCandidates} onObservations={setEditStructuralObservations} />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1 }}>
            <Button variant="outlined" onClick={() => navigate(workspacePath)}>{t('common.cancel')}</Button>
            <Button variant="contained" onClick={() => void handleEditSave()}>{t('admin.saveChanges')}</Button>
          </Box>
        </Box>
      ) : (
        !loadError && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
            <CircularProgress />
          </Box>
        )
      )}

      {/* Snackbar */}
      <Snackbar open={!!snackbar} autoHideDuration={3000} onClose={() => setSnackbar('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="info" variant="filled" onClose={() => setSnackbar('')}>{snackbar}</Alert>
      </Snackbar>
    </Container>
  )
}

export default AdminPaperEditPage
