import { useEffect, useRef, useState } from 'react'
import { Box, Button, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'

/** 将现有字段设置表单挂进审核页签，避免第二份值编辑器或两个重叠侧栏。 */
export default function ReviewFieldSettings({ identity, field, enabled, onDone, onEdit }: {
  identity: string; field: string; enabled: boolean; onDone: () => void; onEdit: () => void
}) {
  const { t } = useLanguage(), container = useRef<HTMLDivElement>(null), started = useRef(false)
  const [available, setAvailable] = useState(true)
  const callbacks = useRef({ onDone, onEdit }); callbacks.current = { onDone, onEdit }
  useEffect(() => {
    if (!enabled || started.current || !container.current) return
    started.current = true
    const request = { field, handled: false, presentation: { container: container.current, onDone: () => {
      started.current = false; callbacks.current.onDone()
    } } }
    document.dispatchEvent(new CustomEvent('scwiki:configure-field', { detail: request }))
    setAvailable(request.handled)
  }, [enabled, field, identity])
  return <Box data-evidence-ignore>
    <Box ref={container} />
    {!available && <><Typography color="text.secondary">{t('evidence.settingsInForm')}</Typography><Button onClick={() => callbacks.current.onEdit()}>{t('evidence.editCurrent')}</Button></>}
  </Box>
}
