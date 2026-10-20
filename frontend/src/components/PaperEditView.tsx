import PropertyModuleSection from './PropertyModuleSection'
import { materialStateSummary } from '../lib/materialStateSummary'
import { PropertySpectraProvider, PropertySpectrumState } from './PropertySpectra'
import React, { useState, useEffect } from 'react'
import {
  Box, Typography, Card, CardContent, Button,
  Chip, Alert,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import DownloadIcon from '@mui/icons-material/Download'
import CrystalStructureView from './CrystalStructureView'
import PaperMaterialsSection from './PaperMaterialsSection'
import { useLanguage } from '../context/LanguageContext'
import { familyName } from '../lib/classifications'
import { api } from '../lib/api'
import PropertyModuleEditor from './PropertyModuleEditor'
import { toTextList } from '../lib/paperTextLists'
import { materialLabel } from '../lib/materialIdentity'
import { Link } from 'react-router-dom'
import PaperStructuralCollection from './PaperStructuralCollection'

interface PaperEditViewProps {
  // 论文数据与加载/错误分流由路由页面壳 PaperDetailPage 负责，本组件只负责展示。
  paper: any
  onBack: () => void
  onOpenMyPapers?: () => void
}

// 审核状态的颜色映射；标签文案按 value 查 dict.enums.reviewStatus。
const STATUS_COLORS: Record<string, 'warning' | 'success' | 'error' | 'info'> = {
  pending: 'warning', approved: 'success', rejected: 'error', needs_revision: 'info',
}

// 按当前语言解析审核状态标签；字典未收录的值回退原文（后端 value 是接口契约，不翻译）。
const reviewStatusLabel = (dict: any, value: string | null | undefined): string => {
  const table: Record<string, string> = dict?.enums?.reviewStatus || {}
  return (value && table[value]) || value || ''
}

const PaperEditView: React.FC<PaperEditViewProps> = ({ paper, onBack, onOpenMyPapers }) => {
  const { t, lang, dict } = useLanguage()

  // 只读展示状态：用于展示的本地状态，切换论文时重新填充
  const [editTitle, setEditTitle] = useState('')
  const [editDoi, setEditDoi] = useState('')
  const [editJournal, setEditJournal] = useState('')
  const [editYear, setEditYear] = useState<number | ''>('')
  const [editAuthors, setEditAuthors] = useState('')
  const [editAbstract, setEditAbstract] = useState('')
  const [editSummary, setEditSummary] = useState('')
  const [editKnowledgeGraphTitle, setEditKnowledgeGraphTitle] = useState('')
  const [editKeyFinding, setEditKeyFinding] = useState('')
  const [editResearchMotivation, setEditResearchMotivation] = useState('')
  const [exportError, setExportError] = useState('')

  const downloadMaterialState = async (state: any) => {
    try {
      setExportError('')
      const blob = await api.download(`/api/papers/${paper.id}/material-states/${encodeURIComponent(state.state_key)}/export`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${materialLabel(state) || 'material-state'}-revision-${paper.content_revision || paper.revision || 1}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (reason) {
      setExportError(reason instanceof Error ? reason.message : '材料状态导出失败')
    }
  }

  // 化学式来自 MaterialState；Read switch 后不再依赖旧 key_properties。
  const formula = paper?.material_states?.[0]?.material || (paper?.materials?.[0]) || '-'

  // 论文数据由 props 传入；同步到本地展示状态，切换论文时重新填充
  useEffect(() => {
    const data = paper || {}
    setEditTitle(data.title || '')
    setEditDoi(data.doi || '')
    setEditJournal(data.journal || '')
    setEditYear(data.year || '')
    // authors 同为 JSON 文本列，直接展示会把 ["A","B"] 原样印到页面上；
    // 分隔符随界面语言：中文顿号、英文逗号。
    setEditAuthors(toTextList(data.authors).join(lang === 'zh' ? '、' : ', '))
    setEditAbstract(data.abstract || '')
    setEditSummary(data.summary || '')
    setEditKnowledgeGraphTitle(data.knowledge_graph_title || '')
    setEditKeyFinding(data.key_finding || '')
    setEditResearchMotivation(data.research_motivation || '')
  }, [paper, lang])

  // 研究方法与关键词处理：转为可读列表
  const methodologyList = toTextList(paper?.methodology)
  const keywordList = toTextList(paper?.keywords_tags)

  return (
    <PropertySpectraProvider context={{ target: { target: 'paper', target_id: String(paper.id) } }}>
    <Box data-paper-detail>
      <PaperStructuralCollection paperId={paper.id} />
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, mb: 3 }}>
        <Box>
          <Button size="small" startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 1 }}>
            {t('paperDetail.backToUpload')}
          </Button>
          <Typography variant="overline" color="text.secondary">{t('paperDetail.readOnlyMode')}</Typography>
          <Typography variant="h4" fontWeight={800}>{t('paperDetail.paperDetailTitle')}</Typography>
        </Box>
        {/* 离开详情页后仍能经界面回到任意已提交论文，无需手工拼接网址 */}
        {onOpenMyPapers && (
          <Button size="small" variant="outlined" onClick={onOpenMyPapers}>{t('paperDetail.myPapers')}</Button>
        )}
      </Box>

      {paper.can_revise ? <Box sx={{ mb: 2 }}>
        <Alert severity="info" sx={{ mb: 1 }}>{t('paperDetail.revisionAvailable')}</Alert>
        {paper.review_comment && <Alert severity="warning" sx={{ mb: 1 }}>{paper.review_comment}</Alert>}
        <Button component={Link} variant="contained" to={`/papers/${paper.id}/revise`}>{t('paperDetail.revise')}</Button>
      </Box> : <Alert severity="info" sx={{ mb: 2 }}>{t('paperDetail.submittedNotice')}</Alert>}

      <Box sx={{
        display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 3, alignItems: 'start',
        '@media (max-width:1180px)': { gridTemplateColumns: '1fr' },
      }}>
        {/* Main content */}
        <Card sx={{ boxShadow: 3 }}>
          <CardContent>
            {/* 基础信息 */}
            <Box component="details" open sx={{
              border: '1px solid', borderColor: 'divider', borderRadius: 2, mb: 1.5, overflow: 'hidden',
            }}>
              <Box component="summary" sx={{ cursor: 'pointer', p: 2, fontSize: 18, fontWeight: 800 }}>
                {t('paperDetail.basicInfo')}
              </Box>
              <Box sx={{ px: 2, pb: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldTitle')}</Typography>
                    <Typography variant="body2">{editTitle || '-'}</Typography>
                  </Box>
                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
                    <Box>
                      {/* DOI 为专有名词，两种语言下写法一致 */}
                      <Typography variant="caption" color="text.secondary">DOI</Typography>
                      <Typography variant="body2">{editDoi || '-'}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldYear')}</Typography>
                      <Typography variant="body2">{editYear || '-'}</Typography>
                    </Box>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldJournal')}</Typography>
                    <Typography variant="body2">{editJournal || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldAuthors')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{editAuthors || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldAbstract')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{editAbstract || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldSummary')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{editSummary || '-'}</Typography>
                  </Box>
                  {(paper.material_families || []).length > 0 && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldMaterialFamily')}</Typography>
                      <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mt: 0.5 }}>
                        {paper.material_families.map((family: any) => (
                          <Chip key={family.id ?? family.name} size="small" label={familyName(family, lang)} />
                        ))}
                      </Box>
                    </Box>
                  )}
                  {paper.superconductor_kind && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldSuperconductorKind')}</Typography>
                      <Typography variant="body2">{paper.superconductor_kind}</Typography>
                    </Box>
                  )}
                  {editKnowledgeGraphTitle && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">{t('paperDetail.fieldKgTitle')}</Typography>
                      <Typography variant="body2">{editKnowledgeGraphTitle}</Typography>
                    </Box>
                  )}
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip label={`${t('paperDetail.reviewStatus')}: ${reviewStatusLabel(dict, paper?.review_status) || reviewStatusLabel(dict, 'pending')}`}
                      size="small" color={STATUS_COLORS[paper?.review_status] || 'default'} />
                    <Chip label={`${t('paperDetail.dataSource')}: Local`} size="small" color="primary" />
                    {paper?.id && <Chip label={`ID: ${paper.id}`} size="small" variant="outlined" />}
                  </Box>
                </Box>
              </Box>
            </Box>

            <PaperMaterialsSection states={paper.material_states || []} historicalMaterials={paper.research_materials} />
            {/* 材料状态 */}
            {(paper.material_states || []).length > 0 ? (
              <Box component="details" open sx={{
                border: '1px solid', borderColor: 'divider', borderRadius: 2, mb: 1.5, overflow: 'hidden',
              }}>
                <Box component="summary" sx={{ cursor: 'pointer', p: 2, fontSize: 18, fontWeight: 800 }}>
                  {t('paperDetail.materialStates')}
                </Box>
                <Box sx={{ px: 2, pb: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {(paper.material_states || []).map((state: any, index: number) => (
                    <Box id={`material-state-${state.state_key || `state-${index+1}`}`} key={state.state_key || state.id || index} data-material-state-index={index} data-state-key={state.state_key} tabIndex={-1} sx={{
                      p: 2, borderRadius: 2, bgcolor: 'grey.50', border: '1px solid', borderColor: 'divider',
                    }}>
                      {/* 分类区 */}
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
                        <Typography variant="subtitle2" fontWeight={700}>
                          {materialStateSummary(state)}
                        </Typography>
                        {state.state_key && <Button size="small" startIcon={<DownloadIcon />} onClick={() => void downloadMaterialState(state)}>导出材料状态</Button>}
                      </Box>
                      {exportError && <Alert severity="error" sx={{ mb: 1 }}>{exportError}</Alert>}

                      <Box data-material-basics sx={{ display: 'grid', gap: 1.5, mb: 2, minWidth: 0 }}>
                        <Box data-material-identity-row sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(7, minmax(0, 1fr))' }, gap: 1.5 }}>
                          {[
                            [t('upload.materialNameField'), state.material_name],
                            [t('upload.materialField'), state.material],
                            [t('paperDetail.fieldElementCount'), state.element_count],
                            [t('paperDetail.fieldDimensionality'), state.material_dimensionality],
                            [t('paperDetail.fieldCrystalSystem'), state.crystal_system],
                            [t('paperDetail.fieldSpaceGroupSymbol'), state.reported_space_group_symbol],
                            [t('paperDetail.fieldSpaceGroupNumber'), state.reported_space_group_number],
                          ].map(([label, value]) => <Box key={label} sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                            <Typography variant="caption" color="text.secondary">{label}</Typography>
                            <Typography variant="body2">{value ?? t('common.notProvided')}</Typography>
                          </Box>)}
                        </Box>
                        <Box data-material-condition-row sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: state.state_kind === 'theoretical' ? 'repeat(3, minmax(0, 1fr))' : 'repeat(2, minmax(0, 1fr))' }, gap: 1.5 }}>
                          <Box>
                            <Typography variant="caption" color="text.secondary">{t('upload.stateKindField')}</Typography>
                            <Typography variant="body2">{(dict.enums.stateKind as Record<string, string>)[state.state_kind || 'unknown'] || state.state_kind}</Typography>
                          </Box>
                          {state.state_kind === 'theoretical' && <Box>
                            <Typography variant="caption" color="text.secondary">{t('upload.structureOptimizationField')}</Typography>
                            <Typography variant="body2">{(dict.enums.structureOptimization as Record<string, string>)[state.structure_optimization || 'unknown']}</Typography>
                          </Box>}
                          <Box>
                            <Typography variant="caption" color="text.secondary">{t('paperDetail.pressureSection')}</Typography>
                            <Typography variant="body2">{state.pressure_value_gpa != null ? `${state.pressure_value_gpa} GPa` : state.pressure_min_gpa != null || state.pressure_max_gpa != null ? `${state.pressure_min_gpa ?? '?'}–${state.pressure_max_gpa ?? '?'} GPa` : state.pressure_raw ? `${state.pressure_raw}${state.pressure_unit_raw ? ` ${state.pressure_unit_raw}` : ''}` : t('common.notProvided')}</Typography>
                          </Box>
                        </Box>
                        <Box data-material-family-row sx={{ minWidth: 0 }}>
                          <Typography variant="caption" color="text.secondary">{t('paperDetail.structureFamiliesLabel')}</Typography>
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'nowrap', overflowX: 'auto', alignItems: 'center', height: 36, '& .MuiChip-root': { flexShrink: 0 } }}>
                            {(state.structure_families || []).map((family: any) => <Chip key={family.id || family.name} size="small" label={familyName(family, lang)} />)}
                          </Box>
                        </Box>
                      </Box>

                      <PropertySpectrumState stateKey={state.state_key || `state-${index + 1}`} summary={materialStateSummary(state)}>
                        <PropertyModuleEditor modules={state.property_modules || []} readOnly onChange={() => undefined} />
                      </PropertySpectrumState>
                      <Box sx={{ mt: 2 }}>
                        <PropertyModuleSection title={t('upload.crystalStructureTitle')}>
                        {(state.structures || []).filter((structure: any) => structure.structure_text).length ? (state.structures || []).filter((structure: any) => structure.structure_text).map((structure: any, structureIndex: number) => <Box key={structure.id || structureIndex} sx={{ mt: 2 }}>
                          <Typography variant="body2" fontWeight={600} gutterBottom>{structure.filename || `${materialLabel(state)} · ${t('paperDetail.structureIndex', { n: structureIndex + 1 })}`} ({structure.structure_format || 'cif'})</Typography>
                          <CrystalStructureView data={structure.structure_text} format={structure.structure_format || 'cif'} />
                        </Box>) : <Typography variant="body2" color="text.secondary">{t('paperDetail.noStructure')}</Typography>}
                        </PropertyModuleSection>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            ) : (
              <Alert severity="info" sx={{ mb: 1.5 }}>{t('paperDetail.noMaterialStates')}</Alert>
            )}

            {/* 研究方法与发现 */}
            <Box component="details" sx={{
              border: '1px solid', borderColor: 'divider', borderRadius: 2, mb: 1.5, overflow: 'hidden',
            }}>
              <Box component="summary" sx={{ cursor: 'pointer', p: 2, fontSize: 18, fontWeight: 800 }}>
                {t('paperDetail.methodsFindings')}
              </Box>
              <Box sx={{ px: 2, pb: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.methodology')}</Typography>
                    {methodologyList.length > 0 ? (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                        {methodologyList.map((method, idx) => (
                          <Typography key={idx} variant="body2">• {method}</Typography>
                        ))}
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary">-</Typography>
                    )}
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.keyFinding')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{editKeyFinding || '-'}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t('paperDetail.researchMotivation')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{editResearchMotivation || '-'}</Typography>
                  </Box>
                </Box>
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* Sidebar */}
        <Card sx={{ position: 'sticky', top: 20, boxShadow: 3 }}>
          <CardContent>
            <Typography variant="overline" color="text.secondary">{t('paperDetail.formulaLabel')}</Typography>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 2, wordBreak: 'break-word' }}>
              {formula}
            </Typography>

            {keywordList.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">{t('paperDetail.keywordsLabel')}</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                  {keywordList.map((kw, idx) => (
                    <Chip key={idx} label={kw} size="small" />
                  ))}
                </Box>
              </Box>
            )}

          </CardContent>
        </Card>
      </Box>

    </Box>
    </PropertySpectraProvider>
  )
}

export default PaperEditView
