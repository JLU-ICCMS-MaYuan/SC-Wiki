import { useEffect, useRef, useState } from 'react'
import { Box, Typography } from '@mui/material'
import EvidenceReadableValue from './EvidenceReadableValue'
import { useLanguage } from '../context/LanguageContext'

/** 将现有字段设置表单挂进审核页签，避免第二份值编辑器或两个重叠侧栏。 */
export default function ReviewFieldSettings({ identity, field, enabled, onDone, onPendingChange, label, value, settingsField, sourceField }: {
  identity: string; field: string; enabled: boolean; onDone: () => void
  onPendingChange?: (pending: boolean) => void; label?: string; value?: unknown
  settingsField?: string; sourceField?: string
}) {
  const { t } = useLanguage(), container = useRef<HTMLDivElement>(null), started = useRef(false)
  const [available, setAvailable] = useState(true)
  const callbacks = useRef({ onDone, onPendingChange }); callbacks.current = { onDone, onPendingChange }
  useEffect(() => {
    if (!enabled || started.current || !container.current) return
    started.current = true
    let targetField = settingsField || field
    const root = /^material_states\[\d+\]\.property_modules\[\d+\]\.records\[\d+\]/
    if (sourceField && field.match(root)) targetField = targetField.replace(root, field.match(root)![0])
    const extension = field.match(/\.extensions\.\d+/)?.[0]
    if (extension) targetField = targetField.replace(/\.extensions\.\d+/, extension)
    const request = { field: targetField, handled: false, presentation: { container: container.current, onPendingChange: (pending: boolean) => callbacks.current.onPendingChange?.(pending), onDone: () => {
      started.current = false; callbacks.current.onDone()
    } } }
    document.dispatchEvent(new CustomEvent('scwiki:configure-field', { detail: request }))
    setAvailable(request.handled)
  }, [enabled, field, identity, settingsField, sourceField])
  return <Box data-evidence-ignore>
    <Box ref={container} />
    {!available && <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Typography color="text.secondary">{t('evidence.settingsName')}</Typography><Typography>{label || field}</Typography>
      <Typography color="text.secondary">{t('evidence.settingsValue')}</Typography><EvidenceReadableValue value={value} />
      <Typography color="text.secondary">{t('evidence.settingsInForm')}</Typography>
    </Box>}
  </Box>
}
