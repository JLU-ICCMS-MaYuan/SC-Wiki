import { Box, Button, TextField } from '@mui/material'
import { useEffect } from 'react'
export interface FieldSettingsPresentation { container: HTMLElement; onDone: () => void }

/** 主表单仅显示字段名称与值，元数据由右侧设置负责。 */
export default function ScientificFieldBox({ name, value, readOnly, numeric, field, fieldKey, error, fullWidth = false, onSettings, onChange }: {
  name: string; value: string; readOnly: boolean; numeric?: boolean; field: string; error?: string
  fieldKey?: string; fullWidth?: boolean; onSettings: (presentation?: FieldSettingsPresentation) => void; onChange?: (value: string) => void
}) {
  useEffect(() => {
    const normalize = (path: string) => path.replace(/\[(\d+)\]/g, '.$1').replace('.omega_log_k', '.omega_log')
    const configure = (event: Event) => {
      const request = (event as CustomEvent<{field: string; presentation: FieldSettingsPresentation; handled: boolean}>).detail
      if (request.handled) return
      const requested = normalize(request.field), own = normalize(field)
      if (requested !== own && requested !== own + '.value_number' && own !== requested + '.value_raw') return
      request.handled = true; onSettings(request.presentation)
    }
    document.addEventListener('scwiki:configure-field', configure)
    return () => document.removeEventListener('scwiki:configure-field', configure)
  }, [field, onSettings])
  return <Box data-scientific-field={field} data-scientific-field-key={fieldKey} data-issue-field={field} sx={{ position: 'relative', boxSizing: 'border-box', width: fullWidth ? '100%' : 'max-content', minWidth: fullWidth ? 0 : 140, maxWidth: '100%', flex: '0 0 auto',
    border: 1, borderColor: error ? 'error.main' : 'divider', borderRadius: 1, px: 1.25, py: .5 }}>
    <Button data-scientific-settings size="small" onClick={event => {
      const request = { field, name, value, handled: false }
      event.currentTarget.dispatchEvent(new CustomEvent('scwiki:open-field-settings', { bubbles: true, detail: request }))
      if (!request.handled) onSettings()
    }} aria-label={`设置字段：${name}`} sx={{ p: 0, minWidth: 0, maxWidth: 'calc(100% - 20px)', fontSize: 12, lineHeight: 1.5, textAlign: 'left', textTransform: 'none' }}>{name}</Button>
    <TextField variant="standard" value={value} placeholder="未填写" type={numeric ? 'number' : 'text'}
      error={Boolean(error)} helperText={error} onChange={event => onChange?.(event.target.value)}
      slotProps={{ input: { disableUnderline: true, readOnly: readOnly || !onChange }, htmlInput: { 'aria-label': name, step: 'any' } }}
      sx={{ display: 'block', width: `${Math.max(14, Math.min(32, value.length + 2))}ch`, maxWidth: '100%', '& input': { py: 0, fontSize: 14 } }} />
  </Box>
}
