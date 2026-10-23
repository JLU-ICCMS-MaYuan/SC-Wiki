import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../../frontend/src/context/AuthContext'
import AuthPage from '../../frontend/src/pages/AuthPage'

const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function response(status: number, body: object, retry?: string) {
  return new Response(JSON.stringify(body), { status, headers: retry ? { 'Retry-After': retry } : {} })
}
function show() {
  render(<MemoryRouter><AuthProvider><Routes>
    <Route path="/" element={<AuthPage />} />
    <Route path="/account" element={<div>注册验证完成</div>} />
  </Routes></AuthProvider></MemoryRouter>)
}
function register() {
  fireEvent.click(screen.getByRole('tab', { name: '注册' }))
  fireEvent.change(screen.getByLabelText('公开用户名'), { target: { value: 'Researcher' } })
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'researcher@example.test' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'strong-pass-123' } })
  fireEvent.click(screen.getByRole('button', { name: '创建账号' }))
}
function login() {
  fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'researcher@example.test' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'strong-pass-123' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
}

it('注册后等待验证码，验证成功才保存登录并进入用户中心', async () => {
  fetchMock.mockResolvedValueOnce(response(202, { requires_email_verification: true, resend_after_seconds: 42 }))
    .mockResolvedValueOnce(response(200, { access_token: 'verified-token', user: { username: 'Researcher', email: 'researcher@example.test' } }))
  show(); register()
  expect(await screen.findByText('42 秒后重新发送')).toBeDisabled()
  expect(localStorage.getItem('auth_token')).toBeNull()
  fireEvent.change(screen.getByLabelText('6 位验证码'), { target: { value: '123456' } })
  fireEvent.click(screen.getByRole('button', { name: '验证邮箱' }))
  expect(await screen.findByText('注册验证完成')).toBeInTheDocument()
  expect(localStorage.getItem('auth_token')).toBe('verified-token')
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/auth/register', '/api/auth/verify-email'])
})

it('首次发送失败保留继续验证入口且不声称已发信', async () => {
  fetchMock.mockResolvedValueOnce(response(503, { code: 'verification_send_failed', requires_email_verification: true, resend_after_seconds: 60 }))
  show(); register()
  expect(await screen.findByLabelText('6 位验证码')).toBeInTheDocument()
  expect(screen.getByText('验证码发送失败，请稍后重新获取。')).toBeInTheDocument()
  expect(screen.queryByText(/验证码已发送至/)).not.toBeInTheDocument()
  expect(localStorage.getItem('auth_token')).toBeNull()
})

it('未验证登录可继续验证，重发限流遵循服务器 Retry-After', async () => {
  fetchMock.mockResolvedValueOnce(response(403, { code: 'email_not_verified' }))
    .mockResolvedValueOnce(response(429, { code: 'verification_rate_limited' }, '125'))
  show(); login()
  const resend = await screen.findByRole('button', { name: '重新发送验证码' })
  fireEvent.click(resend)
  expect(await screen.findByText('125 秒后重新发送')).toBeDisabled()
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ email: 'researcher@example.test', password: 'strong-pass-123' })
  expect(localStorage.getItem('auth_token')).toBeNull()
})

it('错误验证码不会建立会话，重发成功后显示新冷却时间', async () => {
  fetchMock.mockResolvedValueOnce(response(403, { code: 'email_not_verified' }))
    .mockResolvedValueOnce(response(202, { resend_after_seconds: 60 }))
    .mockResolvedValueOnce(response(400, { code: 'invalid_verification_code' }))
  show(); login()
  fireEvent.click(await screen.findByRole('button', { name: '重新发送验证码' }))
  await screen.findByText('60 秒后重新发送')
  fireEvent.change(screen.getByLabelText('6 位验证码'), { target: { value: '123456' } })
  fireEvent.click(screen.getByRole('button', { name: '验证邮箱' }))
  await waitFor(() => expect(screen.getByText('验证码未发送或已过期，请重新发送。')).toBeInTheDocument())
  expect(localStorage.getItem('auth_token')).toBeNull()
})

it('发送期间禁止关闭和切换标签，迟到响应保留注册邮箱', async () => {
  let finish!: (value: Response) => void
  fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
  show()
  register()
  expect(screen.getByRole('tab', { name: '登录' })).toBeDisabled()
  expect(screen.getByLabelText('邮箱')).toBeDisabled()
  expect(screen.getByLabelText('密码')).toBeDisabled()
  expect(screen.getByLabelText('公开用户名')).toBeDisabled()
  const back = screen.getByRole('button', { name: '返回', exact: true })
  expect(back).toBeDisabled()
  fireEvent.click(back)
  expect(screen.getByRole('heading', { name: '从这里，连接新发现' })).toBeInTheDocument()
  finish(response(202, { requires_email_verification: true, resend_after_seconds: 60 }))
  expect(await screen.findByText('researcher@example.test')).toBeInTheDocument()
  expect(screen.getByLabelText('6 位验证码')).toBeInTheDocument()
})
