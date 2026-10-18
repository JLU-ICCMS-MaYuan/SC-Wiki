import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Box, Button, CssBaseline, ThemeProvider, Typography } from '@mui/material'
import theme from './src/theme'
import PropertyModuleEditor from './src/components/PropertyModuleEditor'
import { api } from './src/lib/api'
import { validateRecordClient } from './src/lib/formDefinitions'
import fixture from './fixture.json'

api.get = (async (path: string) => path.startsWith('/api/form-definitions?') ? fixture.definitions
  : fixture.definitions.find(d => path.includes(encodeURIComponent(d.definition_key)))) as typeof api.get
const storageKey = 'field-sidebar-production-verification-v1'
function App() {
  const [mode, setMode] = useState('上传')
  const [width, setWidth] = useState('auto')
  const [modules, setModules] = useState(() => JSON.parse(sessionStorage.getItem(storageKey) || 'null')?.modules || fixture.modules)
  const [deleted, setDeleted] = useState<string[]>(() => JSON.parse(sessionStorage.getItem(storageKey) || 'null')?.deleted_record_keys || [])
  const [message, setMessage] = useState('正式共享组件，隔离夹具；初始数据来自原任务，新增结果只作交互验证，不回写业务草稿。')
  return <ThemeProvider theme={theme}><CssBaseline /><Box sx={{ p: 2 }}>
    <Typography variant="h6">紧凑字段与右侧设置 · 正式共享组件验证</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>{message}</Typography>
    <label>验证入口 <select aria-label="验证入口" value={mode} onChange={e => setMode(e.target.value)}>
      {['上传', '管理员', '只读'].map(m => <option key={m}>{m}</option>)}
    </select></label>
    <label>容器宽度 <select aria-label="容器宽度" value={width} onChange={e => setWidth(e.target.value)}>
      <option value="auto">自适应</option><option value="390">390px</option>
    </select></label>
    <Button onClick={() => {
      const issues = modules.flatMap(m => m.records.flatMap(r => validateRecordClient(r)))
      if (issues.length) { setMessage(issues.map(i => i.message).join('；')); return }
      sessionStorage.setItem(storageKey, JSON.stringify({ modules, deleted_record_keys: deleted }))
      setModules(JSON.parse(JSON.stringify(modules)))
      setMessage('已保存隔离验证载荷，刷新可重开；没有写入业务论文。')
    }} disabled={mode === '只读'}>保存隔离载荷</Button>
    <Typography sx={{ my: 2 }}>P6/mmm · LaSc₂H₂₄ · 150 GPa</Typography>
    <Box sx={{ width: width === 'auto' ? '100%' : 390, maxWidth: '100%' }}>
    <PropertyModuleEditor modules={modules} readOnly={mode === '只读'} basePath="material_states.0.property_modules"
      onChange={(next, deletion) => {
        setModules(next)
        setDeleted(current => [...new Set([...current, ...(deletion?.deletedRecordKey ? [deletion.deletedRecordKey] : []), ...(deletion?.deletedRecordKeys || [])])])
      }} /></Box>
    <details><summary>隔离验证载荷</summary><pre id="payload">{JSON.stringify({ modules, deleted_record_keys: deleted }, null, 2)}</pre></details>
  </Box></ThemeProvider>
}
createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>)
