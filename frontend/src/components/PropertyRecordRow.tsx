import type { ReactNode } from 'react'
import { Box } from '@mui/material'

/** 字段自行横向滚动，记录操作始终留在本行右端。 */
export default function PropertyRecordRow({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return <Box data-record-primary-row sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0,
    '& > :first-of-type': { flex: '1 1 auto', minWidth: 0 } }}>
    {children}
    {actions && <Box data-record-actions sx={{ flexShrink: 0 }}>{actions}</Box>}
  </Box>
}
