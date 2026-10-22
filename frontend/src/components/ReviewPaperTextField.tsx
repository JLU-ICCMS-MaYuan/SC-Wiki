import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Alert, Box, Button, Stack, TextField, type TextFieldProps } from '@mui/material'
import type { FieldSettingsPresentation } from './ScientificFieldBox'
import { useLanguage } from '../context/LanguageContext'

type Props = Omit<TextFieldProps, 'value' | 'onChange'> & {
  'data-issue-field': string
  value: string
  readOnly?: boolean
  onValueChange: (value: string) => void
}
interface Session { original: string; raw: string; presentation: FieldSettingsPresentation }

/** 主表单与设置页使用同一更新回调；侧栏只暂存尚未应用的编辑文本。 */
export default function ReviewPaperTextField({ value, readOnly = false, onValueChange, ...props }: Props) {
  const { t } = useLanguage()
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState('')
  const current = useRef({ value, readOnly: readOnly || Boolean(props.disabled), onValueChange })
  current.current = { value, readOnly: readOnly || Boolean(props.disabled), onValueChange }
  const field = props['data-issue-field']
  useEffect(() => {
    const configure = (event: Event) => {
      const request = (event as CustomEvent<{ field: string; handled: boolean; presentation: FieldSettingsPresentation }>).detail
      if (request.handled || request.field !== field) return
      request.handled = true
      setError('')
      setSession({ original: current.current.value, raw: current.current.value, presentation: request.presentation })
    }
    document.addEventListener('scwiki:configure-field', configure)
    return () => document.removeEventListener('scwiki:configure-field', configure)
  }, [field])
  useEffect(() => () => session?.presentation.onPendingChange?.(false), [session?.presentation])
  const close = () => {
    session?.presentation.onPendingChange?.(false)
    session?.presentation.onDone()
    setSession(null)
  }
  const apply = () => {
    if (!session || current.current.readOnly) return
    if (current.current.value !== session.original) { setError(t('evidence.settingsConflict')); return }
    if (session.raw !== session.original) current.current.onValueChange(session.raw)
    close()
  }
  return <>
    <TextField {...props} value={value} onChange={event => onValueChange(event.target.value)}
      slotProps={{ ...props.slotProps, input: { readOnly, ...props.slotProps?.input } }} />
    {session && createPortal(<Stack component="form" spacing={2} onSubmit={event => { event.preventDefault(); apply() }}>
      <TextField label={t('evidence.settingsName')} value={props.label} slotProps={{ input: { readOnly: true } }} />
      <TextField autoFocus label={t('evidence.settingsValue')} value={session.raw} multiline minRows={4}
        disabled={current.current.readOnly} helperText={props.helperText}
        onChange={event => {
          const raw = event.target.value
          session.presentation.onPendingChange?.(raw !== session.original)
          setSession({ ...session, raw }); setError('')
        }} />
      {error && <Alert severity="error">{error}</Alert>}
      <Box sx={{ display: 'flex', justifyContent: 'end', gap: 1 }}>
        <Button onClick={close}>{t(current.current.readOnly ? 'common.close' : 'common.cancel')}</Button>
        {!current.current.readOnly && <Button type="submit" variant="contained" disabled={session.raw === session.original}>{t('evidence.settingsApply')}</Button>}
      </Box>
    </Stack>, session.presentation.container)}
  </>
}
