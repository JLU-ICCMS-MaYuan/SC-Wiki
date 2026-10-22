import { useEffect, useRef, useState } from 'react'
import { Box, Button, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'

/** 将现有字段设置表单挂进审核页签，避免第二份值编辑器或两个重叠侧栏。 */
export default function ReviewFieldSettings({ identity, field, enabled, onDone, onEdit, settingsField, sourceField, part, related = [], onSelect }: {
  identity: string; field: string; enabled: boolean; onDone: () => void; onEdit: () => void
  settingsField?: string; sourceField?: string; part?: 'name' | 'kind' | 'raw' | 'unit'
  related?: Array<{key: string; label: string}>; onSelect?: (key: string) => void
}) {
  const { t } = useLanguage(), container = useRef<HTMLDivElement>(null), started = useRef(false)
  const [available, setAvailable] = useState(true)
  const callbacks = useRef({ onDone, onEdit }); callbacks.current = { onDone, onEdit }
  useEffect(() => {
    if (!enabled || started.current || !container.current) return
    started.current = true
    let targetField = settingsField || field
    const root = /^material_states\[\d+\]\.property_modules\[\d+\]\.records\[\d+\]/
    if (sourceField && field.match(root)) targetField = targetField.replace(root, field.match(root)![0])
    const extension = field.match(/\.extensions\.\d+/)?.[0]
    if (extension) targetField = targetField.replace(/\.extensions\.\d+/, extension)
    const request = { field: targetField, handled: false, presentation: { container: container.current, onDone: () => {
      started.current = false; callbacks.current.onDone()
    } } }
    document.dispatchEvent(new CustomEvent('scwiki:configure-field', { detail: request }))
    setAvailable(request.handled)
  }, [enabled, field, identity, settingsField, sourceField])
  return <Box data-evidence-ignore>
    <Box ref={container} />
    {!available && <><Typography color="text.secondary">{t('evidence.settingsInForm')}</Typography><Button onClick={() => callbacks.current.onEdit()}>{t('evidence.editCurrent')}</Button></>}
  </Box>
}
