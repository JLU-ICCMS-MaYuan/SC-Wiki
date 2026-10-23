import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { ThemeProvider } from '@mui/material'
import theme from '../../frontend/src/theme'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import AuthDemo from '../../frontend/src/demos/auth/AuthDemo'
import { createDemoAuth } from '../../frontend/src/demos/auth/mockAuth'
import { advanceOrbit, DEFAULT_SPEED, MAX_SPEED, normalizeAngle, pushOrbit, RESTART_SPEED, TAU } from '../../frontend/src/demos/auth/orbitMotion'

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

  it('邮箱重置必须先验证、凭证单次使用，改密后旧密码失效', async () => {
    const auth = createDemoAuth()
    const email = 'researcher@example.com'
    expect((await settle(auth.resetPassword(email, 'fake', 'newPassword123'))).error).toBe('expired')
    await settle(auth.requestPasswordReset(email))
    expect((await settle(auth.requestPasswordReset(email))).error).toBe('cooldown')
    expect((await settle(auth.verifyPasswordReset(email, '000000'))).error).toBe('invalidCode')
    const result = await settle(auth.verifyPasswordReset(email, '123456'))
    const grant = result.value!
    expect((await settle(auth.verifyPasswordReset(email, '123456'))).error).toBe('expired')
    expect((await settle(auth.resetPassword('unverified@example.com', grant, 'newPassword123'))).error).toBe('expired')
    expect((await settle(auth.resetPassword(email, grant, 'short'))).error).toBe('shortPassword')
    expect((await settle(auth.resetPassword(email, grant, 'newPassword123'))).error).toBe('')
    expect((await settle(auth.resetPassword(email, grant, 'anotherPass123'))).error).toBe('expired')
    expect((await settle(auth.login(email, 'demo123456'))).error).toBe('credentials')
    expect((await settle(auth.login(email, 'newPassword123'))).error).toBe('')
  })

  it('重置码与注册码分离，未知邮箱不可验证；过期和取消的授权不可改密', async () => {
    const auth = createDemoAuth(), email = 'researcher@example.com'
    await settle(auth.resend('unverified@example.com'))
    expect((await settle(auth.verifyPasswordReset('unverified@example.com', '123456'))).error).toBe('expired')
    await settle(auth.requestPasswordReset('unknown@example.com'))
    expect((await settle(auth.verifyPasswordReset('unknown@example.com', '123456'))).error).toBe('invalidCode')
    await settle(auth.requestPasswordReset(email))
    await vi.advanceTimersByTimeAsync(300_001)
    expect((await settle(auth.verifyPasswordReset(email, '123456'))).error).toBe('expired')
    await settle(auth.requestPasswordReset(email))
    const grant = (await settle(auth.verifyPasswordReset(email, '123456'))).value!
    await vi.advanceTimersByTimeAsync(300_001)
    expect((await settle(auth.resetPassword(email, grant, 'newPassword123'))).error).toBe('expired')
    await settle(auth.requestPasswordReset(email))
    const next = (await settle(auth.verifyPasswordReset(email, '123456'))).value!
    auth.cancelPasswordReset(email)
    expect((await settle(auth.resetPassword(email, next, 'newPassword123'))).error).toBe('expired')
  })

  it('重置验证码五次错误锁定，重发后恢复且旧授权失效', async () => {
    const auth = createDemoAuth(), email = 'researcher@example.com'
    await settle(auth.requestPasswordReset(email))
    for (let i = 0; i < 5; i++) await settle(auth.verifyPasswordReset(email, '000000'))
    expect((await settle(auth.verifyPasswordReset(email, '123456'))).error).toBe('tooManyAttempts')
    await vi.advanceTimersByTimeAsync(60_000)
    await settle(auth.requestPasswordReset(email))
    const grant = (await settle(auth.verifyPasswordReset(email, '123456'))).value!
    await vi.advanceTimersByTimeAsync(60_000)
    await settle(auth.requestPasswordReset(email))
    expect((await settle(auth.resetPassword(email, grant, 'newPassword123'))).error).toBe('expired')
  })
})

describe('可推动与定点停靠的轨道', () => {
  it('12 秒默认周期、重复推动不超上限，停靠后以低速重启', () => {
    const motion = { angle: .55, speed: DEFAULT_SPEED, target: null as number | null }
    advanceOrbit(motion, 12_000)
    expect(motion.angle).toBeCloseTo(.55)
    for (let i = 0; i < 20; i++) pushOrbit(motion, false)
    expect(motion.speed).toBe(MAX_SPEED)
    expect(TAU / motion.speed).toBeCloseTo(1000, 8)
    motion.target = .8
    expect(advanceOrbit(motion, 1000)).toBe(true)
    expect(motion.angle).toBeCloseTo(.8)
    expect(motion.speed).toBe(0)
    expect(advanceOrbit(motion, 10000)).toBe(false)
    pushOrbit(motion, true)
    expect(motion.speed).toBe(RESTART_SPEED)
    expect(motion.target).toBeNull()
    pushOrbit(motion, false)
    expect(motion.speed).toBeGreaterThan(RESTART_SPEED)
  })
  it('跨零点、大步长与当前位置停靠不会错过目标；新目标取代旧目标', () => {
    const motion = { angle: TAU - .1, speed: DEFAULT_SPEED, target: .1 as number | null }
    expect(advanceOrbit(motion, 100)).toBe(false)
    expect(advanceOrbit(motion, 10000)).toBe(true)
    expect(motion.angle).toBeCloseTo(.1)
    pushOrbit(motion, true)
    motion.target = normalizeAngle(-.2)
    motion.target = motion.angle
    expect(advanceOrbit(motion, 0)).toBe(true)
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

  it('忘记密码按钮进入完整改密流程，新密码可以模拟登录且零真实请求', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Demo must not fetch'))
    mount()
    expect(screen.queryByLabelText('新密码')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '忘记密码？' }))
    fireEvent.change(screen.getByLabelText('邮箱'), { target: { value: 'researcher@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: '发送验证码' }))
    await screen.findByRole('heading', { name: '验证你的身份' })
    expect(screen.queryByLabelText('新密码')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('6 位验证码'), { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: '验证邮箱' }))
    await screen.findByRole('heading', { name: '设置新密码' })
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'newPassword123' } })
    fireEvent.change(screen.getByLabelText('确认新密码'), { target: { value: 'differentPass123' } })
    fireEvent.click(screen.getByRole('button', { name: '确认修改密码' }))
    await screen.findByText('两次输入的密码不一致，请检查后重试。')
    fireEvent.change(screen.getByLabelText('确认新密码'), { target: { value: 'newPassword123' } })
    fireEvent.click(screen.getByRole('button', { name: '确认修改密码' }))
    await screen.findByRole('heading', { name: '密码已更新' })
    fireEvent.click(screen.getByRole('button', { name: '返回登录' }))
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'newPassword123' } })
    fireEvent.click(screen.getByRole('button', { name: '登录', exact: true }))
    await screen.findByRole('heading', { name: '欢迎回来，研究者。' })
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
