import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { ThemeProvider } from '@mui/material'
import theme from '../../frontend/src/theme'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import AuthDemo from '../../frontend/src/demos/auth/AuthDemo'
import { createDemoAuth } from '../../frontend/src/demos/auth/mockAuth'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })

describe('独立 Demo 的内存认证', () => {
  beforeEach(() => vi.useFakeTimers())
  const settle = async <T,>(promise: Promise<T>) => {
    const result = promise.then(value => ({ value, error: '' }), error => ({ value: undefined, error: error.message }))
    await vi.advanceTimersByTimeAsync(500)
    return result
  }

  it('注册、错误验证码、重发冷却、验证后登录；刷新式重建服务不保留账号', async () => {
    const auth = createDemoAuth()
    expect((await settle(auth.register({ email: 'new@example.com', password: 'password123', username: 'new_user', realName: '' }))).error).toBe('')
    expect((await settle(auth.login('new@example.com', 'password123'))).error).toBe('unverified')
    expect((await settle(auth.verify('new@example.com', '000000'))).error).toBe('invalidCode')
    expect((await settle(auth.resend('new@example.com'))).error).toBe('cooldown')
    await vi.advanceTimersByTimeAsync(60_000)
    expect((await settle(auth.resend('new@example.com'))).error).toBe('')
    expect((await settle(auth.verify('new@example.com', '123456'))).error).toBe('')
    expect((await settle(auth.login('new@example.com', 'password123'))).error).toBe('')
    expect((await settle(createDemoAuth().login('new@example.com', 'password123'))).error).toBe('credentials')
  })

  it('既有用户名规则、占用、短密码和凭据错误仍会拒绝', async () => {
    const auth = createDemoAuth()
    const form = { email: 'new@example.com', password: 'password123', username: 'root', realName: '' }
    expect((await settle(auth.register(form))).error).toBe('invalidUsername')
    expect((await settle(auth.register({ ...form, username: 'good_name', password: 'short' }))).error).toBe('shortPassword')
    expect((await settle(auth.register({ ...form, username: 'researcher' }))).error).toBe('taken')
    expect((await settle(auth.login('researcher@example.com', 'wrong'))).error).toBe('credentials')
  })

  it('验证码过期和五次失败后可通过重发恢复，验证码单次消费', async () => {
    const auth = createDemoAuth()
    await settle(auth.resend('unverified@example.com'))
    await vi.advanceTimersByTimeAsync(300_001)
    expect((await settle(auth.verify('unverified@example.com', '123456'))).error).toBe('expired')
    await settle(auth.resend('unverified@example.com'))
    for (let i = 0; i < 5; i++) await settle(auth.verify('unverified@example.com', '111111'))
    expect((await settle(auth.verify('unverified@example.com', '123456'))).error).toBe('tooManyAttempts')
    await vi.advanceTimersByTimeAsync(60_000)
    await settle(auth.resend('unverified@example.com'))
    expect((await settle(auth.verify('unverified@example.com', '123456'))).error).toBe('')
    expect((await settle(auth.verify('unverified@example.com', '123456'))).error).toBe('expired')
  })
})

describe('独立 Demo 表单', () => {
  beforeEach(() => {
    localStorage.clear()
    window.history.replaceState({}, '', '/auth-demo.html')
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  })
  afterEach(() => vi.unstubAllGlobals())
  const mount = () => render(<ThemeProvider theme={theme}><LanguageProvider><AuthDemo /></LanguageProvider></ThemeProvider>)

  it('邮箱登录成功只显示演示结果，不请求真实接口、不改认证存储', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Demo must not fetch'))
    localStorage.setItem('access_token', 'existing-token')
    mount()
    fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'researcher@example.com' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'demo123456' } })
    fireEvent.click(screen.getByRole('button', { name: '登录', exact: true }))
    expect(screen.getByRole('button', { name: '正在处理…' })).toBeDisabled()
    await screen.findByRole('heading', { name: '欢迎回来，研究者。' })
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(localStorage.getItem('access_token')).toBe('existing-token')
    expect(localStorage.length).toBe(1)
  })

  it('注册至验证码，再到成功；仅在演示环境完成', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Demo must not fetch'))
    mount()
    fireEvent.click(screen.getByRole('tab', { name: '注册' }))
    fireEvent.change(screen.getByLabelText('公开用户名'), { target: { value: 'new_person' } })
    fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'new@example.com' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: '创建账号' }))
    await screen.findByRole('heading', { name: '验证你的邮箱' })
    fireEvent.change(screen.getByLabelText('6 位验证码'), { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: '验证邮箱' }))
    await screen.findByRole('heading', { name: '准备好，开始探索。' })
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(localStorage.length).toBe(0)
  })

  it('未验证邮箱可恢复、英文可切换、减少动画默认暂停', async () => {
    mount()
    expect(screen.getByRole('button', { name: '播放动画' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'unverified@example.com' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'demo123456' } })
    fireEvent.click(screen.getByRole('button', { name: '登录', exact: true }))
    await screen.findByRole('heading', { name: '验证你的邮箱' })
    fireEvent.click(screen.getByRole('button', { name: '重新发送验证码' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /秒后重新发送/ })).toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'English' }))
    expect(screen.getByRole('heading', { name: 'Check your inbox' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Resend in/ })).toBeDisabled()
  })
})
