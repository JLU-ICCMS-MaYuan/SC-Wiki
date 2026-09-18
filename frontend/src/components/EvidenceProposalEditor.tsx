import { Box, Checkbox, FormControlLabel, MenuItem, TextField } from '@mui/material'

export interface ProposalSchema { type: string; enum?: string[]; items?: ProposalSchema; properties?: Record<string, ProposalSchema> }
export interface ProposalField { path: string; label: string; value: unknown; schema: ProposalSchema }

/** 按科学字段类型编辑候选；保留原表单的域校验作为提交边界。 */
export function EvidenceValueEditor({ label, schema, value, disabled, onChange }: {
  label: string; schema: ProposalSchema; value: unknown; disabled?: boolean; onChange: (value: unknown) => void
}) {
  if (schema.type === 'object') return <Box sx={{ display: 'grid', gap: 1.5 }}>{Object.entries(schema.properties || {}).map(([key, child]) =>
    <EvidenceValueEditor key={key} label={`${label} · ${key}`} schema={child} value={(value as Record<string, unknown> | undefined)?.[key]} disabled={disabled}
      onChange={next => onChange({ ...(value as Record<string, unknown>), [key]: next })} />)}</Box>
  if (schema.type === 'array') return schema.items?.type === 'string'
    ? <TextField fullWidth multiline minRows={3} label={label} disabled={disabled} value={Array.isArray(value) ? value.join('\n') : ''} onChange={e => onChange(e.target.value.split('\n'))} />
    : <Box sx={{ display: 'grid', gap: 1 }}>{(Array.isArray(value) ? value : []).map((item, index) => <EvidenceValueEditor key={index} label={`${label} ${index + 1}`} schema={schema.items || { type: 'string' }} value={item} disabled={disabled} onChange={next => onChange((value as unknown[]).map((v, i) => i === index ? next : v))} />)}</Box>
  if (schema.type === 'boolean') return <FormControlLabel label={label} control={<Checkbox checked={value === true} disabled={disabled} onChange={e => onChange(e.target.checked)} />} />
  const numeric = schema.type === 'number' || schema.type === 'integer'
  return <TextField fullWidth label={label} disabled={disabled} select={Boolean(schema.enum)} type={numeric ? 'number' : 'text'}
    multiline={!numeric && !schema.enum} minRows={!numeric && !schema.enum ? 4 : undefined} value={value ?? ''}
    onChange={e => onChange(numeric && e.target.value !== '' ? Number(e.target.value) : e.target.value)}>
    {schema.enum?.map(option => <MenuItem key={option} value={option}>{option}</MenuItem>)}
  </TextField>
}
