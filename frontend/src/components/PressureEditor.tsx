import { draftNumber } from '../lib/fieldDrafts'
import { useEffect, useRef, useState } from 'react'
import { Alert, Box, TextField } from '@mui/material'
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
    error={false}
    slotProps={{ htmlInput: { inputMode: 'decimal', 'data-pressure-input': 'true' } }}
    onChange={event => {
      const next = event.target.value
      setText(next)
      onChange(draftNumber(next))
    }} />
}

export default function PressureEditor({ state, index, onChange }: {
  state: DraftMaterialState; index: number; onChange: (patch: Partial<DraftMaterialState>) => void
}) {
  const { t } = useLanguage()
  const path = `material_states[${index}]`
  return <Box sx={{ minWidth: 0 }}>
    <PressureNumber value={state.pressure_value_gpa} label={t('upload.pressureField')} field={`${path}.pressure_value_gpa`}
      onChange={value => onChange({ pressure_value_gpa: value })} />


  </Box>
}
