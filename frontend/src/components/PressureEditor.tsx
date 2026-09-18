import { useEffect, useRef, useState } from 'react'
import { Alert, Box, TextField, Typography } from '@mui/material'
import type { DraftMaterialState } from '../lib/paperProcessing'
import { useLanguage } from '../context/LanguageContext'

const numberPattern = '[+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?'

/** 临时输入与科学数值分开，输入小数点或指数时不误删条件。 */
function PressureNumber({ value, label, field, onChange }: {
  value?: number | null; label: string; field: string; onChange: (value: number | null) => void
}) {
  const { t } = useLanguage()
  const [text, setText] = useState(String(value ?? ''))
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { setText(old => old !== '' && Number(old) === value ? old : String(value ?? '')) }, [value])
  const valid = text === '' || (new RegExp(`^${numberPattern}$`).test(text) && Number.isFinite(Number(text)))
  useEffect(() => { input.current?.setCustomValidity(valid ? '' : t('evidence.invalidPressure')) }, [valid, t])
  return <TextField fullWidth label={label} data-issue-field={field} value={text} inputRef={input}
    error={!valid} helperText={!valid ? t('evidence.invalidPressure') : undefined}
    slotProps={{ htmlInput: { inputMode: 'decimal', 'data-pressure-input': 'true' } }}
    onChange={event => {
      const next = event.target.value
      setText(next)
      if (next === '') onChange(null)
      else if (new RegExp(`^${numberPattern}$`).test(next) && Number.isFinite(Number(next))) onChange(Number(next))
    }} />
}

export default function PressureEditor({ state, index, onChange }: {
  state: DraftMaterialState; index: number; onChange: (patch: Partial<DraftMaterialState>) => void
}) {
  const { t } = useLanguage()
  const path = `material_states[${index}]`
  const factors: Record<string, number> = { pa: 1e-9, kpa: 1e-6, mpa: 0.001, gpa: 1, bar: 0.0001, kbar: 0.1, atm: 0.000101325 }
  const raw = String(state.pressure_raw ?? '').trim()
  const factor = factors[(state.pressure_unit_raw ?? '').trim().toLowerCase()]
  const converted = raw !== '' && new RegExp(`^${numberPattern}$`).test(raw) && factor ? Number(raw) * factor : undefined
  const value = state.pressure_value_gpa
  const mismatch = value != null && converted !== undefined && Math.abs(value - converted) > Math.max(1e-12, Math.abs(converted) * 1e-6)
  const outsideRange = value != null && ((state.pressure_min_gpa != null && value < state.pressure_min_gpa) || (state.pressure_max_gpa != null && value > state.pressure_max_gpa))
  return <Box sx={{ minWidth: 0 }}>
    <PressureNumber value={state.pressure_value_gpa} label={t('upload.pressureField')} field={`${path}.pressure_value_gpa`}
      onChange={value => onChange(value === null
        ? { pressure_value_gpa: null, pressure_raw: null, pressure_unit_raw: null, pressure_min_gpa: null, pressure_max_gpa: null }
        : { pressure_value_gpa: value })} />
    {(mismatch || outsideRange) && <Alert severity="warning" sx={{ mt: 1 }}>{t('evidence.pressureMismatch')}</Alert>}
    <Box component="details" sx={{ mt: 1 }}>
      <Box component="summary" sx={{ cursor: 'pointer', color: 'text.secondary' }}>{t('evidence.pressureConditions')}</Box>
      <Box sx={{ display: 'grid', gap: 1, mt: 1 }}>
        <TextField label={t('evidence.pressureRaw')} data-issue-field={`${path}.pressure_raw`} value={state.pressure_raw ?? ''}
          onChange={e => onChange({pressure_raw: e.target.value || null})} />
        <TextField label={t('evidence.pressureUnit')} data-issue-field={`${path}.pressure_unit_raw`} value={state.pressure_unit_raw ?? ''}
          onChange={e => onChange({pressure_unit_raw: e.target.value || null})} />
        <PressureNumber label={t('evidence.pressureMin')} field={`${path}.pressure_min_gpa`} value={state.pressure_min_gpa} onChange={value => onChange({pressure_min_gpa: value})} />
        <PressureNumber label={t('evidence.pressureMax')} field={`${path}.pressure_max_gpa`} value={state.pressure_max_gpa} onChange={value => onChange({pressure_max_gpa: value})} />
        <Typography variant="caption" color="text.secondary">{t('evidence.pressureHint')}</Typography>
      </Box>
    </Box>
  </Box>
}
