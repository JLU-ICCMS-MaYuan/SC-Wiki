import React, { useState } from 'react'
import { Box, ButtonBase, Menu, MenuItem } from '@mui/material'
import TranslateIcon from '@mui/icons-material/Translate'
import { useLanguage } from '../context/LanguageContext'
import type { Lang } from '../i18n'
import SidebarButton from './SidebarButton'

const OPTIONS: Array<{ value: Lang; label: string; labelKey: string }> = [
  { value: 'zh', label: '中文', labelKey: 'nav.switchToZh' },
  { value: 'en', label: 'English', labelKey: 'nav.switchToEn' },
]

const LanguageSwitcher: React.FC<{ collapsed: boolean }> = ({ collapsed }) => {
  const { lang, setLang, t } = useLanguage()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)

  return <>
    {collapsed ? (
      <SidebarButton
        icon={<TranslateIcon />} label={t('nav.languageGroup')} detail={lang === 'zh' ? '中文' : 'English'} collapsed
        aria-haspopup="menu" aria-expanded={Boolean(anchorEl)}
        onClick={event => setAnchorEl(event.currentTarget)}
      />
    ) : (
      <Box role="group" aria-label={t('nav.languageGroup')} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minHeight: 48, px: 1.5 }}>
        <TranslateIcon sx={{ fontSize: 21, color: 'text.secondary', flexShrink: 0 }} />
        <Box sx={{ display: 'flex', flex: 1, minWidth: 0, p: 0.375, bgcolor: 'action.hover', borderRadius: 1.5 }}>
          {OPTIONS.map(option => <ButtonBase
            key={option.value} aria-label={t(option.labelKey)} aria-pressed={lang === option.value}
            onClick={() => setLang(option.value)}
            sx={{
              flex: 1, minHeight: 32, borderRadius: 1, px: 0.5, fontSize: 11, fontWeight: 700,
              bgcolor: lang === option.value ? 'background.paper' : 'transparent',
              color: lang === option.value ? 'primary.main' : 'text.secondary',
              boxShadow: lang === option.value ? 1 : 0,
              '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main' },
            }}
          >{option.label}</ButtonBase>)}
        </Box>
      </Box>
    )}
    <Menu
      anchorEl={anchorEl} open={collapsed && Boolean(anchorEl)} onClose={() => setAnchorEl(null)}
      anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }} transformOrigin={{ horizontal: 'left', vertical: 'bottom' }}
    >
      {OPTIONS.map(option => <MenuItem
        key={option.value} selected={lang === option.value} aria-label={t(option.labelKey)}
        onClick={() => { setLang(option.value); setAnchorEl(null) }}
      >{option.label}</MenuItem>)}
    </Menu>
  </>
}

export default LanguageSwitcher
