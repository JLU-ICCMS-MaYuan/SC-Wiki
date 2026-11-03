import React from 'react'
import '@testing-library/jest-dom/vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {MemoryRouter} from 'react-router-dom'
import UploadParsingDetail from '../../frontend/src/components/UploadParsingDetail'

vi.mock('../../frontend/src/components/StructureViewer3D', () => ({default: () => <div />}))
beforeEach(() => {
  const values = new Map<string,string>()
  vi.stubGlobal('localStorage', {getItem:(key:string)=>values.get(key) ?? null,
    setItem:(key:string,value:string)=>values.set(key,value), removeItem:(key:string)=>values.delete(key), clear:()=>values.clear()})
})
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals()})

const response = (data: unknown) => new Response(JSON.stringify(data), {
  status: 200, headers: {'Content-Type': 'application/json'},
})
const state = {material: 'CaH6', material_name: 'CaH6', state_kind: 'theoretical',
  pressure_value_gpa: 150, tc_results: [], properties: []}

it('图片待处理：在现有分段页显示文件和PDF页码，不声称已完成图像核对', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ok: true, data: {
    status: 'failed', stage: 'reading', chunks: [], partial_draft: null, next_poll_ms: null,
    summary: {completed: 2, total: 2},
    files: [{file_id: 'si', role: 'supplementary', original_filename: 'CaH6-SI.pdf'}],
    pending_visual_regions: [
      {file_id: 'si', pdf_page: 10, block_id: 'figure-a'},
      {file_id: 'si', pdf_page: 5, block_id: 'figure-b'},
      {file_id: 'si', pdf_page: 10, block_id: 'figure-c'},
    ],
  }})))
  render(<MemoryRouter><UploadParsingDetail taskId={'c'.repeat(32)} /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('tab', {name: '分段解析与证据'}))
  expect(screen.getByText('有 3 个图片／公式区域尚未由文字步骤读取。已保留原文位置供后续图像处理，图像内容尚未核对。')).toBeVisible()
  expect(screen.getByText('CaH6-SI.pdf · PDF 第 5, 10 页')).toBeVisible()
})

it('完整上传预览：核对中展示材料，晚到题录和失败均不清空科学区域', async () => {
  let reads = 0
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input); requests.push(url)
    if (!url.endsWith('/parsing')) return response({ok: true})
    reads += 1
    return response({ok: true, data: {
      status: reads >= 3 ? 'failed' : 'summarizing', stage: 'summarizing',
      processing_error: reads >= 3 ? '模型调用失败' : null,
      preview_phase: reads === 1 ? 'organizing' : 'reviewing', files: [], chunks: [],
      partial_draft: {paper: {title: reads === 1 ? 'Initial' : 'Late title', authors: [], paper_type: 'theoretical'},
        material_states: [state]},
      summary: {completed: 2, total: 2}, next_poll_ms: reads >= 3 ? null : 30,
    }})
  }))
  render(<MemoryRouter><UploadParsingDetail taskId={'a'.repeat(32)} /></MemoryRouter>)
  expect(await screen.findByLabelText('化学式')).toHaveValue('CaH6')
  await waitFor(() => expect(screen.getByLabelText('标题')).toHaveValue('Late title'))
  await screen.findByText('本次处理失败，已生成内容保留为只读预览；失败原因见上方提示。')
  expect(screen.getByLabelText('化学式')).toHaveValue('CaH6')
  expect(screen.getByText('只读预览')).toBeVisible()
  expect(screen.queryByRole('button', {name: '提交审核'})).not.toBeInTheDocument()
  expect(requests.filter(url => /\/check|\/review|\/submit/.test(url))).toHaveLength(0)
  expect(requests.filter(url => url.includes('/spectra'))).toHaveLength(0)
})

it('完整上传预览：ready只读取正式草稿，不把最后一份预览当正式内容', async () => {
  const id = 'b'.repeat(32)
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/parsing')) return response({ok: true, data: {
      status: 'ready', files: [], chunks: [], next_poll_ms: null, summary: {completed: 2, total: 2},
      partial_draft: {paper: {title: 'Obsolete preview'}, material_states: [state]},
    }})
    if (url.endsWith('/draft')) return response({ok: true, data: {
      paper: {title: 'Saved formal draft', authors: [], paper_type: 'theoretical'}, material_states: [],
    }})
    return response({ok: true, records: [], version: 'fixture'})
  }))
  render(<MemoryRouter><UploadParsingDetail taskId={id} /></MemoryRouter>)
  expect(await screen.findByLabelText('标题')).toHaveValue('Saved formal draft')
  expect(screen.queryByText('只读预览')).not.toBeInTheDocument()
  expect(screen.queryByDisplayValue('Obsolete preview')).not.toBeInTheDocument()
})

it('自动谱阶段明确仍在处理，不显示已完成或提前读取谱', async () => {
  const requests:string[]=[]
  vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input);requests.push(url)
    if(url.endsWith('/parsing'))return response({ok:true,data:{
      status:'summarizing',stage:'summarizing',preview_phase:'spectra',files:[],chunks:[],
      partial_draft:{paper:{title:'CaH6',authors:[],paper_type:'theoretical'},material_states:[state]},
      summary:{completed:2,total:2},next_poll_ms:null}})
    return response({ok:true})
  }))
  render(<MemoryRouter><UploadParsingDetail taskId={'d'.repeat(32)} /></MemoryRouter>)
  expect(await screen.findByText('正在提取 α²F 和声子态密度；谱处理结束后才进入校对并结束解析计时。')).toBeVisible()
  expect(requests.filter(url=>url.includes('/spectra'))).toHaveLength(0)
})
