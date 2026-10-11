import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

const summary = {
  key: 'summary', field: 'paper.summary', label: '总结', status: 'supported', source_kind: 'paper_synthesis',
  reason: '本文各相的压力与 Tc 结果支持这些核心结论。',
  evidences: [{ file_id: 'main', chunk_index: 0, page_start: 2, quote: 'The Im-3m phase reaches 204 K at 200 GPa.' }]
}

function Form({ target = 'upload' }: { target?: 'upload' | 'paper' }) {
  const flow = useEvidenceWorkflow({ target: { target, target_id: 'h3s' } })
  return <><button onClick={() => flow.openIssue('summary')}>查看总结来源</button><button onClick={() => flow.invalidate('paper.summary')}>修改总结</button>{flow.dialog}</>
}

it.each(['upload', 'paper'] as const)('%s 侧栏显示总结归纳理由，不显示直接记载回退', async target => {
  vi.mocked(api.post).mockResolvedValue({ version: 'v1', needs_check: false, records: [summary] } as never)
  await act(async () => render(<Form target={target} />))
  await act(async () => fireEvent.click(screen.getByText('查看总结来源')))
  expect(screen.getByText(/论文归纳：以下原文片段用于支撑总结/)).toBeInTheDocument()
  expect(screen.getAllByText(summary.reason).length).toBeGreaterThan(0)
  expect(screen.getByRole('dialog')).toHaveTextContent(summary.evidences[0].quote)
  expect(screen.queryByText('原文直接记载，无需额外推断。')).not.toBeInTheDocument()
  await act(async () => fireEvent.click(screen.getByText('修改总结')))
  expect(screen.getAllByText(/数据已修改/).length).toBeGreaterThan(0)
  expect(screen.queryByText(/论文归纳：以下原文片段用于支撑总结/)).not.toBeInTheDocument()
  expect(screen.queryByText('原文直接记载，无需额外推断。')).not.toBeInTheDocument()
})
