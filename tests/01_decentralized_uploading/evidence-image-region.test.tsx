import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { EvidenceRegion } from '../../frontend/src/components/EvidenceRegion'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

const source = { file_id: 'main', source_name: '附件.pdf', chunk_index: 0, page_start: 2,
  block_id: 'figure-1', evidence_kind: 'pdf_image' as const }
const target = { target: 'upload' as const, target_id: 'task' }

it('图像依据打开字段即加载可靠 PDF 区域', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'located', image: 'data:image/png;base64,AA==',
    region: [0.1, 0.1, 0.2, 0.2], parser: { name: 'layout', mode: 'layout' } } as never)
  render(<EvidenceRegion target={target} source={source} />)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/region',
    expect.objectContaining({ block_id: 'figure-1', quote: undefined, pdf_page: 2 })))
  expect(await screen.findByAltText('原 PDF 页面与证据区域高亮')).toBeInTheDocument()
  expect(screen.getByText(/附件.pdf · 第 2 页/)).toBeInTheDocument()
})

it('图像加载失败仍保留来源文件和位置', async () => {
  vi.mocked(api.post).mockRejectedValue(new Error('unavailable'))
  render(<EvidenceRegion target={target} source={source} />)
  expect(await screen.findByText(/区域暂不可用/)).toBeInTheDocument()
  expect(screen.getByText(/附件.pdf · 第 2 页/)).toBeInTheDocument()
})
