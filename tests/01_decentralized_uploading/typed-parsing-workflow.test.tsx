import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import UploadParsingDetail from '../../frontend/src/components/UploadParsingDetail'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 2, role: 'user' } }) }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.useRealTimers() })

it.each(['unmatched', 'uncertain', 'failed'])('%s 暂停只显示通用结果，不加载编辑器或继续轮询', async status => {
  vi.useFakeTimers()
  vi.mocked(api.get).mockResolvedValue({ data: {
    status: 'needs_workflow', stage: 'extracting', next_poll_ms: null,
    chunks: [], summary: { completed: 0, total: 0, status: 'extracting' },
    workflow_assessment: { status, reason: '尚无适用流程', paper: { title: 'Experimental paper', authors: ['A. Author'], year: 2026 } },
    files: [{ file_id: 'main', original_filename: 'source.pdf' }],
  } })
  render(<LanguageProvider><UploadParsingDetail taskId="isolated" /></LanguageProvider>)
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  expect(screen.getByText('Experimental paper')).toBeVisible()
  expect(screen.getByText(/专用解析暂停/)).toBeVisible()
  expect(screen.queryByRole('button', { name: /提交|手动填写|保存/ })).toBeNull()
  await act(async () => { vi.advanceTimersByTime(10_000) })
  expect(api.get).toHaveBeenCalledTimes(1)
  expect(api.post).not.toHaveBeenCalled()
})

it('新任务在选定流程前读取失败时，不展示手动填写绕过入口', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: {
    status: 'failed', stage: 'extracting', workflow_policy: 'typed-parsing-v1',
    next_poll_ms: null, chunks: [], partial_draft: null,
    summary: { completed: 0, total: 0, status: 'extracting' },
  } })
  render(<LanguageProvider><UploadParsingDetail taskId="unselected" /></LanguageProvider>)
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  expect(screen.queryByRole('button', { name: '手动填写' })).toBeNull()
  expect(api.get).toHaveBeenCalledTimes(1)
})
