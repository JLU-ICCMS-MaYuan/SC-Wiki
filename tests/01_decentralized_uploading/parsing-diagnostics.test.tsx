import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import ParsingDiagnosticsPanel from '../../frontend/src/components/ParsingDiagnosticsPanel'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import * as diagnostics from '../../frontend/src/lib/parsingDiagnostics'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() } }))
const regions = Array.from({length: 90}, (_, i) => ({ file_id: 'main', pdf_page: 1, kind: 'paragraph', selected: `b${i}`,
  selected_text: `Original source ${i}`, alternatives: [{block_id:`alt${i}`,engine:'marker',text:`Alternative ${i}`}],
  triage: {id:`r${i}`,version:'v1', category:i<30?'notation':'symbol',status:i<30?'system_checked':'system_pending',
    reason:i<30?'notation_equal':'original_check_needed',filename:'Main paper.pdf',impact:{status:'unmapped',references:[]}} })) as diagnostics.ParsingDifference[]
const bibliography: diagnostics.BibliographyDifference[] = [{field:'year',grobid_value:2021,extracted_value:2012,
  triage:{id:'year',category:'bibliography',status:'system_checked',reason:'publication_verified',checked_value:2012,
    evidence:{url:'https://api.crossref.org/works/10.1073/pnas.1118168109',year:2012,doi:'10.1073/pnas.1118168109',title:'CaH6 source test'}}}]
const draft = {paper:{title:'CaH6 source test',doi:'10.1073/pnas.1118168109',year:2012,authors:[],paper_type:'review',material_families:[]},
  material_states:[],parsing_conflicts:regions,bibliography_conflicts:bibliography}
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async url => url.endsWith('/draft') ? {data:structuredClone(draft)} as never
    : {items:[],records:[],jobs:[],modules:[],space_groups:[],material_families:[],structure_families:[],material_dimensionalities:[]} as never)
  vi.mocked(api.post).mockResolvedValue({version:'v1',records:[],needs_check:false} as never)
  vi.mocked(api.patch).mockResolvedValue({changed:true,version:'v2'} as never)
})
afterEach(() => {cleanup();vi.restoreAllMocks();vi.clearAllMocks()})

it('完整上传宿主按类别显示90来源，标题输入不重新分组或启动模型', async () => {
  const grouped = vi.spyOn(diagnostics, 'groupParsingDifferences')
  render(<LanguageProvider><UploadTaskEditor taskId={'a'.repeat(32)} onSubmitted={()=>{}} /></LanguageProvider>)
  await screen.findByDisplayValue('CaH6 source test')
  expect(screen.getByText('解析来源检查')).toBeVisible()
  expect(screen.queryByText('Original source 89')).not.toBeInTheDocument()
  const before = grouped.mock.calls.length
  fireEvent.change(screen.getByDisplayValue('CaH6 source test'), {target:{value:'Edited title'}})
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,30))})
  expect(grouped.mock.calls.length).toBe(before)
  expect(vi.mocked(api.post).mock.calls.some(([url])=>url.endsWith('/jobs')||url.endsWith('/region'))).toBe(false)
  fireEvent.click(screen.getAllByRole('button',{name:'查看本类代表例'})[0])
  expect(document.querySelectorAll('[data-diagnostic-region]')).toHaveLength(1)
})

it('相同新来源容器复用快照；真正来源变化更新，年份变化不继承旧已核实结论', () => {
  const first = diagnostics.retainParsingSnapshot(diagnostics.EMPTY_PARSING_SNAPSHOT, draft)
  expect(diagnostics.retainParsingSnapshot(first, structuredClone(draft))).toBe(first)
  const changed=structuredClone(draft);changed.parsing_conflicts[0].selected_text='New actual source'
  expect(diagnostics.retainParsingSnapshot(first,changed)).not.toBe(first)
  const view=render(<LanguageProvider><ParsingDiagnosticsPanel snapshot={first} paper={draft.paper} /></LanguageProvider>)
  expect(screen.queryByText(/当前值已变化/)).not.toBeInTheDocument()
  view.rerender(<LanguageProvider><ParsingDiagnosticsPanel snapshot={first} paper={{...draft.paper,year:2013}} /></LanguageProvider>)
  expect(screen.getByText(/当前值已变化/)).toBeVisible()
  view.rerender(<LanguageProvider><ParsingDiagnosticsPanel snapshot={first} paper={{...draft.paper,doi:'10.9999/another'}} /></LanguageProvider>)
  expect(screen.getByText(/当前值已变化/)).toBeVisible()
  view.rerender(<LanguageProvider><ParsingDiagnosticsPanel snapshot={first} paper={{...draft.paper,title:'Another paper'}} /></LanguageProvider>)
  expect(screen.getByText(/当前值已变化/)).toBeVisible()
  view.rerender(<LanguageProvider><ParsingDiagnosticsPanel snapshot={first} paper={draft.paper} /></LanguageProvider>)
  expect(screen.queryByText(/当前值已变化/)).not.toBeInTheDocument()
})
