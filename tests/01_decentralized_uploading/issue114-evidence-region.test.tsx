import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { EvidenceRegion } from '../../frontend/src/components/EvidenceRegion'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const source = { file_id: 'f', chunk_index: 0, page_start: 1, quote: 'Tc = 200 K' }
it('按需请求区域并保留原文，高亮在页面范围内', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'located', image: 'data:image/png;base64,aA==', region: [.1,.1,.4,.2], parser: { name: 'docling', mode: 'text' } })
  render(<EvidenceRegion target={{ target: 'upload', target_id: 'task' }} source={source} />)
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '查看原 PDF 区域' }))
  expect(await screen.findByRole('img')).toHaveAttribute('alt', '原 PDF 页面与证据区域高亮')
  expect(screen.getByText(/Tc = 200 K/)).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/region', expect.objectContaining({ file_id: 'f', quote: 'Tc = 200 K' }))
})
it('区域失败保留页码和引句并允许重试', async () => {
  vi.mocked(api.post).mockRejectedValue(new Error('unavailable'))
  render(<EvidenceRegion target={{ target: 'paper', target_id: '1' }} source={source} />)
  fireEvent.click(screen.getByRole('button'))
  expect(await screen.findByText('区域暂不可用，请继续核对页码和原文。')).toBeInTheDocument()
  expect(screen.getByText(/Tc = 200 K/)).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
})
it('切换来源后不显示迟到的旧区域', async () => {
  let finish: (data: unknown) => void = () => {}
  vi.mocked(api.post).mockImplementation(() => new Promise(resolve => { finish = resolve }) as never)
  const view = render(<EvidenceRegion target={{ target: 'upload', target_id: 'task' }} source={source} />)
  fireEvent.click(screen.getByRole('button'))
  view.rerender(<EvidenceRegion target={{ target: 'upload', target_id: 'task2' }} source={{ ...source, quote: 'New quote' }} />)
  finish({ status: 'located', image: 'data:image/png;base64,aA==', region: [0,0,1,1] })
  await waitFor(() => expect(screen.queryByRole('img')).not.toBeInTheDocument())
})
