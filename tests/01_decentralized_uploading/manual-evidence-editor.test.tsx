import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn(), download: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('立即打开未保存字段即可填写说明，显式保存先保存主值并使用新版本', async () => {
  let serverValue = '原始标题', version = 1
  const calls: string[] = []
  const item = (): EvidenceRecord => ({ key: 'title', item_key: 'a'.repeat(64), field: 'paper.title', label: '标题', current_value: serverValue, status: 'supported', reason: '原文', evidences: [] })
  vi.mocked(api.post).mockImplementation(async (url) => {
    expect(url).toContain('/preflight')
    return { version: `v${version}`, needs_check: false, records: [item()] } as never
  })
  vi.mocked(api.get).mockImplementation(async () => ({ ok: true, data: {
    changed: serverValue !== '原始标题', reason: '', no_evidence_reason: '', items: [],
  } }) as never)
  vi.mocked(api.put).mockImplementation(async (_url, body: any) => {
    calls.push('说明')
    expect(serverValue).toBe('人工标题')
    expect(body).toMatchObject({ expected_version: 'v2', reason: '对照作者稿', no_evidence_reason: '没有电子附件' })
    return { ok: true, data: { changed: true, status: 'draft', reason: body.reason, no_evidence_reason: body.no_evidence_reason, items: [] } } as never
  })
  function Editor() {
    const [value, setValue] = useState('原始标题')
    const workflow = useEvidenceWorkflow({ target: { target: 'upload', target_id: 'fixture' },
      getCurrentValue: () => ({ field: 'paper.title', value }),
      saveCurrent: async () => { calls.push('主值'); serverValue = value; version++; return true },
    })
    return <><input aria-label="主表单标题" value={value} onChange={e => { workflow.invalidate('paper.title'); setValue(e.target.value) }} />
      <button onClick={() => workflow.openIssue('title')}>查看标题</button>{workflow.dialog}</>
  }
  render(<Editor />)
  await waitFor(() => expect(api.post).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('主表单标题'), { target: { value: '人工标题' } })
  fireEvent.click(screen.getByText('查看标题'))
  const reason = await screen.findByLabelText('人工修改判断理由（必填）')
  expect(calls).toEqual([])
  fireEvent.change(reason, { target: { value: '对照作者稿' } })
  fireEvent.click(screen.getByLabelText('不提供证据'))
  fireEvent.change(screen.getByLabelText('不提供证据的理由（必填）'), { target: { value: '没有电子附件' } })
  fireEvent.click(screen.getByText('保存人工修改说明'))
  await waitFor(() => expect(calls).toEqual(['主值', '说明']))
})

it('主表单保存失败保留人工输入且不发送说明请求', async () => {
  const record: EvidenceRecord = { key: 'title', item_key: 'b'.repeat(64), field: 'paper.title', label: '标题', current_value: '旧值', status: 'supported', reason: '', evidences: [] }
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', records: [record] } as never)
  vi.mocked(api.get).mockResolvedValue({ data: { changed: true, reason: '', no_evidence_reason: '', items: [] } } as never)
  function Editor() {
    const workflow = useEvidenceWorkflow({ target: { target: 'revision', target_id: 'fixture' }, getCurrentValue: () => ({ field: 'paper.title', value: '新值' }), saveCurrent: async () => false })
    return <><button onClick={() => workflow.openIssue('title')}>查看标题</button>{workflow.dialog}</>
  }
  render(<Editor />)
  await waitFor(() => expect(api.post).toHaveBeenCalled())
  fireEvent.click(screen.getByText('查看标题'))
  fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'), { target: { value: '请保留这个理由' } })
  fireEvent.click(screen.getByText('保存人工修改说明'))
  await screen.findByText(/请先保存当前编辑|保存当前内容失败|主表单/)
  expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('请保留这个理由')
  expect(api.put).not.toHaveBeenCalled()
})
