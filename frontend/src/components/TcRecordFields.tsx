import { useEffect, useId, useRef, useState } from 'react'
import {
  Box, Checkbox, FormControl, FormControlLabel, InputAdornment, InputLabel,
  MenuItem, Select, TextField,
} from '@mui/material'
import type { PropertyRecordDraft, PropertyValueKind } from '../lib/propertyModules'

interface Props {
  record: PropertyRecordDraft
  readOnly: boolean
  issue: (field: string) => string | undefined
  fieldPath: (field: string) => string
  update: (patch: Partial<PropertyRecordDraft>) => void
}

const numberPattern = /^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/

/** 编辑中的小数/指数保留为文本；无效时向表单写 null，保存校验不能读到旧值。 */
function TcNumber({ value, label, field, error, readOnly, onChange }: {
  value?: number | null; label: string; field: string; error?: string; readOnly: boolean
  onChange: (value: number | null) => void
}) {
  const [text, setText] = useState(String(value ?? ''))
  const published = useRef(value)
  useEffect(() => {
    if (!Object.is(value, published.current)) setText(String(value ?? ''))
    published.current = value
  }, [value])
  const valid = numberPattern.test(text) && Number.isFinite(Number(text))
  const message = text !== '' && !valid ? '请输入完整的非负 Tc 数值' : error
  return <TextField size="small" fullWidth label={label} value={text} disabled={readOnly}
    data-issue-field={field} data-tc-current-value error={Boolean(message)} helperText={message}
    slotProps={{ htmlInput: { inputMode: 'decimal' }, input: { endAdornment: <InputAdornment position="end">K</InputAdornment> } }}
    onChange={event => {
      const next = event.target.value
      setText(next)
      const number = numberPattern.test(next) && Number.isFinite(Number(next)) ? Number(next) : null
      published.current = number
      onChange(number)
    }} />
}

export default function TcRecordFields({ record, readOnly, issue, fieldPath, update }: Props) {
  const kindLabel = useId()
  const numeric = (field: 'value_number' | 'value_min' | 'value_max', label: string) => (
    <TcNumber key={field} value={record[field]} label={label} field={fieldPath(field)} error={issue(field)}
      readOnly={readOnly} onChange={value => update({ [field]: value })} />
  )
  const changeKind = (kind: PropertyValueKind) => {
    if (kind === record.value_kind) return
    update({ value_kind: kind, value_number: null, value_min: null, value_max: null,
      value_text: kind === 'text' ? '' : null, value_boolean: kind === 'boolean' ? false : null })
  }
  return <Box data-testid="tc-core-row" sx={{ display: 'grid', gridColumn: '1 / -1', alignItems: 'start', gap: 1,
    gridTemplateColumns: 'minmax(0, 1fr)', '& > *': { minWidth: 0 },
    '@container tc-record (min-width: 400px)': { gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' },
    '@container tc-record (min-width: 640px)': { gridTemplateColumns: 'minmax(160px, 1.5fr) 104px minmax(190px, 1fr) auto' },
  }}>
    <TextField size="small" label="名称" value={record.name_raw} disabled={readOnly}
      data-issue-field={fieldPath('name_raw')} error={Boolean(issue('name_raw'))} helperText={issue('name_raw')}
      onChange={event => update({ name_raw: event.target.value })} />
    <FormControl size="small" data-issue-field={fieldPath('value_kind')} error={Boolean(issue('value_kind'))}>
      <InputLabel id={kindLabel}>值类型</InputLabel>
      <Select labelId={kindLabel} label="值类型" value={record.value_kind} disabled={readOnly} onChange={event => changeKind(event.target.value as PropertyValueKind)}>
        <MenuItem value="number">数值</MenuItem><MenuItem value="range">范围</MenuItem>
        <MenuItem value="text">文本</MenuItem><MenuItem value="boolean">布尔</MenuItem>
      </Select>
    </FormControl>
    {record.value_kind === 'number' && numeric('value_number', 'Tc 值')}
    {record.value_kind === 'range' && <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
      {numeric('value_min', '下界')}{numeric('value_max', '上界')}
    </Box>}
    {record.value_kind === 'text' && <TextField size="small" label="文本值" value={record.value_text ?? ''} disabled={readOnly}
      data-issue-field={fieldPath('value_text')} data-tc-current-value error={Boolean(issue('value_text'))} helperText={issue('value_text')}
      onChange={event => update({ value_text: event.target.value })} />}
    {record.value_kind === 'boolean' && <FormControlLabel label="布尔值" data-issue-field={fieldPath('value_boolean')} data-tc-current-value
      control={<Checkbox checked={Boolean(record.value_boolean)} disabled={readOnly} onChange={event => update({ value_boolean: event.target.checked })} />} />}
    <FormControlLabel label="代表结果" data-issue-field={fieldPath('is_representative')} sx={{ m: 0, whiteSpace: 'nowrap' }}
      control={<Checkbox checked={Boolean(record.is_representative)} disabled={readOnly} onChange={event => update({ is_representative: event.target.checked })} />} />
  </Box>
}
