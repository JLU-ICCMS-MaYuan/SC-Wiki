import React from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import theme from '../../theme'
import { LanguageProvider } from '../../context/LanguageContext'
import AuthDemo from './AuthDemo'
import '../../features/auth/auth-demo.css'

// 独立入口不挂载 App 或 AuthProvider，演示数据不能进入正式认证链路。
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <LanguageProvider><AuthDemo /></LanguageProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
