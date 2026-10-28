import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from '../../frontend/src/context/AuthContext'
import AuthPage from '../../frontend/src/pages/AuthPage'
import { authHref, safeAuthReturnTo } from '../../frontend/src/lib/authNavigation'
import { createProductionAuth } from '../../frontend/src/features/auth/productionService'

const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear(); fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const response = (status: number, body: object) => new Response(status === 204 ? null : JSON.stringify(body), { status })
function Destination() { const loc = useLocation(); return <output>{loc.pathname + loc.search + loc.hash}</output> }
function mount(path = '/auth') {
  render(<MemoryRouter initialEntries={[path]}><AuthProvider><Routes><Route path="/auth" element={<AuthPage />} /><Route path="*" element={<Destination />} /></Routes></AuthProvider></MemoryRouter>)
}

describe('登录来源安全', () => {
  it.each(['https://evil.test', '//evil.test', '/%2fevil.test', '/%252fevil.test', '/\\evil.test', '/%5cevil.test', '/%00evil', '/auth', '/auth?returnTo=/news', '/x/../auth', '/x/../Auth', '/x/../auth-demo.html', '/auth-demo.html', '/%2561uth'])('拒绝 %s', value => {
    expect(safeAuthReturnTo(value)).toBeNull()
  })
  it('保留站内路径、业务参数和锚点', () => {
    expect(safeAuthReturnTo('/search?q=La%20Sc#materials')).toBe('/search?q=La%20Sc#materials')
    expect(authHref({ pathname: '/upload', search: '?task=12', hash: '#draft' })).toBe('/auth?returnTo=%2Fupload%3Ftask%3D12%23draft')
  })
})

it('注册使用用户名标签，失焦提示重复，提交时后端冲突仍被展示', async () => {
  fetchMock.mockResolvedValueOnce(response(200, { available: false, reason: '用户名已被占用' }))
    .mockResolvedValueOnce(response(409, { error: '用户名已被占用' }))
  mount()
  fireEvent.click(screen.getByRole('tab', { name: '注册', exact: true }))
  expect(screen.queryByLabelText('公开用户名')).not.toBeInTheDocument()
  const field = screen.getByLabelText('用户名', { exact: true })
  fireEvent.change(field, { target: { value: 'ExistingUser' } })
  fireEvent.blur(field)
  await screen.findByText('该邮箱或用户名已被使用，请换一个再试。')
  expect(field).toHaveAttribute('aria-invalid', 'true')
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'another@example.test' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'longPassword123' } })
  fireEvent.click(screen.getByRole('button', { name: '创建账号' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('该邮箱或用户名已被使用，请换一个再试。')
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/auth/username-availability?username=ExistingUser', '/api/auth/register'])
  expect(localStorage.getItem('auth_token')).toBeNull()
})

it('正式登录保存会话并返回来源，页面无 Demo 账号提示', async () => {
  fetchMock.mockResolvedValueOnce(response(200, { access_token: 'token', user: { username: 'Researcher' } }))
  mount('/auth?returnTo=%2Fupload%3Ftask%3D12%23draft')
  expect(screen.queryByText(/演示账号|交互演示/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'real@example.test' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'realPassword123' } })
  fireEvent.click(screen.getByRole('button', { name: '登录', exact: true }))
  await screen.findByText('/upload?task=12#draft')
  expect(localStorage.getItem('auth_token')).toBe('token')
})

it('找回流程使用真实 API 契约，验证码授权只在内存，未验证前不能提交新密码', async () => {
  fetchMock.mockResolvedValueOnce(response(202, { resend_after_seconds: 75 }))
    .mockResolvedValueOnce(response(200, { reset_token: 'a'.repeat(64), expires_in_seconds: 300 }))
    .mockResolvedValueOnce(response(204, {}))
  mount()
  fireEvent.click(screen.getByRole('button', { name: '忘记密码？' }))
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'real@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: '发送验证码' }))
  await screen.findByRole('heading', { name: '验证你的身份' })
  expect(screen.getByRole('button', { name: '75 秒后重新发送' })).toBeDisabled()
  expect(screen.queryByLabelText('新密码')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('6 位验证码'), { target: { value: '654321' } })
  fireEvent.click(screen.getByRole('button', { name: '验证邮箱' }))
  await screen.findByRole('heading', { name: '设置新密码' })
  fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'changedPassword123' } })
  fireEvent.change(screen.getByLabelText('确认新密码'), { target: { value: 'changedPassword123' } })
  fireEvent.click(screen.getByRole('button', { name: '确认修改密码' }))
  await screen.findByRole('heading', { name: '密码已更新' })
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/auth/password-reset/request', '/api/auth/password-reset/verify', '/api/auth/password-reset/complete'])
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ email: 'real@example.test', reset_token: 'a'.repeat(64), new_password: 'changedPassword123' })
  expect(localStorage.length).toBe(0)
})

it('重置发送失败不进入验证码页，服务恢复后可以重试', async () => {
  fetchMock.mockResolvedValueOnce(response(503, { code: 'verification_send_failed', resend_after_seconds: 60 }))
  mount()
  fireEvent.click(screen.getByRole('button', { name: '忘记密码？' }))
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'real@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: '发送验证码' }))
  await screen.findByText('验证码发送失败，请稍后重新获取。')
  expect(screen.queryByLabelText('6 位验证码')).not.toBeInTheDocument()
  expect(screen.queryByText('123456')).not.toBeInTheDocument()
})

it('已失效改密凭证不能落成成功页面', async () => {
  const noop = vi.fn()
  const auth = createProductionAuth({ login: noop, register: noop, verifyEmail: noop, resendVerification: noop })
  fetchMock.mockResolvedValueOnce(response(400, { code: 'invalid_reset_token' }))
  await expect(auth.resetPassword('real@example.test', 'a'.repeat(64), 'changedPassword123')).rejects.toThrow('expired')
})

it.each([
  ['/auth?returnTo=%2Fupload%3Ftask%3D12%23draft', '/upload?task=12#draft'],
  ['/auth?returnTo=https%3A%2F%2Fevil.test', '/news'],
  ['/auth', '/news'],
])('其他标签页登录后自动安全返回：%s', async (path, destination) => {
  fetchMock.mockResolvedValue(response(200, { user: { id: 1, username: 'Researcher' } }))
  mount(path)
  localStorage.setItem('auth_token', 'external-token')
  localStorage.setItem('auth_user', JSON.stringify({ id: 1, username: 'Researcher' }))
  localStorage.setItem('auth_session_revision', 'external-session')
  fireEvent(window, new StorageEvent('storage', { key: 'auth_token', storageArea: localStorage }))
  await screen.findByText(destination)
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/auth/me'])
})
