import React from 'react'
import '@testing-library/jest-dom/vitest'
import {cleanup, render, screen, waitFor} from '@testing-library/react'
import {afterEach, expect, it, vi} from 'vitest'
import UploadParsingDetail from '../../frontend/src/components/UploadParsingDetail'

vi.mock('../../frontend/src/components/StructureViewer3D', () => ({default: () => <div />}))
afterEach(() => {cleanup(); localStorage.clear(); vi.restoreAllMocks()})

const response = (data: unknown) => new Response(JSON.stringify(data), {
  status: 200, headers: {'Content-Type': 'application/json'},
})
const state = {material: 'CaH6', material_name: 'CaH6', state_kind: 'theoretical',
  pressure_value_gpa: 150, tc_results: [], properties: []}

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
  render(<UploadParsingDetail taskId={'a'.repeat(32)} />)
  expect(await screen.findByLabelText('化学式')).toHaveValue('CaH6')
  await waitFor(() => expect(screen.getByLabelText('标题')).toHaveValue('Late title'))
  await screen.findByText('本次处理失败，已生成内容保留为只读预览；失败原因见上方提示。')
  expect(screen.getByLabelText('化学式')).toHaveValue('CaH6')
  expect(screen.getByText('只读预览')).toBeVisible()
  expect(screen.queryByRole('button', {name: '提交审核'})).not.toBeInTheDocument()
  expect(requests.filter(url => /\/check|\/review|\/submit/.test(url))).toHaveLength(0)
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
  render(<UploadParsingDetail taskId={id} />)
  expect(await screen.findByLabelText('标题')).toHaveValue('Saved formal draft')
  expect(screen.queryByText('只读预览')).not.toBeInTheDocument()
  expect(screen.queryByDisplayValue('Obsolete preview')).not.toBeInTheDocument()
})
