import '@testing-library/jest-dom/vitest'
import React, { useEffect, useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AppShell from '../../frontend/src/components/AppShell'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import type { User } from '../../frontend/src/context/AuthContext'
import { api } from '../../frontend/src/lib/api'

let currentUser: Pick<User, 'role' | 'username' | 'avatar_url'> | null = null
const logout = vi.fn(() => { currentUser = null })
const mounted = vi.fn()

vi.mock('../../frontend/src/context/AuthContext', () => ({
  useAuth: () => ({ user: currentUser, loading: false, logout }),
}))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

function DraftPage() {
  const [draft, setDraft] = useState('')
  const location = useLocation()
  useEffect(() => { mounted() }, [])
  return <>
    <output aria-label="当前地址">{location.pathname}</output>
    <input aria-label="未保存内容" value={draft} onChange={event => setDraft(event.target.value)} />
    <input aria-label="未上传文件" type="file" />
  </>
}

function renderShell(path = '/news') {
  return render(<MemoryRouter initialEntries={[path]}><LanguageProvider><Routes>
    <Route element={<AppShell />}>
      <Route path="/" element={<Navigate to="/news" replace />} />
      <Route path="*" element={<DraftPage />} />
    </Route>
  </Routes></LanguageProvider></MemoryRouter>)
}

beforeEach(() => {
  localStorage.clear()
  currentUser = null
  vi.mocked(api.get).mockResolvedValue({ data: { provider_name: 'OpenAI', model: 'server-model', source: 'server' } })
})
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks() })

describe('全角色统一侧栏', () => {
  it('全部全局入口位于侧栏，业务顺序固定，品牌回到默认热点页', async () => {
    const user = userEvent.setup()
    renderShell('/search')
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    const labels = within(nav).getAllByRole('button').map(button => button.getAttribute('aria-label'))
    expect(labels).toEqual([
      'SC-Wiki · 返回首页', '收起侧栏', '热点', '探索', '脉络', '社区', '上传', '对话', '预测',
      '配置 AI 供应商', '切换为简体中文', '切换为英文', '登录',
    ])
    await user.click(within(nav).getByRole('button', { name: 'SC-Wiki · 返回首页' }))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/news')
    expect(screen.getByRole('button', { name: '热点' })).toHaveAttribute('aria-current', 'page')
  })

  it('收起与展开保留正文挂载、未保存输入和本地文件，图标仍可导航', async () => {
    const user = userEvent.setup()
    renderShell('/upload')
    const input = screen.getByLabelText('未保存内容')
    const fileInput = screen.getByLabelText('未上传文件')
    const file = new File(['draft'], 'draft.pdf', { type: 'application/pdf' })
    await user.type(input, '尚未提交的内容')
    await user.upload(fileInput, file)
    const main = screen.getByRole('main')
    await user.click(screen.getByRole('button', { name: '收起侧栏' }))
    expect(screen.getByRole('button', { name: '展开侧栏' })).toHaveAttribute('aria-expanded', 'false')
    expect(main.parentElement).toHaveStyle({ gridTemplateColumns: '64px minmax(0, 1fr)' })
    expect(screen.getByLabelText('未保存内容')).toBe(input)
    expect(input).toHaveValue('尚未提交的内容')
    expect(fileInput).toHaveProperty('files', expect.objectContaining({ 0: file }))
    await user.click(screen.getByRole('button', { name: '展开侧栏' }))
    expect(main.parentElement).toHaveStyle({ gridTemplateColumns: '216px minmax(0, 1fr)' })
    expect(mounted).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: '收起侧栏' }))
    for (const [label, path] of [['热点', '/news'], ['探索', '/search'], ['脉络', '/knowledge'], ['上传', '/upload'], ['对话', '/rag'], ['预测', '/tc-predict']]) {
      await user.click(screen.getByRole('button', { name: label }))
      expect(screen.getByLabelText('当前地址')).toHaveTextContent(path)
      expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-current', 'page')
    }
    await user.click(screen.getByRole('button', { name: '社区' }))
    expect(screen.getByRole('menuitem', { name: '排行榜' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Tc~X 演变' })).toBeInTheDocument()
    await user.click(screen.getByRole('menuitem', { name: '讨论' }))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/share/discussions')
  })

  it.each([
    ['user', '用户', '/account'], ['admin', '管理员', '/admin'], ['superadmin', '超级管理员', '/superadmin'],
  ] as const)('%s 的角色入口、活动态和退出菜单在收起后仍可用', async (role, label, path) => {
    currentUser = { role, username: 'Researcher', avatar_url: null }
    const user = userEvent.setup()
    renderShell(path)
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-current', 'page')
    await user.click(screen.getByRole('button', { name: '收起侧栏' }))
    await user.click(screen.getByRole('button', { name: label }))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/account')
    await user.click(screen.getByRole('button', { name: '打开账户菜单' }))
    expect(screen.getAllByRole('menuitem')).toHaveLength(1)
    await user.click(screen.getByRole('menuitem', { name: '退出登录' }))
    expect(logout).toHaveBeenCalledOnce()
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/news')
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('收起时能切换中英文并保留表单，模型弹窗与登录注册可打开', async () => {
    const user = userEvent.setup()
    renderShell('/upload')
    fireEvent.change(screen.getByLabelText('未保存内容'), { target: { value: '保留' } })
    await user.click(screen.getByRole('button', { name: '收起侧栏' }))
    await user.click(screen.getByRole('button', { name: '界面语言' }))
    await user.click(screen.getByRole('menuitem', { name: '切换为英文' }))
    expect(localStorage.getItem('sc-wiki.language')).toBe('en')
    expect(screen.getByRole('button', { name: 'Upload' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByLabelText('未保存内容')).toHaveValue('保留')
    await user.click(screen.getByRole('button', { name: 'Interface language' }))
    await user.click(screen.getByRole('menuitem', { name: 'Switch to Simplified Chinese' }))
    await user.click(screen.getByRole('button', { name: '配置 AI 供应商' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('OpenAI · server-model')
    await user.click(screen.getByRole('button', { name: '取消' }))
    await user.click(await screen.findByRole('button', { name: '登录' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '注册' }))
    expect(screen.getByLabelText('真实姓名（选填，填写后公开）')).toBeInTheDocument()
  })

  it('键盘可以展开侧栏并聚焦、激活导航', async () => {
    const user = userEvent.setup()
    renderShell()
    screen.getByRole('button', { name: '收起侧栏' }).focus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('button', { name: '展开侧栏' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: '热点' })).toHaveFocus()
    await user.tab()
    await user.keyboard('{Enter}')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/search')
  })
})
