import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import ManualEvidenceSection from '../../frontend/src/components/ManualEvidenceSection'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), download: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

it('人工修改以姓名列表和独立来源显示，保存理由及缺证原因', async () => {
  const itemKey = 'a'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: true, before_value: ['Defang Duan'], after_value: ['Defang Duan', 'Tian Cui'],
    reason: '', no_evidence_reason: '', items: [],
  } } as never)
  vi.mocked(api.put).mockResolvedValue({ ok: true, data: {
    changed: true, reason: '对照作者页', no_evidence_reason: '暂无截图', items: [],
  } } as never)
  render(<ManualEvidenceSection target={{ target: 'upload', target_id: 'task' }} version="v1"
    record={{ key: 'authors', item_key: itemKey, field: 'paper.authors', label: '作者', status: 'supported', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getAllByText('Defang Duan')).toHaveLength(2))
  expect(screen.getByText('Tian Cui')).toBeInTheDocument()
  expect(document.body.textContent).not.toContain('["Defang Duan"')
  fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'), { target: { value: '对照作者页' } })
  fireEvent.change(screen.getByLabelText('无法提供证据的原因（必填）'), { target: { value: '暂无截图' } })
  fireEvent.click(screen.getByText('保存理由和文字证据'))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(
    `/api/rag/evidence/upload/task/manual/${itemKey}`,
    expect.objectContaining({ expected_version: 'v1', reason: '对照作者页', no_evidence_reason: '暂无截图' }),
  ))
})

it('审核员能查看上传者留在同一字段的人工证据历史', async () => {
  const itemKey = 'b'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: false, reason: '', no_evidence_reason: '', items: [],
    history: [{ id: 'prior', changed: true, actor_user_id: 7, actor_name: 'mayuan',
      reason: '对照实验记录', no_evidence_reason: '', before_value: '旧值', after_value: '新值',
      items: [{ id: 'source', kind: 'text', text: '实验结果', source_description: '实验室笔记' }] }],
  } } as never)
  render(<ManualEvidenceSection target={{ target: 'paper', target_id: '29' }} version="v1"
    record={{ key: 'field', item_key: itemKey, field: 'paper.summary', label: '总结', status: 'supported', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getByText(/历史记录（1）/)).toBeInTheDocument())
  fireEvent.click(screen.getByText(/历史记录（1）/))
  expect(screen.getByText(/mayuan/)).toBeInTheDocument()
  expect(screen.getByText('实验结果')).toBeInTheDocument()
  expect(screen.getByText('对照实验记录')).toBeInTheDocument()
})

it('历史图片在字段改回原值后仍能预览，已提交记录只读', async () => {
  const itemKey = 'c'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: false, reason: '', no_evidence_reason: '', items: [], history: [{
      id: 'prior', changed: true, actor_user_id: 7, actor_name: 'uploader',
      reason: '按截图修正', no_evidence_reason: '', before_value: '旧值', after_value: '新值',
      items: [{ id: 'image', kind: 'image', filename: 'page.png', source_description: '人工截图' }],
    }],
  } } as never)
  vi.mocked(api.download).mockResolvedValue(new Blob(['image'], { type: 'image/png' }) as never)
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL() { return 'blob:manual-image' }
    static revokeObjectURL() { /* jsdom 不实现 Blob URL */ }
  })
  render(<ManualEvidenceSection target={{ target: 'paper', target_id: '29' }} version="v1"
    record={{ key: 'field', item_key: itemKey, field: 'paper.summary', label: '总结', status: 'supported', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getByText(/历史记录（1）/)).toBeInTheDocument())
  fireEvent.click(screen.getByText(/历史记录（1）/))
  fireEvent.click(screen.getByText('page.png'))
  await waitFor(() => expect(screen.getByAltText('人工提供的截图')).toHaveAttribute('src', 'blob:manual-image'))
})

it('已提交的人工修改记录显示理由而没有编辑控件', async () => {
  const itemKey = 'd'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: true, status: 'submitted', before_value: '旧值', after_value: '新值',
    reason: '依据原始实验记录', no_evidence_reason: '原记录不可公开', items: [],
  } } as never)
  render(<ManualEvidenceSection target={{ target: 'paper', target_id: '29' }} version="v1"
    record={{ key: 'field', item_key: itemKey, field: 'paper.summary', label: '总结', status: 'supported', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getByText(/依据原始实验记录/)).toBeInTheDocument())
  expect(screen.queryByText('保存理由和文字证据')).not.toBeInTheDocument()
  expect(screen.queryByText('选择截图或文本文件')).not.toBeInTheDocument()
})
