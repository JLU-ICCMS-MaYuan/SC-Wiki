import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import ManualEvidenceSection from '../../frontend/src/components/ManualEvidenceSection'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn(), download: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

it('人工修改只显示判断理由和证据二选一，缺证路径保存独立理由', async () => {
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
  await waitFor(() => expect(screen.getByLabelText('人工修改判断理由（必填）')).toBeInTheDocument())
  expect(screen.queryByText('Defang Duan')).not.toBeInTheDocument()
  expect(screen.queryByText('Tian Cui')).not.toBeInTheDocument()
  expect(document.body.textContent).not.toContain('["Defang Duan"')
  expect(screen.queryByLabelText('不提供证据的理由（必填）')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'), { target: { value: '对照作者页' } })
  fireEvent.click(screen.getByLabelText('不提供证据'))
  fireEvent.change(screen.getByLabelText('不提供证据的理由（必填）'), { target: { value: '暂无截图' } })
  expect(screen.queryByText('选择图片、文本或 PDF')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('保存人工修改说明'))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(
    `/api/rag/evidence/upload/task/manual/${itemKey}`,
    expect.objectContaining({ expected_version: 'v1', reason: '对照作者页', no_evidence_reason: '暂无截图' }),
  ))
})

it('提供证据路径上传 PDF，不要求填写来源说明', async () => {
  const itemKey = 'e'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: true, reason: '', no_evidence_reason: '曾经没有证据', items: [],
  } } as never)
  vi.mocked(api.put).mockResolvedValue({ ok: true, data: {
    changed: true, reason: '查看原始报告', no_evidence_reason: '', items: [],
  } } as never)
  vi.mocked(api.post).mockResolvedValue({ ok: true, data: {
    changed: true, reason: '查看原始报告', no_evidence_reason: '',
    items: [{ id: 'pdf', kind: 'pdf', filename: 'report.pdf', source_description: 'report.pdf' }],
  } } as never)
  render(<ManualEvidenceSection target={{ target: 'upload', target_id: 'task' }} version="v1"
    record={{ key: 'field', item_key: itemKey, field: 'paper.summary', label: '总结', status: 'missing', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getByLabelText('人工修改判断理由（必填）')).toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'), { target: { value: '查看原始报告' } })
  fireEvent.click(screen.getByLabelText('提供证据'))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ no_evidence_reason: '' })))
  expect(screen.queryByLabelText('不提供证据的理由（必填）')).not.toBeInTheDocument()
  const file = new File(['%PDF-1.4'], 'report.pdf', { type: 'application/pdf' })
  fireEvent.change(document.querySelector('input[type=file]')!, { target: { files: [file] } })
  await waitFor(() => expect(screen.getByText('上传人工证据')).toBeEnabled())
  fireEvent.click(screen.getByText('上传人工证据'))
  await waitFor(() => expect(api.post).toHaveBeenCalled())
  const body = vi.mocked(api.post).mock.calls[0][1] as FormData
  expect(body.get('file')).toBe(file)
  expect(body.has('source_description')).toBe(false)
  expect(api.put).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ no_evidence_reason: '' }))
})

it('已有待提交附件时不能直接切到无证据路径保存', async () => {
  const itemKey = 'f'.repeat(64)
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: {
    changed: true, status: 'draft', reason: '核对报告', no_evidence_reason: '',
    items: [{ id: 'file', kind: 'pdf', filename: 'report.pdf', source_description: 'report.pdf' }],
  } } as never)
  render(<ManualEvidenceSection target={{ target: 'upload', target_id: 'task' }} version="v1"
    record={{ key: 'field', item_key: itemKey, field: 'paper.summary', label: '总结', status: 'missing', reason: '', evidences: [] }} />)
  await waitFor(() => expect(screen.getAllByText('report.pdf').length).toBeGreaterThan(0))
  fireEvent.click(screen.getByLabelText('不提供证据'))
  expect(screen.getByText('请先移除当前待提交的证据，再选择不提供证据。')).toBeInTheDocument()
  expect(screen.getByText('保存人工修改说明')).toBeDisabled()
  expect(api.put).not.toHaveBeenCalled()
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
  expect(screen.queryByText('保存人工修改说明')).not.toBeInTheDocument()
  expect(screen.queryByText('选择图片、文本或 PDF')).not.toBeInTheDocument()
})
