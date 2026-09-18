import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import MultiFileUploadPanel from '../../frontend/src/components/MultiFileUploadPanel'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn() } }))
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); vi.clearAllMocks() })

it('文件上传 XHR 携带所选模型配置，使入队处理使用同一供应商', async () => {
  localStorage.setItem('auth_token', 'test-session')
  localStorage.setItem('sc-wiki.llm-provider', JSON.stringify({ provider: 'custom', baseUrl: 'http://127.0.0.1:18952/v1', model: 'fixed', apiKey: 'test-key' }))
  const headers: Record<string, string> = {}
  class UploadXhr {
    upload = {}; status = 200; onload?: () => void
    open() {}
    setRequestHeader(key: string, value: string) { headers[key] = value }
    send() { this.onload?.() }
  }
  vi.stubGlobal('XMLHttpRequest', UploadXhr)
  const task = { task_id: 'test-task', files: [{ file_id: 'test-file' }] }
  vi.mocked(api.post).mockResolvedValue({ ok: true, data: task })
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: task })
  const created = vi.fn()
  const { container } = render(<LanguageProvider><MultiFileUploadPanel onCreated={created} /></LanguageProvider>)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['paper'], 'paper.txt', { type: 'text/plain' })] } })
  fireEvent.click(screen.getByRole('button', { name: '开始上传并解析' }))
  await waitFor(() => expect(created).toHaveBeenCalled())
  expect(headers).toMatchObject({ Authorization: 'Bearer test-session', 'X-LLM-Provider': 'custom', 'X-LLM-Base-URL': 'http://127.0.0.1:18952/v1', 'X-LLM-Model': 'fixed', 'X-LLM-Api-Key': 'test-key' })
})
