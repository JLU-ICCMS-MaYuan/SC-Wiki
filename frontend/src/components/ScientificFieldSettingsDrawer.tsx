import { Alert, Box, Button, Drawer, MenuItem, Stack, TextField, Typography } from '@mui/material'
import type { PropertyValueKind } from '../lib/propertyModules'

export interface ScientificFieldSettings { name: string; kind: PropertyValueKind; raw: string; unit: string }
const kinds: Record<PropertyValueKind, string> = { text: '文本', number: '数值', range: '范围', boolean: '布尔' }
export default function ScientificFieldSettingsDrawer({ value, readOnly, typeLocked, adding, error, note, onChange, onApply, onClose, onDelete }: {
  value: ScientificFieldSettings | null; readOnly: boolean; typeLocked?: boolean; adding?: boolean; error?: string
  note?: string; onChange: (value: ScientificFieldSettings) => void; onApply: () => void; onClose: () => void; onDelete?: () => void
}) {
  return <Drawer anchor="right" open={Boolean(value)} onClose={onClose} PaperProps={{ role: 'dialog', 'aria-label': '字段设置', sx: { width: { xs: '100%', sm: 380 }, maxWidth: '100vw' } }}>
    {value && <Stack component="form" onSubmit={event => { event.preventDefault(); onApply() }} spacing={2} sx={{ p: 3, minHeight: '100%', boxSizing: 'border-box' }}>
      <Typography variant="h6">{readOnly ? '查看字段' : adding ? '新增字段' : '编辑字段'}</Typography>
      <TextField autoFocus label="字段名称（key）" value={value.name} disabled={readOnly} onChange={event => onChange({ ...value, name: event.target.value })} />
      <TextField select label="值类型" value={value.kind} disabled={readOnly || typeLocked} onChange={event => onChange({ ...value, kind: event.target.value as PropertyValueKind, raw: '' })}>
        {Object.entries(kinds).map(([key, name]) => <MenuItem key={key} value={key}>{name}</MenuItem>)}
      </TextField>
      {value.kind === 'boolean' ? <TextField select label="值" value={value.raw} disabled={readOnly} onChange={event => onChange({ ...value, raw: event.target.value })}>
        <MenuItem value="">未填写</MenuItem><MenuItem value="true">是</MenuItem><MenuItem value="false">否</MenuItem>
      </TextField> : <TextField label={value.kind === 'range' ? '值（下界..上界）' : '值'} value={value.raw} disabled={readOnly} onChange={event => onChange({ ...value, raw: event.target.value })} />}
      <TextField label="单位" value={value.unit} disabled={readOnly} onChange={event => onChange({ ...value, unit: event.target.value })} />
      <Alert severity="info">{typeLocked ? '固定字段保留科学类型。' : ''}修改单位不自动换算数值；请同时核对当前值。</Alert>
      {note && <Typography variant="caption" color="text.secondary">{note}</Typography>}
      {error && <Alert severity="error">{error}</Alert>}
      {!readOnly && onDelete && <Button color="error" onClick={onDelete}>删除这个补充字段</Button>}
      <Box sx={{ flex: 1 }} /><Stack direction="row" justifyContent="end" spacing={1}>
        <Button onClick={onClose}>{readOnly ? '关闭' : '取消'}</Button>
        {!readOnly && <Button type="submit" variant="contained">{adding ? '添加到表单' : '应用修改'}</Button>}
      </Stack>
    </Stack>}
  </Drawer>
}
