import React from 'react'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import CitationMatchingPage from '../../frontend/src/pages/CitationMatchingPage'
import { allocateGraphPositions } from '../../frontend/src/lib/citationGraphLayout'
import { api } from '../../frontend/src/lib/api'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('确定布局与增量位置', () => {
  it('输入顺序不改变默认位置，旧位置及手动位置不会被新增节点覆盖', () => {
    const first = allocateGraphPositions(['paper:3', 'paper:1', 'paper:2'], [], 2)
    expect([...allocateGraphPositions(['paper:2', 'paper:3', 'paper:1'], [], 2)]).toEqual([...first])
    const occupied = [{ x: 400, y: 300 }, ...first.values()]
    const before = structuredClone(occupied)
    const extra = allocateGraphPositions(['paper:4'], occupied, 2).get('paper:4')!
    expect(occupied).toEqual(before)
    expect(occupied.some(p => Math.abs(p.x - extra.x) < 320 && Math.abs(p.y - extra.y) < 150)).toBe(false)
  })
})

describe('匹配结果页', () => {
  it('保留全部引文，只填色命中项，并在重新打开时只读结果', async () => {
    const paper = { paper_id: 2, title: 'Library paper', authors: ['A'], year: 2020, doi: null }
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { status: 'completed', paper,
      downstream: [{ paper, decision: { reason: '原始参考文献对应' } }],
      references: [
        { reference_index: 0, raw_citation: 'Matched original reference', matched_paper: paper, decision: { reason: '题名对应' } },
        { reference_index: 1, raw_citation: 'External reference stays visible', matched_paper: null, decision: { reason: '未命中' } },
      ] } })
    const mount = () => render(<MemoryRouter initialEntries={['/upload/tasks/example/citation-matching']}>
      <Routes><Route path="/upload/tasks/:taskId/citation-matching" element={<CitationMatchingPage />} /></Routes>
    </MemoryRouter>)
    const first = mount()
    expect(await screen.findByText('External reference stays visible')).toBeTruthy()
    expect(screen.getByText('Matched original reference')).toBeTruthy()
    expect(document.querySelectorAll('[data-matched="true"]').length).toBe(2)
    expect(document.querySelectorAll('[data-matched="false"]').length).toBe(1)
    expect(get).toHaveBeenCalledTimes(1)
    first.unmount()
    mount()
    await screen.findByText('External reference stays visible')
    expect(get).toHaveBeenCalledTimes(2)
    expect(get.mock.calls.every(call => call[0] === '/api/upload-tasks/example/citation-matching')).toBe(true)
  })
})
