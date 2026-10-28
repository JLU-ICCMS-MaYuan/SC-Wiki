// 隔离浏览器夹具直接使用正式共用组件、主题、语言和HTTP客户端。
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from '@mui/material/styles'
import { Button, CssBaseline } from '@mui/material'
import theme from '../../frontend/src/theme'
import { LanguageProvider, useLanguage } from '../../frontend/src/context/LanguageContext'
import { useEvidenceWorkflow, type EvidenceTarget } from '../../frontend/src/components/EvidenceWorkflow'

function Harness() {
  const flow = useEvidenceWorkflow()
  const { setLang } = useLanguage()
  const [result, setResult] = useState('')
  const target = new URLSearchParams(location.search).get('target') as EvidenceTarget['target'] || 'upload'
  return <main style={{ padding: 24 }}>
    <Button onClick={() => { setResult(''); void flow.gate({ target, target_id: 'fixture' }).then(value => setResult(value ? 'completed' : 'stopped')) }}>开始核对</Button>
    <Button onClick={() => setLang('en')}>English</Button>
    <output>{result}</output>{flow.dialog}
  </main>
}
createRoot(document.getElementById('root')!).render(<ThemeProvider theme={theme}><CssBaseline /><LanguageProvider><Harness /></LanguageProvider></ThemeProvider>)
