import React from 'react'
import { Box, ButtonBase, Tooltip, Typography, type ButtonBaseProps } from '@mui/material'

interface Props extends ButtonBaseProps {
  icon: React.ReactNode
  label: string
  detail?: string
  collapsed?: boolean
  selected?: boolean
}

/** 只负责侧栏入口呈现；导航与配置状态由调用方持有。 */
const SidebarButton: React.FC<Props> = ({ icon, label, detail, collapsed = false, selected = false, ...props }) => (
  <Tooltip title={collapsed ? [label, detail].filter(Boolean).join(' · ') : ''} placement="right" arrow>
    <ButtonBase
      aria-label={label}
      aria-current={selected ? 'page' : undefined}
      {...props}
      sx={{
        width: '100%', minWidth: 0, minHeight: 44, borderRadius: 2,
        display: 'flex', justifyContent: collapsed ? 'center' : 'flex-start',
        gap: 1.5, px: collapsed ? 0 : 1.5, py: 1.25, textAlign: 'left',
        color: selected ? 'primary.main' : 'text.secondary',
        bgcolor: selected ? '#eef2ff' : 'transparent',
        '&:hover': { bgcolor: selected ? '#e0e7ff' : 'action.hover', color: 'primary.main' },
        '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 },
      }}
    >
      <Box component="span" sx={{ display: 'flex', flexShrink: 0, '& .MuiSvgIcon-root': { fontSize: 21 } }}>{icon}</Box>
      <Box component="span" sx={{ display: collapsed ? 'none' : 'block', minWidth: 0 }}>
        <Typography component="span" sx={{ display: 'block', fontSize: 13, fontWeight: selected ? 750 : 600 }} noWrap>{label}</Typography>
        {detail && <Typography component="span" title={detail} sx={{ display: 'block', fontSize: 11, mt: 0.25, color: 'text.secondary' }} noWrap>{detail}</Typography>}
      </Box>
    </ButtonBase>
  </Tooltip>
)

export default SidebarButton
