import type { PropsWithChildren, ReactNode } from 'react'
import { Box, Typography } from '@mui/material'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'

/** 原生折叠保留表单挂载及临时输入；模块工具栏不参与标题的切换。 */
export default function PropertyModuleSection({ title, status, actions, children }: PropsWithChildren<{
  title: string
  status?: string
  actions?: ReactNode
}>) {
  return <Box sx={{ position: 'relative', minWidth: 0, pointerEvents: 'auto',
    '& > details:not([open]) > [data-property-module-body]': { display: 'none' },
    '& > details[open] > summary .property-module-chevron': { transform: 'rotate(90deg)' },
  }}>
    <Box component="details" data-property-module-section>
      <Box component="summary" data-property-module-toggle sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minHeight: 40, pr: actions ? 16 : 0, cursor: 'pointer', listStyle: 'none', borderRadius: 1,
        '&::-webkit-details-marker': { display: 'none' }, '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' },
      }}>
        <ChevronRightIcon className="property-module-chevron" fontSize="small" sx={{ flexShrink: 0 }} />
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle2" fontWeight={700}>{title}</Typography>
          {status && <Typography variant="caption" color="error">{status}</Typography>}
        </Box>
      </Box>
      <Box data-property-module-body sx={{ minWidth: 0 }}>{children}</Box>
    </Box>
    {actions && <Box sx={{ position: 'absolute', top: 4, right: 0 }}>{actions}</Box>}
  </Box>
}
