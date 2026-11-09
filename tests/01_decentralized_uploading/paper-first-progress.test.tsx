import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import UploadPage from '../../frontend/src/pages/UploadPage'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 7, role: 'user' } }) }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('材料组填写后核对并保存的进度沿现有轮询显示', async () => {
  const id = 'c'.repeat(32)
  vi.mocked(api.post).mockResolvedValue({records:[],version:'fixture'})
  vi.mocked(api.get).mockImplementation(async path => {
    if (path === `/api/upload-tasks/${id}`) return {data: {task_id:id,status:'summarizing',stage:'summarizing',files:[]}} as never
    if (path.endsWith('/parsing')) return {data: {status:'summarizing',stage:'summarizing',processing_phase:'material_reviewing',
      material_batch:{index:2,total:3,state_count:2,completed_states:2,action:'reviewing'},
      files:[],chunks:[],partial_draft:{paper:{title:'CaH6',authors:[],paper_type:'unknown'},material_states:[]},
      summary:{completed:5,total:5},next_poll_ms:null}} as never
    return {data:{},items:[],records:[],jobs:[],space_groups:[],material_families:[],structure_families:[],material_dimensionalities:[]} as never
  })
  render(<MemoryRouter><UploadPage taskId={id} /></MemoryRouter>)
  expect(await screen.findByText('材料表单：第 2/3 组 · 核对 · 已保存 2 个材料状态')).toBeVisible()
  expect(vi.mocked(api.post).mock.calls.filter(([path]) => /\/jobs$|\/submit$|\/check$/.test(path))).toHaveLength(0)
})

it.each([
  ['paper_reviewing', '核对并保存论文级字段', ''],
  ['material_extracting', '并发提取材料状态与科学结果', ''],
  ['workflow_selection', '读取原文结构表与图片', 'structure_reading'],
])('完整任务页显示实际阶段 %s，取消固定五步文案且不新增请求', async (phase, label, activity) => {
  const id = 'b'.repeat(32)
  vi.mocked(api.post).mockResolvedValue({ records: [], version: 'current' })
  vi.mocked(api.get).mockImplementation(async path => {
    if (path === `/api/upload-tasks/${id}`) return { data: { task_id: id, filename: 'source.pdf', status: 'extracting',
      stage: 'extracting', stage_index: 2, stage_total: 5, processing_status: 'processing', files: [],
      ...(activity ? { model_activity: { phase: activity, status: 'requesting' } } : {}) } } as never
    if (path.endsWith('/parsing')) return { data: { status: 'extracting', stage: 'extracting', processing_phase: phase,
      files: [], chunks: [], partial_draft: { paper: { title: 'Current source', authors: [], paper_type: 'unknown' }, material_states: [] },
      summary: { completed: 0, total: 0 }, next_poll_ms: null } } as never
    return { data: {}, items: [], records: [], jobs: [], space_groups: [], material_families: [], structure_families: [], material_dimensionalities: [] } as never
  })
  const view = render(<MemoryRouter><UploadPage taskId={id} /></MemoryRouter>)
  await waitFor(() => expect(view.container.querySelector('[data-processing-phase-heading]')).toHaveTextContent(label))
  expect(view.container.querySelector('[data-processing-phase-heading]')).not.toHaveTextContent('2/5')
  expect(vi.mocked(api.post).mock.calls.filter(([path]) => /\/jobs$|\/submit$|\/check$/.test(path))).toHaveLength(0)
})
