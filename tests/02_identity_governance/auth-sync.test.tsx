import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { AuthProvider, useAuth, type AuthState, type User } from '../../frontend/src/context/AuthContext'

const alice = { id: 1, username: 'Alice', email: 'alice@example.test', role: 'user', account_status: 'active' } as User
const bob = { ...alice, id: 2, username: 'Bob', email: 'bob@example.test' }
const fetchMock = vi.fn()
let auth: AuthState
const response = (status: number, body: object = {}) => new Response(JSON.stringify(body), { status })
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function Probe() {
  auth = useAuth()
  return <><output>{auth.user?.username || 'guest'}</output><input aria-label="draft" defaultValue="未保存编辑" /></>
}
function mount() { return render(<AuthProvider><Probe /></AuthProvider>) }
function store(token: string, user: User, revision = token) {
  localStorage.setItem('auth_token', token)
  localStorage.setItem('auth_user', JSON.stringify(user))
  localStorage.setItem('auth_session_revision', revision)
}
function notify(key: string | null = 'auth_token') {
  fireEvent(window, new StorageEvent('storage', { key, storageArea: localStorage }))
}
beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('其他标签页登录后采用经当前凭据核验的身份，保留页面输入', async () => {
  fetchMock.mockResolvedValue(response(200, { user: alice }))
  mount()
  fireEvent.change(screen.getByLabelText('draft'), { target: { value: '保留草稿' } })
  // 模拟多键写入期间缓存仍是旧用户；身份必须来自当前凭据的 /me。
  store('alice-token', bob); notify()
  await screen.findByText('Alice')
  expect(fetchMock).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ headers: { Authorization: 'Bearer alice-token' } }))
  expect(screen.getByLabelText('draft')).toHaveValue('保留草稿')
})

it('其他标签页退出或清空存储后，本页同步退出', async () => {
  store('alice-token', alice)
  fetchMock.mockResolvedValue(response(200, { user: alice }))
  mount(); await screen.findByText('Alice')
  localStorage.clear(); notify(null)
  await screen.findByText('guest')
  expect(auth.token).toBeNull()
})

it.each(['focus', 'visibilitychange'])('遗漏 storage 时由 %s 恢复当前会话', async event => {
  fetchMock.mockResolvedValue(response(200, { user: bob }))
  mount(); store('bob-token', bob)
  fireEvent(event === 'focus' ? window : document, new Event(event))
  await screen.findByText('Bob')
})

it.each(['success', 'unauthorized', 'unavailable', 'network'])('旧 /me 的 %s 不得影响重新登录后的会话', async outcome => {
  const old = deferred<Response>()
  store('old-token', alice)
  fetchMock.mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(response(200, { access_token: 'new-token', user: bob }))
  mount()
  await act(async () => { await auth.login('bob@example.test', 'password') })
  await screen.findByText('Bob')
  await act(async () => {
    if (outcome === 'network') old.reject(new TypeError('offline'))
    else old.resolve(response(outcome === 'unauthorized' ? 401 : outcome === 'unavailable' ? 503 : 200, { user: alice }))
  })
  expect(screen.getByText('Bob')).toBeInTheDocument()
  expect(localStorage.getItem('auth_token')).toBe('new-token')
  expect(JSON.parse(localStorage.getItem('auth_user')!).id).toBe(2)
})

it('即便新旧 JWT 相同，旧会话响应也不能越过登录世代', async () => {
  const old = deferred<Response>()
  store('same-token', alice, 'before')
  fetchMock.mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(response(200, { access_token: 'same-token', user: { ...alice, username: 'NewName' } }))
  mount()
  await act(async () => { await auth.login(alice.email, 'password') })
  await act(async () => { old.resolve(response(401)) })
  expect(screen.getByText('NewName')).toBeInTheDocument()
  expect(localStorage.getItem('auth_token')).toBe('same-token')
  expect(localStorage.getItem('auth_session_revision')).not.toBe('before')
})

it.each([503, 'network'])('暂时故障 %s 不清共享凭据，恢复焦点后可重试', async failure => {
  store('alice-token', alice)
  if (failure === 'network') fetchMock.mockRejectedValueOnce(new TypeError('offline'))
  else fetchMock.mockResolvedValueOnce(response(failure as number))
  fetchMock.mockResolvedValueOnce(response(200, { user: alice }))
  mount()
  await waitFor(() => expect(auth.loading).toBe(false))
  expect(localStorage.getItem('auth_token')).toBe('alice-token')
  fireEvent.focus(window)
  await screen.findByText('Alice')
})

it.each([401, 403])('当前会话明确失效 %s 才清理共享认证', async status => {
  store('alice-token', alice)
  fetchMock.mockResolvedValue(response(status))
  mount()
  await waitFor(() => expect(localStorage.getItem('auth_token')).toBeNull())
  expect(auth.user).toBeNull()
})

it('合并同一会话的事件，不因无关存储或重复用户缓存循环核验', async () => {
  fetchMock.mockResolvedValue(response(200, { user: alice }))
  mount(); store('alice-token', alice)
  notify(); notify('auth_user'); notify('auth_session_revision'); fireEvent.focus(window)
  await screen.findByText('Alice')
  notify('auth_user'); notify('sc-wiki.language'); fireEvent.focus(window)
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 25)) })
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('未登录时发出的登录响应不能在主动退出后重新建立会话', async () => {
  const pending = deferred<Response>()
  fetchMock.mockReturnValueOnce(pending.promise)
  mount()
  let result!: Promise<unknown>
  act(() => { result = auth.login(alice.email, 'password').catch(error => error) })
  act(() => { auth.logout() })
  await act(async () => {
    pending.resolve(response(200, { access_token: 'late-token', user: alice }))
    await result
  })
  expect(localStorage.getItem('auth_token')).toBeNull()
  expect(screen.getByText('guest')).toBeInTheDocument()
})

it('旧页面闭包的资料修改不能覆盖新账号', async () => {
  store('alice-token', alice)
  fetchMock.mockResolvedValueOnce(response(200, { user: alice }))
    .mockResolvedValueOnce(response(200, { access_token: 'bob-token', user: bob }))
  mount(); await screen.findByText('Alice')
  const staleReplaceUser = auth.replaceUser
  await act(async () => { await auth.login(bob.email, 'password') })
  act(() => { staleReplaceUser({ ...alice, username: 'Stale' }) })
  expect(screen.getByText('Bob')).toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('auth_user')!).id).toBe(2)
})

it('旧更名响应和卸载后的身份核验不能写回存储', async () => {
  const rename = deferred<Response>()
  const verification = deferred<Response>()
  store('alice-token', alice)
  fetchMock.mockResolvedValueOnce(response(200, { user: alice }))
    .mockReturnValueOnce(rename.promise)
    .mockResolvedValueOnce(response(200, { access_token: 'bob-token', user: bob }))
  const view = mount(); await screen.findByText('Alice')
  let result!: Promise<unknown>
  act(() => { result = auth.updateUsername('Renamed').catch(error => error) })
  await act(async () => { await auth.login(bob.email, 'password') })
  await act(async () => { rename.resolve(response(200, { user: { ...alice, username: 'Renamed' } })); await result })
  expect(screen.getByText('Bob')).toBeInTheDocument()
  view.unmount()
  fetchMock.mockReturnValueOnce(verification.promise)
  const next = mount(); next.unmount()
  await act(async () => { verification.resolve(response(401)) })
  expect(localStorage.getItem('auth_token')).toBe('bob-token')
})
