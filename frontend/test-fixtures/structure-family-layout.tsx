// 独立浏览器夹具：真实编辑器、来源标记和主题；内存数据，不连接业务 API。
import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Alert, Box, Button, CssBaseline, ThemeProvider } from '@mui/material'
import MaterialStatesEditor from '../src/components/MaterialStatesEditor'
import EvidenceFieldMarkers from '../src/components/EvidenceFieldMarkers'
import type { EvidenceRecord } from '../src/components/EvidenceWorkflow'
import { LanguageProvider, useLanguage } from '../src/context/LanguageContext'
import type { DraftMaterialState } from '../src/lib/paperProcessing'
import { DEFAULT_MATERIAL_DIMENSIONALITIES, type ClassificationCatalogs } from '../src/lib/classifications'
import theme from '../src/theme'

const catalogs: ClassificationCatalogs = {
  material_families: [], material_dimensionalities: DEFAULT_MATERIAL_DIMENSIONALITIES,
  structure_families: [{ id: 1, name: '笼状结构', name_en: 'Clathrate', aliases: [] }],
}
const samples = ['empty', 'single', 'multiple', 'long'] as const
const cases = [1440, 390].flatMap(width => ['zh', 'en'].flatMap(lang => samples.map(sample => ({ width, lang, sample }))))
type Case = typeof cases[number]
type Report = { case: Case; passed: boolean; summary: string; details: unknown }
const params = new URLSearchParams(location.search)
const current: Case = { width: Number(params.get('width')), lang: params.get('lang') || 'zh', sample: (params.get('sample') || 'single') as Case['sample'] }
const noop = () => {}

// 夹具没有真实记录；阻止任何误触的上传或目录请求到达业务服务。
window.fetch = async () => { throw new Error('布局夹具禁止调用业务 API') }

function Preview() {
  const { setLang } = useLanguage()
  const names = current.sample === 'empty' ? [] : current.sample === 'single' ? ['笼状结构']
    : current.sample === 'multiple' ? ['笼状结构', '层状结构', '链状结构', '二维网络', '三维网络', '用户输入的结构分类']
      : ['VeryLongStructureFamilyNameWithoutSpacesForNarrowScreenWrapping']
  const [states, setStates] = useState<DraftMaterialState[]>([{
    state_key: 'fixture-state', material: 'H3S', material_name: 'H3S', state_kind: 'theoretical',
    element_count: 2, material_dimensionality: 'three_dimensional', crystal_system: 'cubic',
    pressure_value_gpa: 150, property_modules: [],
    structure_families: names.map(name => ({ id: null, name, status: 'pending', is_primary: false })),
  }])
  const [refresh, setRefresh] = useState(0)
  const [opened, setOpened] = useState('')
  const records = useMemo<EvidenceRecord[]>(() => ['element_count', 'material_dimensionality', 'structure_families'].map(field => ({
    key: field, field: `material_states[0].${field}`, state_key: 'fixture-state', label: field,
    status: refresh % 2 ? 'uncertain' : 'supported', required: true, reason: '', evidences: [],
  })), [refresh])
  useEffect(() => { setLang(current.lang === 'en' ? 'en' : 'zh') }, [setLang])
  useEffect(() => {
    // 三轮状态切换覆盖旧实现的重复标签；等待布局与标记完成后再测量。
    const timer = setTimeout(() => {
      if (refresh < 3) { setRefresh(refresh + 1); return }
      const fields = ['element_count', 'material_dimensionality', 'structure_families'].map(field => {
        const anchor = document.querySelector<HTMLElement>(`[data-issue-field="material_states[0].${field}"]`)!
        const box = anchor.querySelector<HTMLElement>('.MuiInputBase-root')!
        const label = anchor.querySelector<HTMLElement>('label')!
        const rect = box.getBoundingClientRect(), labelRect = label.getBoundingClientRect(), style = getComputedStyle(box)
        return { field, top: rect.top, bottom: rect.bottom, height: rect.height, labelBottom: labelRect.bottom,
          fontSize: style.fontSize, fontWeight: style.fontWeight, labelFontSize: getComputedStyle(label).fontSize,
          labelFontWeight: getComputedStyle(label).fontWeight, triggers: anchor.querySelectorAll('[data-evidence-key]').length }
      })
      const spread = (key: 'top' | 'bottom' | 'labelBottom') => Math.max(...fields.map(f => f[key])) - Math.min(...fields.map(f => f[key]))
      const sameRow = current.width >= 900
      const oneLine = ['empty', 'single'].includes(current.sample)
      const chips = [...document.querySelectorAll<HTMLElement>('.MuiAutocomplete-tag')].map(chip => {
        const label = chip.querySelector<HTMLElement>('.MuiChip-label')!
        return { fontSize: getComputedStyle(chip).fontSize, fontWeight: getComputedStyle(chip).fontWeight,
          clipped: label.scrollWidth > label.clientWidth + 1 || label.scrollHeight > label.clientHeight + 1 }
      })
      const passed = fields.every(f => f.triggers === 1 && f.fontSize === fields[0].fontSize && f.fontWeight === fields[0].fontWeight
        && f.labelFontSize === fields[0].labelFontSize && f.labelFontWeight === fields[0].labelFontWeight)
        && innerWidth === current.width
        && (!sameRow || spread('top') <= 1 && spread('labelBottom') <= 1 && (!oneLine || spread('bottom') <= 1))
        && chips.every(c => !c.clipped && c.fontSize === fields[0].fontSize && c.fontWeight === fields[0].fontWeight)
        && document.documentElement.scrollWidth <= innerWidth + 1
        && !document.querySelector('button[data-evidence-key="structure_families"]')
      const summary = `视口 ${innerWidth}px；框高 ${fields.map(f => f.height).join('/')}px；顶部差 ${sameRow ? spread('top') : '纵向排列'}；标签差 ${sameRow ? spread('labelBottom') : '纵向排列'}；字体 ${fields[0].fontSize}/${fields[0].fontWeight}；入口 ${fields.map(f => f.triggers).join('/')}；溢出 ${document.documentElement.scrollWidth - innerWidth}px`
      parent.postMessage({ type: 'family-layout', report: { case: current, passed, summary, details: { fields, chips, overflow: document.documentElement.scrollWidth - innerWidth } } }, location.origin)
    }, 180)
    return () => clearTimeout(timer)
  }, [refresh])
  return <Box sx={{ p: 2 }} data-evidence-scope="layout-fixture">
    <MaterialStatesEditor states={states} onChange={setStates} catalogs={catalogs} />
    <EvidenceFieldMarkers records={records} scope="layout-fixture" onOpen={key => setOpened(key)} onChange={noop} />
    <Alert severity="info">来源入口：{opened || '尚未打开'}；核对结果更新 {refresh} 次；仅内存数据。</Alert>
    <Button onClick={() => setRefresh(r => r + 1)}>更新核对结果</Button>
    <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(states[0].structure_families)}</pre>
  </Box>
}

