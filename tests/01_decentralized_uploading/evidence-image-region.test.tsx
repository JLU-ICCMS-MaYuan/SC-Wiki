import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

it('旧 PDF 的唯一文本匹配可按需显示原页并补出页码', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'located', image: 'data:image/png;base64,AA==',
    pdf_page: 1, dpi: 300, crops: [{ image: 'data:image/png;base64,AA==', width: 1200, height: 320,
      highlights: [[0.1, 0.2, 0.3, 0.04], [0.1, 0.25, 0.2, 0.04]] }],
    parser: { name: '原 PDF 文本层检索', mode: 'legacy_text' } } as never)
  render(<EvidenceRegion target={target} source={{ file_id: 'main', source_name: '正文.pdf', quote: 'Tc = 200 K' }} />)
  expect(screen.getByText(/正文.pdf · 原文未提供页码/)).toBeInTheDocument()
  fireEvent.click(screen.getByText('查看原 PDF 区域'))
  expect(await screen.findByAltText('原 PDF 页面与证据区域高亮')).toBeInTheDocument()
  expect(screen.getByText(/正文.pdf · 第 1 页/)).toBeInTheDocument()
  expect(screen.getByText(/原 PDF 文本层唯一匹配/)).toBeInTheDocument()
  expect(screen.getByText(/300 DPI/)).toBeInTheDocument()
  expect(screen.getByAltText('原 PDF 页面与证据区域高亮')).toHaveStyle({ width: '1200px' })
  fireEvent.click(screen.getByRole('button', { name: '点击放大 PDF 局部证据' }))
  expect(screen.getByRole('dialog', { name: '正文.pdf · 第 1 页' })).toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: '点击缩回 PDF 局部证据' }).at(-1)!)
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '正文.pdf · 第 1 页' })).not.toBeInTheDocument())
})

it('旧 PDF 无唯一文本匹配时说明原因且保留引句', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'unlocated' } as never)
  render(<EvidenceRegion target={target} source={{ file_id: 'main', source_name: '正文.pdf', quote: 'ambiguous quote' }} />)
  fireEvent.click(screen.getByText('查看原 PDF 区域'))
  expect(await screen.findByText('引句未在原 PDF 文本层唯一匹配，不能可靠高亮。')).toBeInTheDocument()
  expect(screen.getByText(/ambiguous quote/)).toBeInTheDocument()
})

it('局部 PNG 解码失败只隐藏该图并保留来源引句', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'located', dpi: 300, pdf_page: 1,
    crops: [{ image: 'data:image/png;base64,invalid', width: 1200, height: 320,
      highlights: [[0.1, 0.2, 0.3, 0.04]] }] } as never)
  render(<EvidenceRegion target={target} source={{ file_id: 'main', source_name: '正文.pdf', quote: 'Tc = 200 K' }} />)
  fireEvent.click(screen.getByText('查看原 PDF 区域'))
  fireEvent.error(await screen.findByAltText('原 PDF 页面与证据区域高亮'))
  expect(screen.queryByAltText('原 PDF 页面与证据区域高亮')).not.toBeInTheDocument()
  expect(screen.getByText(/正文.pdf · 第 1 页：Tc = 200 K/)).toBeInTheDocument()
  expect(screen.getByText(/区域暂不可用/)).toBeInTheDocument()
})

it('原始扫描不足 300 DPI 时说明限制而不假称细节已恢复', async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 'located', dpi: 300, pdf_page: 1,
    crops: [{ image: 'data:image/png;base64,AA==', width: 1200, height: 320,
      source_raster_dpi: 72, highlights: [[0.1, 0.2, 0.3, 0.04]] }] } as never)
  render(<EvidenceRegion target={target} source={{ file_id: 'main', source_name: '扫描.pdf', quote: 'Tc = 200 K' }} />)
  fireEvent.click(screen.getByText('查看原 PDF 区域'))
  expect(await screen.findByText(/原始扫描图约 72 DPI/)).toBeInTheDocument()
})
