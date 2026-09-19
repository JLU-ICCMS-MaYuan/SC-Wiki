import { currentEvidenceField, evidenceIssuesForStates } from '../lib/evidenceFields'
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
import PaperMetadataRow from '../components/PaperMetadataRow'
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
        setEditHadScientificData(
          materialStates.length > 0 || structureCandidates.length > 0 || classifications.materialFamilies.length > 0,
        )
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
      let classifications: ReviewClassifications | undefined
      if (editReviewStatus === 'approved') {
        if ((!evidenceWorkflow.hasAccepted || evidenceWorkflow.hasUnsavedChanges()) && !(await handleEditSave())) return
        if (!(await evidenceWorkflow.applyAccepted({ target: 'paper', target_id: String(paperId) }, handleEditSave))) return
        const { detail } = await loadPaperReviewSource(Number(paperId))
        classifications = resolveReviewClassifications(detail)
      }
      const payload = paperReviewPayload(editReviewStatus, editReviewComment, classifications)
      const evidence = editReviewStatus === 'approved' ? await evidenceWorkflow.gate({ target: 'paper', target_id: String(paperId) }) : {}
      if (!evidence) return
      await api.post(`/api/admin/papers/${paperId}/review`, { ...payload, ...evidence })
      navigate(workspacePath)
    } catch (e: unknown) {
      setSnackbar(t('admin.reviewFailed', { reason: (e as Error).message }))
    } finally { setEditReviewSaving(false) }
  }

  // 两段保存（契约 C4）：先论文级（Go，低风险），后科学数据（Python，整体替换）。
  // 科学数据段仅当论文原本有科学数据或当前编辑区有内容时执行——纯论文级编辑
  // （如无材料状态的综述）不需要触发整体替换。
  const handleEditSave = async (patches: EvidencePatch[] = [], preparationId?: string, resumeStage?: 'scientific' | 'finalize', refreshEvidence = true) => {
    const revision = evidenceWorkflow.getEditRevision()
    const invalidPressure = Array.from(document.querySelectorAll<HTMLInputElement>('[data-evidence-scope="paper-edit"] [data-pressure-input]')).find(input => !input.checkValidity())
    if (invalidPressure) { invalidPressure.reportValidity(); setSnackbar(t('evidence.invalidPressure')); return false }
    try {
      const tcIssue = validateTcRecords(editMaterialStates)[0]
      if (tcIssue) { setSnackbar(tcIssue.message); return false }
      const historyOperationId = crypto.randomUUID()
      const paper: Record<string, any> = { ...editForm, material_families: editMaterialFamilies }
      const changed = applyEvidencePatches({ paper, material_states: editMaterialStates }, patches)
      const missingIdentity = changed.material_states.findIndex(materialIdentityMissing)
      if (missingIdentity >= 0) throw new Error(t('upload.missingMaterial', {label:t('upload.materialStateLabel', {index:missingIdentity+1})}))
      const payload: Record<string, any> = { ...changed.paper, history_operation_id: historyOperationId, evidence_preparation_id: preparationId }
      // 分类由科学保存原子写入，避免第一段先改类型使第二段误判为同值。
      if (editHadScientificData || changed.paper.material_families?.length || changed.material_states.length || editStructureCandidates.length) delete payload.superconductor_kind
      // 科学段可能失败；汇总与材料状态由同一 Python 事务保存，避免第一段先写入未来值。
      if (editHadScientificData || changed.material_states.length) delete payload.research_materials
      for (const field of ['research_materials', 'material_relations']) {
        if (Array.isArray(payload[field])) payload[field] = JSON.stringify(payload[field])
      }
      if (authorInput.trim()) {
        payload.authors = JSON.stringify(appendAuthor(toTextList(editForm.authors), authorInput))
      }
      // Go 文本列不接收数组；只转换数组和用户编辑过的字段，原字符串/空值保持不变。
      for (const field of ['authors', 'keywords_tags', 'methodology'] as const) {
        if (field !== 'authors' && editListText[field] !== undefined && !patches.some(p => p.field === `paper.${field}`)) {
          payload[field] = JSON.stringify(textLinesToList(editListText[field]!))
        } else if (Array.isArray(payload[field])) {
          payload[field] = JSON.stringify(payload[field])
        }
      }
      delete payload.key_properties
      // 只提交 superconductor_properties 的真实列。压强、温度等条件字段属材料状态，
      // 不经物性接口修改；后端也不再接受这些无对应列的字段。
      if (payload.key_properties) {
        payload.key_properties = payload.key_properties.map((kp: any) => ({
          id: kp.id, material: kp.material, name_raw: kp.name_raw,
          value_min: kp.value_min, value_max: kp.value_max,
          value_raw: kp.value_raw, value_number: kp.value_number,
          unit: kp.unit, canonical_unit: kp.canonical_unit,
          condition_note: kp.condition_note,
        }))
      }
      // 第一步：论文级字段保存（Go）。失败在此终止，不调用科学数据段。
      if (resumeStage !== 'scientific') await api.put(`/api/admin/papers/${paperId}`, payload)
      if (patches.length) { setEditForm(changed.paper); setEditListText({}) }
      if (editHadScientificData || changed.paper.material_families?.length || changed.material_states.length || editStructureCandidates.length) {
        try {
          const identities = remapScientificIdentities(changed.material_states, editStructureCandidates, scientificIdentityMap.current)
          // 第二步：科学数据整体替换（Python，契约 C1）。
          // structure_candidates 只提交已确认候选：未确认（unreviewed）与已排除（excluded）
          // 的候选不落库，与上传链路「先确认后保存」的语义一致（契约 C1/C2）。
          const response = await api.put<{ ok: boolean; data: ScientificIdentityMap & { revision_bumped?: boolean } }>(
            `/api/rag/papers/${paperId}/scientific-draft`,
            {
              paper_type: changed.paper.paper_type || '',
              superconductor_kind: changed.paper.superconductor_kind || 'unknown',
              material_families: changed.paper.material_families,
              material_states: identities.states,
              structure_candidates: identities.candidates.filter(candidate => candidate.confirmation === 'confirmed'),
              history_operation_id: historyOperationId, evidence_preparation_id: preparationId,
            },
          )
          scientificIdentityMap.current = {
            structure_candidate_id_map: { ...scientificIdentityMap.current.structure_candidate_id_map, ...response?.data?.structure_candidate_id_map },
            structure_key_map: { ...scientificIdentityMap.current.structure_key_map, ...response?.data?.structure_key_map },
          }
          setEditMaterialStates(current => remapScientificIdentities(current, [], scientificIdentityMap.current).states)
          setEditStructureCandidates(current => remapScientificIdentities([], current, scientificIdentityMap.current).candidates)
          // 升版成功（T045）：论文已退回待审核，明确提示审核通过前不对外公开
          setSnackbar(response?.data?.revision_bumped
            ? t('admin.scientificSavedRevisionBumped')
            : t('common.saved'))
        } catch (e: unknown) {
          // FR-019：论文级已保存成功，只需重试科学数据部分；不离开编辑页
          setSnackbar(t('admin.scientificSaveFailed', { reason: (e as Error).message }))
          return false
        }
      } else {
        setSnackbar(t('common.saved'))
      }
      if (patches.length) {
        setEditForm(changed.paper); setEditMaterialFamilies(changed.paper.material_families)
        setEditMaterialStates(remapScientificIdentities(changed.material_states, [], scientificIdentityMap.current).states); setEditListText({})
      }
      if (!preparationId && refreshEvidence) await evidenceWorkflow.refreshAfterSave(revision)
      return true
    } catch (e: unknown) { setSnackbar(t('admin.saveFailedReason', { reason: (e as Error).message })); return false }
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
    <Container component="fieldset" disabled={editReviewSaving} maxWidth="lg" sx={{ py: 3, px: { xs: 0, sm: 3 }, border: 0, minWidth: 0 }}>
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
              <Button variant="outlined" disabled={editReviewSaving || evidenceWorkflow.busy} onClick={async () => { if (await handleEditSave()) void evidenceWorkflow.run({ target: 'paper', target_id: String(paperId) }) }}>{t('evidence.audit')}</Button>
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

          <TextField data-issue-field="paper.title" label={t('admin.fieldTitle')} size="small" fullWidth multiline rows={2}
            value={editForm.title || ''} onChange={e => setEditForm({ ...editForm, title: e.target.value })} />
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
          <PaperMaterialsSection states={editMaterialStates} relations={editForm.material_relations} historicalMaterials={editForm.research_materials} onChange={values => { evidenceWorkflow.invalidate('paper.material_relations'); setEditForm(current => ({ ...current, material_relations: values })) }} />
          <TextField label={t('admin.fieldAbstract')} size="small" fullWidth multiline rows={3}
            data-issue-field="paper.abstract" value={editForm.abstract || ''} onChange={e => setEditForm({ ...editForm, abstract: e.target.value })} />
          <TextField label={t('admin.fieldLlmSummary')} size="small" fullWidth multiline rows={2}
            data-issue-field="paper.summary" value={editForm.summary || ''} onChange={e => setEditForm({ ...editForm, summary: e.target.value })} />
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(3, minmax(0, 1fr))' }, gap: 1.5 }}>
            <TextField label={t('admin.fieldPaperType')} size="small" data-issue-field="paper.paper_type" value={editForm.paper_type || ''}
              onChange={e => setEditForm({ ...editForm, paper_type: e.target.value })} />
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
              <TextField key={field} data-issue-field={`paper.${field}`}
                label={t(field === 'keywords_tags' ? 'admin.fieldKeywordsTags' : 'admin.fieldMethodology')}
                size="small" fullWidth multiline minRows={3}
                helperText={t('admin.listOnePerLine')}
                value={editListText[field] ?? toTextList(editForm[field]).join('\n')}
                onChange={event => setEditListText(current => ({ ...current, [field]: event.target.value }))} />
            ))}
          </Box>
          <TextField label={t('admin.fieldKeyFinding')} size="small" fullWidth multiline rows={2}
            data-issue-field="paper.key_finding" value={editForm.key_finding || ''} onChange={e => setEditForm({ ...editForm, key_finding: e.target.value })} />
          <TextField label={t('admin.fieldResearchMotivation')} size="small" fullWidth multiline rows={2}
            data-issue-field="paper.research_motivation" value={editForm.research_motivation || ''} onChange={e => setEditForm({ ...editForm, research_motivation: e.target.value })} />
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
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 1 }}>
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
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr', gap: 1, mt: 1 }}>
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
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1, mt: 1 }}>
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
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 1 }}>
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
            onScientificEdit={evidenceWorkflow.invalidate}
            issues={evidenceIssuesForStates(evidenceWorkflow.issues, editMaterialStates)}
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