function Runner() {
  const [index, setIndex] = useState(0)
  const [running, setRunning] = useState(true)
  const [reports, setReports] = useState<Report[]>([])
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.source !== document.querySelector('iframe')?.contentWindow || event.data?.type !== 'family-layout') return
      const report: Report = event.data.report
      setReports(old => [...old.filter(r => JSON.stringify(r.case) !== JSON.stringify(report.case)), report])
      if (running && index < cases.length - 1) setIndex(index + 1)
      else setRunning(false)
    }
    window.addEventListener('message', receive)
    return () => window.removeEventListener('message', receive)
  }, [index, running])
  const test = cases[index]
  const url = new URL(location.href)
  url.search = new URLSearchParams({ frame: '1', width: String(test.width), lang: test.lang, sample: test.sample }).toString()
  return <Box sx={{ p: 1 }}>
    <h1>结构家族布局验收</h1>
    <p role="status">{running ? '正在验证' : '验证完成'}：{reports.filter(r => r.passed).length}/{cases.length} 通过，{reports.filter(r => !r.passed).length} 失败</p>
    {cases.map((c, i) => <Button key={i} size="small" onClick={() => { setRunning(false); setIndex(i) }}>{c.width} {c.lang} {c.sample}</Button>)}
    <p>当前：{test.width}px / {test.lang} / {test.sample}</p>
    {reports.filter(r => JSON.stringify(r.case) === JSON.stringify(test)).map(r => <p key={r.summary}>{r.passed ? '通过' : '失败'}：{r.summary}</p>)}
    <iframe title="真实共享材料状态编辑器" src={url.href} style={{ boxSizing: 'content-box', width: test.width, maxWidth: '100%', height: 920, border: '1px solid #ddd' }} />
    <details><summary>尺寸与样式测量结果</summary><pre>{JSON.stringify(reports, null, 2)}</pre></details>
  </Box>
}

createRoot(document.getElementById('root')!).render(<ThemeProvider theme={theme}><CssBaseline /><LanguageProvider>
  {params.has('frame') ? <Preview /> : <Runner />}
</LanguageProvider></ThemeProvider>)
