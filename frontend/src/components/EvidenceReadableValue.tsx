import { Box, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'

const labels: Record<'zh' | 'en', Record<string, string>> = {
  zh: {
    authors: '作者', co_first_authors: '共同第一作者', corresponding_authors: '通讯作者',
    material: '材料', pressure_value_gpa: '压强 (GPa)', value_raw: '原始值',
    field_settings: '字段标注', name_raw: '名称', unit_raw: '单位', cell_parameters: '晶胞参数',
    space_group_symbol: '空间群', rule: '规则', input: '输入',
  },
  en: {
    authors: 'Authors', co_first_authors: 'Co-first authors', corresponding_authors: 'Corresponding authors',
    material: 'Material', pressure_value_gpa: 'Pressure (GPa)', value_raw: 'Original value',
    field_settings: 'Field annotations', name_raw: 'Name', unit_raw: 'Unit', cell_parameters: 'Cell parameters',
    space_group_symbol: 'Space group', rule: 'Rule', input: 'Input',
  },
}

/** 侧栏不展示原始 JSON；递归把列表和字段组转成可阅读的内容。 */
export default function EvidenceReadableValue({ value }: { value: unknown }) {
  const { lang } = useLanguage()
  if (value == null || value === '') return <Typography color="text.secondary">—</Typography>
  if (Array.isArray(value)) return <Box component="ul" sx={{ my: 0.5, pl: 2.5 }}>
    {value.map((item, index) => <Box component="li" key={index} sx={{ mb: 0.5 }}><EvidenceReadableValue value={item} /></Box>)}
  </Box>
  if (typeof value === 'object') return <Box component="dl" sx={{ my: 0.5, display: 'grid', gap: 0.75 }}>
    {Object.entries(value).filter(([key]) => !['source_associations', 'table_row_ref', 'tc_group', 'tc_range_origin', 'field_key', 'validation_record'].includes(key)).map(([key, item]) => <Box key={key} sx={{ overflowWrap: 'anywhere' }}>
      <Typography component="dt" variant="caption" color="text.secondary">{labels[lang][key] || key.replaceAll('_', ' ')}</Typography>
      <Box component="dd" sx={{ m: 0 }}><EvidenceReadableValue value={item} /></Box>
    </Box>)}
  </Box>
  return <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{String(value)}</Typography>
}
