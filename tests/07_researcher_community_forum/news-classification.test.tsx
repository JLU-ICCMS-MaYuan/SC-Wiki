import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import NewsFeed from '../../frontend/src/components/NewsFeed'
import NewsClassificationLabels from '../../frontend/src/components/NewsClassificationLabels'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('shows all families for reviews in details and hides unknown dimensions', () => {
  const { rerender, container } = render(<NewsClassificationLabels expanded item={{ paper_type: 'review', material_families: [
    { id: 1, name_zh: '铁基超导体', name_en: 'Iron based' }, { id: 2, name_zh: '铜基超导体', name_en: 'Cuprates' },
  ] }} />)
  expect(screen.getByText('综述文章')).toBeInTheDocument()
  expect(screen.getByText('铁基超导体')).toBeInTheDocument()
  expect(screen.getByText('铜基超导体')).toBeInTheDocument()
  rerender(<NewsClassificationLabels expanded item={{ paper_type: 'experimental', theoretical_subtype: 'calculation' }} />)
  expect(screen.queryByText('计算类')).not.toBeInTheDocument()
  rerender(<NewsClassificationLabels item={{ paper_type: null, theoretical_subtype: null, material_families: [] }} />)
  expect(container).toBeEmptyDOMElement()
})

it('measures overflow families and recomputes when the card grows', () => {
  let width = 230
  let resize = () => {}
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    return { width: this.dataset.testid === 'news-classification' ? width : 65, height: 22, x: 0, y: 0, top: 0, left: 0, right: 65, bottom: 22, toJSON() {} }
  })
  vi.stubGlobal('ResizeObserver', class { constructor(callback: () => void) { resize = callback } observe() {} disconnect() {} })
  const item = { paper_type: 'review' as const, material_families: [1, 2, 3].map(id => ({ id, name_zh: `家族${id}`, name_en: `Family ${id}` })) }
  const { rerender } = render(<NewsClassificationLabels item={item} />)
  expect(screen.getByLabelText('另有 2 个材料家族，点击条目查看全部')).toBeInTheDocument()
  width = 500
  // 重新渲染也应触发标签内容变化测量。
  rerender(<NewsClassificationLabels item={{ ...item, paper_type: 'experimental' }} />)
  expect(screen.queryByText('+2')).not.toBeInTheDocument()
  expect(resize).toBeTypeOf('function')
})

it('keeps independent pagination and opens the full classification drawer', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
    const kind = new URL(url, 'http://localhost').searchParams.get('kind')
    return Promise.resolve(new Response(JSON.stringify({ items: [{
      id: kind, title: `${kind} test`, kind, source: 'arxiv', original_source: '', url: 'https://arxiv.org',
      summary: '', summary_source: '', links: [], authors: [], journal: '', doi: '', version: 1,
      published_at: '2026-10-22', date_precision: 'day', last_seen_at: '2026-10-22',
      paper_type: 'theoretical', theoretical_subtype: 'method', material_families: [{ id: 1, name_zh: '氢基超导体', name_en: 'Hydrides' }],
    }], total: 6, page: 1, page_size: 5, sources: [] }), { status: 200 }))
  }))
  render(<NewsFeed />)
  await screen.findByText('preprint test')
  expect(screen.getByText('标签依据标题和摘要自动判断')).toBeInTheDocument()
  fireEvent.click(screen.getByText('preprint test'))
  expect(await screen.findByText('氢基超导体', { selector: '[data-testid="news-classification"] > div:first-child .MuiChip-label' })).toBeInTheDocument()
  expect(screen.getByText('自动采集，未经本站审核')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('关闭'))
  await waitFor(() => expect(screen.getAllByRole('button', { name: '下一页' })).toHaveLength(3))
  fireEvent.click(screen.getAllByRole('button', { name: '下一页' })[1])
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining('kind=preprint&page=2'), expect.anything()))
})
