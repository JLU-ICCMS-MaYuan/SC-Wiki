import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { EvidenceRegion } from '../../frontend/src/components/EvidenceRegion'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('原文上下文不丢失，标记切换不重复请求且支持Unicode字符位置', async () => {
  const text = '🔬 At 150 GPa, Tc is 200 K; conditions apply.'
  const start = Array.from(text).join('').indexOf('200 K') - 1
  vi.mocked(api.post).mockResolvedValue({ status: 'text_only', context_text: text,
    text_locator: { char_interval: [start, start + 5], match_kind: 'exact', text_sha256: 'verified-text' } })
  const view = render(<EvidenceRegion target={{ target: 'upload', target_id: 'current-task' }}
    source={{ file_id: 'main', page_start: 1, chunk_index: 0, quote: '200 K' }} />)
  fireEvent.click(screen.getByRole('button', { name: '查看原 PDF 区域' }))
  const toggle = await screen.findByRole('button', { name: '隐藏来源标记' })
  expect(view.container.querySelector('mark')).toHaveTextContent('200 K')
  expect(view.container.querySelector('[data-source-context]')).toHaveTextContent('150 GPa')
  fireEvent.click(toggle)
  expect(view.container.querySelector('mark')).toBeNull()
  expect(view.container.querySelector('[data-source-context]')).toHaveTextContent('conditions apply.')
  fireEvent.click(screen.getByRole('button', { name: '显示来源标记' }))
  expect(view.container.querySelector('mark')).toHaveTextContent('200 K')
  expect(api.post).toHaveBeenCalledTimes(1)
})
