import { useEffect, useState, type ReactNode } from 'react'
import { Box, Typography } from '@mui/material'

/** 分区保持挂载；收起不会丢失人工输入、原PDF区域或未应用设置。 */
export default function ReviewSection({ title, initialOpen = false, expand = false, children }: { title: string; initialOpen?: boolean; expand?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(initialOpen)
  useEffect(() => { if (expand) setOpen(true) }, [expand])
  return <Box component="details" open={open} onToggle={event => setOpen(event.currentTarget.open)} sx={{ my: 1.5, border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
    <Typography component="summary" fontWeight={600} sx={{ cursor: 'pointer', p: 1.5, bgcolor: 'action.hover' }}>{title}</Typography>
    <Box sx={{ p: 1.5 }}>{children}</Box>
  </Box>
}
