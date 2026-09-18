import { Alert, Box, Button, IconButton, TextField, Tooltip, Typography } from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { useLanguage } from '../context/LanguageContext'
import { locateMaterialState, parseMaterialRelations, type MaterialRelation, type MaterialSummaryState } from '../lib/paperMaterials'
import { toTextList } from '../lib/paperTextLists'

interface Props {
  states: MaterialSummaryState[]
  relations: unknown
  historicalMaterials?: unknown
  onChange?: (relations: MaterialRelation[]) => void
}

export default function PaperMaterialsSection({ states, relations, historicalMaterials, onChange }: Props) {
  const { t } = useLanguage()
  const rows = parseMaterialRelations(relations)
  const materials = new Map<string, { name: string; formula: string; indices: number[] }>()
  states.forEach((state, index) => {
    const name = state.material_name?.trim() || state.material?.trim() || t('upload.materialStateNumber', { index: index + 1 })
    const formula = state.material?.trim() || ''
    const key = `${name}\n${formula}`
    const item = materials.get(key) || { name, formula, indices: [] }
    item.indices.push(index)
    materials.set(key, item)
  })
  return <Box sx={{ my: 2, minWidth: 0 }}>
    <Box data-issue-field="paper.research_materials" sx={{ mb: 2 }}>
      <Typography variant="subtitle1" fontWeight={700}>{t('upload.researchMaterialsTitle')}</Typography>
      {[...materials.values()].map((item, i) => <Box key={i} sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', py: 0.75, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{item.name}{item.formula && item.name !== item.formula ? ` (${item.formula})` : ''}</Typography>
        {item.indices.map(index => <Button key={index} size="small" sx={{ overflowWrap: 'anywhere', minWidth: 0 }} onClick={event => locateMaterialState(event.currentTarget, index)}>{item.name} · #{index + 1}</Button>)}
      </Box>)}
      {!materials.size && <Typography variant="body2">{toTextList(historicalMaterials).join(t('upload.listSeparator')) || t('common.notProvided')}</Typography>}
    </Box>
    <Box data-issue-field="paper.material_relations">
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1 }}>
        <Typography variant="subtitle1" fontWeight={700}>{t('upload.materialRelationsTitle')}</Typography>
        {onChange && rows && <Button size="small" startIcon={<AddIcon />} onClick={() => onChange([...rows, { material: '', relation: '' }])}>{t('upload.addRelation')}</Button>}
      </Box>
      {!rows ? <Alert severity="warning">{t('upload.invalidRelations')}</Alert> : rows.length === 0 ? <Typography variant="body2" color="text.secondary">{t('upload.noRelations')}</Typography> : rows.map((row, index) => <Box key={index} data-issue-field={`paper.material_relations[${index}]`} sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr) auto', sm: 'minmax(110px, 1fr) minmax(0, 3fr) auto' }, gap: 1, py: 1, borderBottom: 1, borderColor: 'divider' }}>
        {onChange ? <>
          <TextField size="small" label={t('upload.relationMaterial')} value={row.material || ''} sx={{ gridColumn: { xs: '1 / -1', sm: 'auto' } }} onChange={e => onChange(rows.map((item, i) => i === index ? { ...item, material: e.target.value } : item))} />
          <TextField size="small" multiline minRows={1} label={t('upload.relationDescription')} value={row.relation || ''} onChange={e => onChange(rows.map((item, i) => i === index ? { ...item, relation: e.target.value } : item))} />
          <Tooltip title={t('upload.removeRelation')}><IconButton aria-label={t('upload.removeRelation')} sx={{ alignSelf: 'start' }} onClick={() => onChange(rows.filter((_, i) => i !== index))}><DeleteOutlineIcon /></IconButton></Tooltip>
        </> : <>
          <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{row.material || t('common.notProvided')}</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', gridColumn: { xs: '1 / -1', sm: '2 / -1' } }}>{row.relation || t('common.notProvided')}</Typography>
        </>}
      </Box>)}
    </Box>
  </Box>
}
