import { Box, Button, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { locateMaterialState, type MaterialSummaryState } from '../lib/paperMaterials'
import { toTextList } from '../lib/paperTextLists'

interface Props {
  states: MaterialSummaryState[]
  historicalMaterials?: unknown
}

export default function PaperMaterialsSection({ states, historicalMaterials }: Props) {
  const { t } = useLanguage()
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
  </Box>
}
