import { Box, FormControl, InputLabel, MenuItem, Select, TextField } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { draftNumber } from '../lib/fieldDrafts'

/** 状态几何工作流详情；不向物性结果写入计算条件。 */
export default function StructureOptimizationFields({ value, basePath, readOnly, onChange }: {
  value?: Record<string, unknown> | null; basePath: string; readOnly: boolean
  onChange: (value: Record<string, unknown>) => void
}) {
  const { lang } = useLanguage()
  const labels = lang === 'zh'
    ? { method: '结构优化方法', electronic_method: '优化求力电子理论', calculation_code: '结构优化软件',
        temperature_k: '优化温度 (K)', pressure_gpa: '优化外压 (GPa)', centroids: '原子平均位置', volume: '体积', cell_shape: '晶胞形状' }
    : { method: 'Geometry optimization method', electronic_method: 'Force calculator theory', calculation_code: 'Geometry optimization software',
        temperature_k: 'Optimization temperature (K)', pressure_gpa: 'External pressure (GPa)', centroids: 'Atomic centroids', volume: 'Volume', cell_shape: 'Cell shape' }
  const data = value || {}
  const set = (key: string, next: unknown) => onChange({ ...data, [key]: next })
  return <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
    {(['method', 'electronic_method', 'calculation_code', 'temperature_k', 'pressure_gpa'] as const).map(key =>
      <TextField key={key} label={labels[key]} value={data[key] ?? ''} disabled={readOnly} size="small"
        data-issue-field={basePath + '.' + key}
        onChange={event => set(key, key === 'temperature_k' || key === 'pressure_gpa' ? draftNumber(event.target.value) : event.target.value)} />)}
    {(['centroids', 'volume', 'cell_shape'] as const).map(key =>
      <FormControl key={key} size="small" sx={{ minWidth: 140 }} data-issue-field={basePath + '.' + key}>
        <InputLabel id={basePath + '.' + key}>{labels[key]}</InputLabel>
        <Select labelId={basePath + '.' + key} label={labels[key]} value={data[key] || 'unknown'} disabled={readOnly}
          onChange={event => set(key, event.target.value)}>
          <MenuItem value="unknown">{lang === 'zh' ? '未说明' : 'Unspecified'}</MenuItem>
          <MenuItem value="fixed">{lang === 'zh' ? '固定' : 'Fixed'}</MenuItem>
          <MenuItem value="optimized">{lang === 'zh' ? '已优化' : 'Optimized'}</MenuItem>
        </Select>
      </FormControl>)}
  </Box>
}
