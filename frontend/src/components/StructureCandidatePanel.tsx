import React, { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Alert, Box, Button, ButtonBase, Chip, CircularProgress, Divider, FormControl, InputLabel, MenuItem, Select, Stack, Typography } from '@mui/material'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import DownloadIcon from '@mui/icons-material/Download'
import BlockIcon from '@mui/icons-material/Block'
import RestoreIcon from '@mui/icons-material/Restore'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import CrystalStructureView from './CrystalStructureView'
import { StructureRoundingNotice } from './StructureCandidateSource'
import { StructureCandidate } from '../lib/paperProcessing'
import { useLanguage } from '../context/LanguageContext'

interface Props {
  hasCanonicalStructure?: boolean
  materialName?: string
  candidates: StructureCandidate[]
  uploading: boolean
  readOnly?: boolean
  onUpload: (file: File) => void
  onChange: (candidateId: string, changes: Partial<StructureCandidate>) => void
}

type CellKind = 'primitive' | 'conventional'
type StructureFormat = 'cif' | 'poscar'

const StructureCandidatePanel: React.FC<Props> = ({ candidates, uploading, readOnly = false, onUpload, onChange, hasCanonicalStructure }) => {
  const { t } = useLanguage()
  const preferredCandidate = useMemo(
    () => [...candidates].reverse().find(candidate => candidate.confirmation !== 'excluded') || candidates.at(-1),
    [candidates],
  )
  const [selectedCandidateId, setSelectedCandidateId] = useState(preferredCandidate?.candidate_id || '')
  const [cell, setCell] = useState<CellKind>('conventional')
  const [format, setFormat] = useState<StructureFormat>('cif')
  const [expanded, setExpanded] = useState(false)
  const contentId = useId()
  const cellLabelId = useId()
  const formatLabelId = useId()
  const previousCandidateCount = useRef(candidates.length)

  useEffect(() => {
    const candidateAdded = candidates.length > previousCandidateCount.current
    const selectionMissing = !candidates.some(candidate => candidate.candidate_id === selectedCandidateId)
    if (candidateAdded || selectionMissing) {
      setSelectedCandidateId(preferredCandidate?.candidate_id || '')
    }
    if (candidateAdded) setExpanded(true)
    previousCandidateCount.current = candidates.length
  }, [candidates, preferredCandidate, selectedCandidateId])

  const candidate = candidates.find(item => item.candidate_id === selectedCandidateId) || preferredCandidate

  const download = (candidate: StructureCandidate, cell: CellKind, format: StructureFormat) => {
    const representation = candidate.representations?.[cell]?.[format]
    if (!representation?.text) return
    const blob = new Blob([representation.text], { type: format === 'cif' ? 'chemical/x-cif' : 'text/plain' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${candidate.candidate_id}-${cell}.${format === 'poscar' ? 'POSCAR' : 'cif'}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const representation = candidate?.representations?.[cell]?.[format]
  const preview = representation?.text
    ? { text: representation.text, format: format === 'poscar' ? 'vasp' : 'cif' }
    : null
  const anotherGeometry = hasCanonicalStructure || candidates.some(item => item.candidate_id !== candidate?.candidate_id && item.confirmation === 'confirmed' && item.status === 'confirmed')
  const blocked = candidate?.status === 'blocked'
    || (candidate?.source_kind?.startsWith('pdf') && candidate.validation?.ase_valid !== true)
  const decided = candidate?.confirmation === 'confirmed' || candidate?.confirmation === 'excluded'
  const filename = [...new Set(candidate?.sources?.map(source => String(source.filename || '')).filter(Boolean) || [])].join(t('upload.listSeparator'))
  const statusLabel = blocked
    ? t('upload.structureStatusBlocked')
    : candidate?.confirmation === 'confirmed'
      ? t('upload.structureStatusConfirmed')
      : candidate?.confirmation === 'excluded'
        ? t('upload.structureStatusExcluded')
        : candidate?.status === 'valid'
          ? t('upload.structureStatusValid')
          : t('upload.structureStatusReview')
  const cellLabel = cell === 'conventional' ? t('upload.cell.conventional') : t('upload.cell.primitive')
  const formatLabel = format === 'cif' ? 'CIF' : 'POSCAR'

  return (
    <Box data-structure-attachment data-scientific-structure={candidate ? true : undefined} data-structure-hash={candidate?.validation?.structure_hash} data-structure-id={candidate?.candidate_id} sx={{ mt: 2, minWidth: 0, pointerEvents: 'auto', ...(readOnly ? { '& .MuiButton-root': { display: 'inline-flex' } } : {}) }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ minHeight: 40 }}>
        <ButtonBase aria-expanded={expanded} aria-controls={contentId} onClick={() => setExpanded(value => !value)} sx={{ minWidth: 0, flex: 1, justifyContent: 'flex-start', textAlign: 'left', gap: 0.5, minHeight: 40, borderRadius: 1, '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 } }}>
          <ChevronRightIcon fontSize="small" sx={{ flexShrink: 0, transform: expanded ? 'rotate(90deg)' : undefined }} />
          <Typography component="span" variant="subtitle2" fontWeight={700}>{t('upload.crystalStructureTitle')}</Typography>
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>{uploading ? t('upload.validating') : candidate ? statusLabel : t('upload.structureStatusEmpty')}</Typography>
        </ButtonBase>
        {candidate && <Typography data-evidence-readonly data-structure-field="structure_text" component="span" variant="caption" sx={{ flexShrink: 0 }}>{t('upload.structureSourceReview')}</Typography>}
      </Stack>
      {/* 隐藏而不卸载，保留画布、视角和选择；来源入口独立于折叠按钮。 */}
      <Box id={contentId} hidden={!expanded}>
        {anotherGeometry && <Alert severity="info" sx={{ mt: 1 }}>{t('upload.singleStructureHelp')}</Alert>}
        {!readOnly && <Button component="label" size="small" variant="outlined" startIcon={uploading ? <CircularProgress size={16} /> : <UploadFileIcon />} disabled={uploading} sx={{ mt: 1.5 }}>
          {uploading ? t('upload.validating') : t('upload.uploadStructure')}
          <input hidden type="file" accept=".cif,.poscar,.vasp,POSCAR,CONTCAR" onChange={event => {
            const selected = event.target.files?.[0]
            event.target.value = ''
            if (selected) { setExpanded(true); onUpload(selected) }
          }} />
        </Button>}
        {!candidate && <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>{t('paperDetail.noStructure')}</Typography>}
        {candidate && <Box sx={{ mt: 1.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={1}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ overflowWrap: 'anywhere' }}>{filename || candidate.candidate_id}</Typography>
            <Chip size="small" label={statusLabel} color={blocked ? 'warning' : candidate.confirmation === 'confirmed' ? 'success' : 'default'} />
          </Stack>
          <StructureRoundingNotice candidate={candidate} />
          {candidates.length > 1 && (
            <Select fullWidth size="small" value={candidate.candidate_id} aria-label={t('upload.candidateSelectAria')} onChange={event => setSelectedCandidateId(String(event.target.value))} sx={{ mt: 1.5 }}>
              {candidates.map(item => (
                <MenuItem key={item.candidate_id} value={item.candidate_id}>
                  {item.sources?.map(source => String(source.filename || '')).filter(Boolean).join(t('upload.listSeparator')) || item.candidate_id}
                </MenuItem>
              ))}
            </Select>
          )}

          {blocked
            ? <Box sx={{ mt: 1.5 }}>
                <Alert severity="warning">{candidate.validation?.message || t('upload.blockedValidation')}</Alert>
                {candidate.reported_structure?.cell_parameters && (
                  <Typography variant="body2" sx={{ mt: 1, overflowWrap: 'anywhere' }}>
                    {Object.entries(candidate.reported_structure.cell_parameters).map(([name, value]) => `${name}=${value}`).join(' · ')}
                  </Typography>
                )}
                {candidate.sources?.map((source, index) => <Typography key={index} variant="caption" color="text.secondary" display="block" sx={{ mt: 0.75, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                  {[source.filename, source.page && `${t('upload.pageRef', { page: source.page as number })}`].filter(Boolean).join(' · ')}：{String(source.quote || '')}
                </Typography>)}
              </Box>
            : preview
              ? (
                  <Box sx={{ mt: 1.5 }}>
                    <CrystalStructureView data={preview.text} format={preview.format} reviewFields={cell === 'conventional'} />
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.75 }}>
                      {t('upload.currentDisplay', { cell: cellLabel, format: formatLabel })}
                    </Typography>
                  </Box>
                )
              : <Alert severity="info" sx={{ mt: 1.5 }}>{t('upload.missingRepresentation', { cell: cellLabel, format: formatLabel })}</Alert>}

          {!blocked && (
            <>
              <Divider sx={{ my: 1.5 }} />
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1.5 }}>
                <FormControl size="small" sx={{ minWidth: 104 }}>
                  <InputLabel id={cellLabelId}>{t('upload.cellRepresentation')}</InputLabel>
                  <Select labelId={cellLabelId} label={t('upload.cellRepresentation')} value={cell} onChange={event => setCell(event.target.value as CellKind)}>
                    <MenuItem value="conventional">{t('upload.cell.conventional')}</MenuItem>
                    <MenuItem value="primitive">{t('upload.cell.primitive')}</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 104 }}>
                  <InputLabel id={formatLabelId}>{t('upload.structureFormat')}</InputLabel>
                  <Select labelId={formatLabelId} label={t('upload.structureFormat')} value={format} onChange={event => setFormat(event.target.value as StructureFormat)}>
                    <MenuItem value="cif">CIF</MenuItem>
                    <MenuItem value="poscar">POSCAR</MenuItem>
                  </Select>
                </FormControl>
                <Button startIcon={<DownloadIcon />} variant="outlined" disabled={!representation?.text} onClick={() => download(candidate, cell, format)}>{t('upload.downloadStructure')}</Button>
                {!readOnly && (decided
                  ? (
                      <Button startIcon={<RestoreIcon />} color="inherit" onClick={() => onChange(candidate.candidate_id, { confirmation: 'unreviewed', status: 'valid' })}>
                        {t('upload.restoreToPending')}
                      </Button>
                    )
                  : (
                      <>
                        <Button startIcon={<CheckCircleOutlineIcon />} variant="contained" color="success" disabled={candidate.status !== 'valid' || anotherGeometry} onClick={() => onChange(candidate.candidate_id, { confirmation: 'confirmed', status: 'confirmed' })}>{t('upload.adoptStructure')}</Button>
                        <Button startIcon={<BlockIcon />} color="inherit" onClick={() => onChange(candidate.candidate_id, { confirmation: 'excluded', status: 'excluded' })}>{t('upload.excludeStructure')}</Button>
                      </>
                    ))}
              </Stack>
            </>
          )}
        </Box>}
      </Box>
    </Box>
  )
}

export default StructureCandidatePanel
