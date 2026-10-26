import React from 'react'
import { createRoot } from 'react-dom/client'
import theme from '../../../../../frontend/src/theme'
import App from './App'
import './styles.css'

// 直接使用主站主题，避免独立 Demo 再维护一套基础色调和字体。
const tokens = {
  '--sc-primary': theme.palette.primary.main,
  '--sc-primary-hover': theme.palette.primary.dark,
  '--sc-primary-border': theme.palette.primary.light,
  '--sc-secondary': theme.palette.secondary.main,
  '--sc-bg': theme.palette.background.default,
  '--sc-paper': theme.palette.background.paper,
  '--sc-text': theme.palette.text.primary,
  '--sc-muted': theme.palette.text.secondary,
  '--sc-divider': theme.palette.divider,
  '--sc-success': theme.palette.success.main,
  '--sc-warning': theme.palette.warning.main,
  '--sc-error': theme.palette.error.main,
  '--sc-disabled': theme.palette.action.disabled,
  '--sc-disabled-bg': theme.palette.action.disabledBackground,
  '--sc-surface-muted': theme.palette.grey[50],
  '--sc-font': theme.typography.fontFamily!,
  '--sc-title-size': String(theme.typography.h1.fontSize),
  '--sc-card-shadow': theme.shadows[1],
}
for (const [key, value] of Object.entries(tokens)) document.documentElement.style.setProperty(key, value)
document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.palette.background.default)
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
