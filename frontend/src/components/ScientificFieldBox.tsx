import { Box, Button, TextField } from '@mui/material'

/** 主表单仅显示字段名称与值，元数据由右侧设置负责。 */
export default function ScientificFieldBox({ name, value, readOnly, numeric, field, error, fullWidth = false, onSettings, onChange }: {
  name: string; value: string; readOnly: boolean; numeric?: boolean; field: string; error?: string
  fullWidth?: boolean; onSettings: () => void; onChange?: (value: string) => void
}) {
  return <Box data-scientific-field={field} data-issue-field={field} sx={{ boxSizing: 'border-box', width: fullWidth ? '100%' : 'max-content', minWidth: fullWidth ? 0 : 140, maxWidth: '100%', flex: '0 0 auto',
    border: 1, borderColor: error ? 'error.main' : 'divider', borderRadius: 1, px: 1.25, py: .5 }}>
    <Button size="small" onClick={onSettings} aria-label={`设置字段：${name}`} sx={{ p: 0, minWidth: 0, fontSize: 12, lineHeight: 1.5, textAlign: 'left', textTransform: 'none' }}>{name}</Button>
    <TextField variant="standard" value={value} placeholder="未填写" type={numeric ? 'number' : 'text'}
      error={Boolean(error)} helperText={error} onChange={event => onChange?.(event.target.value)}
      slotProps={{ input: { disableUnderline: true, readOnly: readOnly || !onChange }, htmlInput: { 'aria-label': name, step: 'any' } }}
      sx={{ display: 'block', width: `${Math.max(14, Math.min(32, value.length + 2))}ch`, maxWidth: '100%', '& input': { py: 0, fontSize: 14 } }} />
  </Box>
}
