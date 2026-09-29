import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LlmProviderSwitcher from '../../frontend/src/components/LlmProviderSwitcher'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'
import { buildLlmHeaders, saveLlmConfig } from '../../frontend/src/lib/llmProvider'

const auth = vi.hoisted(() => ({ user: { id: 1 } as { id: number } | null }))
vi.mock('../../frontend/src/context/AuthContext', async importOriginal => ({
  ...await importOriginal<typeof import('../../frontend/src/context/AuthContext')>(),
  useAuth: () => auth,
}))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('auth_token', 'test-token'); auth.user = { id: 1 }
  vi.mocked(api.get).mockImplementation(async url => ({ data: url.endsWith('/catalog')
    ? { items: [{ id: 'LLM1', name: '共享一', model: 'one' }, { id: 'LLM3', name: '共享三', model: 'three' }] }
    : { provider: 'server:LLM1', provider_name: '共享一', model: 'one', source: 'server' } }) as any)
})
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks() })

it('服务端选择只保存和发送 ID，不出现密钥输入框', async () => {
  const user = userEvent.setup()
  render(<LanguageProvider><LlmProviderSwitcher /></LanguageProvider>)
  await user.click(await screen.findByRole('button', { name: '配置 AI 供应商' }))
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/rag/llm/catalog'))
  await user.click(screen.getByRole('combobox'))
  await user.click(await screen.findByRole('option', { name: '服务端模型 · 共享三 · three' }))
  expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument()
  expect(screen.getByText('使用部署者配置的模型，无需填写 API Key。')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(buildLlmHeaders()).toEqual({ 'X-LLM-Config-ID': 'LLM3' })
  const stored = JSON.parse(localStorage.getItem('sc-wiki.llm-provider')!)
  expect(Object.keys(stored).sort()).toEqual(['model', 'provider', 'providerName', 'serverId'])
  expect(stored.model).toBe('three')
  localStorage.removeItem('auth_token')
  expect(buildLlmHeaders()).toEqual({})
})

it('删除的模型不能自动变成默认，仍能获取新目录重新选择', async () => {
  saveLlmConfig({ provider: 'server:LLM9', serverId: 'LLM9', providerName: '旧模型', model: 'old' })
  const user = userEvent.setup()
  render(<LanguageProvider><LlmProviderSwitcher /></LanguageProvider>)
  await user.click(await screen.findByRole('button', { name: '配置 AI 供应商' }))
  expect(await screen.findAllByText('请登录并重新选择可用的服务端模型')).not.toHaveLength(0)
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(buildLlmHeaders()).toEqual({ 'X-LLM-Config-ID': 'LLM9' })
  expect(screen.getByRole('dialog')).toBeVisible()
  await user.click(screen.getByRole('combobox'))
  await user.click(await screen.findByRole('option', { name: '服务端模型 · 共享一 · one' }))
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(buildLlmHeaders()).toEqual({ 'X-LLM-Config-ID': 'LLM1' })
})
