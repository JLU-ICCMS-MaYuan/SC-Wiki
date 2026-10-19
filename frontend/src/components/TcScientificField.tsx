import { useEffect, useRef, useState } from 'react'
import { Box } from '@mui/material'
import ScientificFieldBox, { type FieldSettingsPresentation } from './ScientificFieldBox'
import ScientificFieldSettingsDrawer, { type ScientificFieldSettings } from './ScientificFieldSettingsDrawer'
import type { ParameterValue } from '../lib/tcParameters'

export interface TcFieldSettings { name_raw: string; unit_raw: string }
const numeric = /^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/
export default function TcScientificField({ value, label, unit = '', field, readOnly, error, settings, currentTc = false, onChange, onApply }: {
  value: ParameterValue; label: string; unit?: string; field: string; readOnly: boolean; error?: string
  settings?: TcFieldSettings; currentTc?: boolean; onChange: (value: ParameterValue) => void; onApply: (value: ParameterValue, settings: TcFieldSettings) => void
}) {
  const [editing, setEditing] = useState<(ScientificFieldSettings & { signature: string }) | null>(null), [message, setMessage] = useState('')
  const [text, setText] = useState(String(value ?? '')), published = useRef(value)
  useEffect(() => {
    if (!Object.is(value, published.current)) setText(String(value ?? ''))
    published.current = value
  }, [value])
  const [presentation, setPresentation] = useState<FieldSettingsPresentation>()
  const signature = JSON.stringify([field, value, settings])
  const convert = (raw: string): ParameterValue => raw === '' ? null : numeric.test(raw) && Number.isFinite(Number(raw)) ? Number(raw) : raw
  const raw = text, name = settings?.name_raw || label
  return <Box data-issue-field={field} data-tc-current-value={currentTc || undefined}>
    <ScientificFieldBox name={name} value={raw} field={field} readOnly={readOnly} fullWidth
      error={raw && typeof convert(raw) === 'string' ? '请输入完整的非负数值' : error} onChange={next => {
        setText(next); const value = convert(next)
        published.current = currentTc && typeof value === 'string' ? null : value; onChange(value)
      }}
      onSettings={host => { setPresentation(host); setMessage(''); setEditing({ name, kind: 'number', raw, unit: settings?.unit_raw ?? unit, signature }) }} />
    <ScientificFieldSettingsDrawer presentation={presentation} value={editing} readOnly={readOnly} typeLocked error={message}
      note={unit === 'K' ? '规范值以 K 保存；此处单位设置保留原始标注，不自动换算规范值。' : '名称和单位设置保留为字段标注，不改变固定字段的科学含义。'}
      onChange={next => setEditing(current => current && { ...current, ...next })} onClose={() => setEditing(null)} onApply={() => {
        if (!editing || readOnly) return
        if (editing.signature !== signature) { setMessage('字段已发生变化，请关闭后重新打开'); return }
        if (!editing.name.trim()) { setMessage('请填写字段名称'); return }
        const number = convert(editing.raw)
        if (typeof number === 'string') { setMessage('请输入完整的非负数值'); return }
        setText(editing.raw); published.current = number
        onApply(number, { name_raw: editing.name.trim(), unit_raw: editing.unit.trim() }); setEditing(null)
      }} />
  </Box>
}
