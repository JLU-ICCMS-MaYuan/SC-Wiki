import React from 'react'
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AccountPage from '../../frontend/src/pages/AccountPage'
import AccountSecurity from '../../frontend/src/components/AccountSecurity'
import SuperAdminGovernance from '../../frontend/src/components/SuperAdminGovernance'
import { api } from '../../frontend/src/lib/api'

const auth = vi.hoisted(() => ({ user: { id: 7, email: 'owner@example.test', username: 'owner', role: 'user' }, replaceUser: vi.fn(), updateUsername: vi.fn(), logout: vi.fn() }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() } }))
vi.mock('../../frontend/src/pages/AdminPage', () => ({ default: () => <div data-testid="review-workspace" /> }))
const mocked = vi.mocked(api)
const profile = { ...auth.user, real_name: '研究者', affiliation: '测试机构', orcid: '', research_interests: ['超导'], is_email_verified: true, username_change_allowed: false, account_status: 'active' }
const show = (element: React.ReactElement) => render(<MemoryRouter>{element}</MemoryRouter>)
beforeEach(() => {
  vi.clearAllMocks(); auth.user.role = 'user'
  mocked.get.mockImplementation(async (url: string) => (url === '/api/account/profile' ? { ...profile, role: auth.user.role } : url.includes('papers') || url.includes('my-uploads') ? { items: [], total: 0 } : []) as never)
})
afterEach(cleanup)

describe('正式用户中心', () => {
  it.each([null, undefined, []])('研究方向为 %j 时可展示、取消编辑及保存', async interests => {
    const emptyProfile = { ...profile, research_interests: interests }
    mocked.get.mockImplementation(async (url: string) => (url === '/api/account/profile' ? emptyProfile : url.includes('papers') ? { items: [], total: 0 } : []) as never)
    mocked.patch.mockResolvedValue(emptyProfile)
    show(<AccountPage />)
    await screen.findByRole('button', { name: '修改资料' })
    expect(screen.getAllByText('暂未填写').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: '修改资料' }))
    expect(screen.getByLabelText('研究方向')).toHaveValue('')
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    fireEvent.click(screen.getByRole('button', { name: '修改资料' }))
    fireEvent.click(screen.getByRole('button', { name: '保存资料' }))
    await screen.findByText('个人资料已保存')
    expect(mocked.patch).toHaveBeenCalledWith('/api/account/profile', expect.objectContaining({ research_interests: [] }))
    expect(screen.getByRole('button', { name: '修改资料' })).toBeInTheDocument()
  })
  it('默认只读，取消还原，保存失败保留输入，成功后回到只读', async () => {
    show(<AccountPage />)
    await screen.findByText('测试机构')
    expect(screen.queryByRole('textbox', { name: '真实姓名' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '修改资料' }))
    fireEvent.change(screen.getByLabelText('真实姓名'), { target: { value: '临时名字' } })
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(screen.queryByText('临时名字')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '修改资料' }))
    fireEvent.change(screen.getByLabelText('所属机构'), { target: { value: '新机构' } })
    mocked.patch.mockRejectedValueOnce(new Error('保存失败'))
    fireEvent.click(screen.getByRole('button', { name: '保存资料' }))
    await screen.findByText('保存失败'); expect(screen.getByLabelText('所属机构')).toHaveValue('新机构')
    mocked.patch.mockResolvedValueOnce({ ...profile, affiliation: '新机构' })
    fireEvent.click(screen.getByRole('button', { name: '保存资料' }))
    await screen.findByText('个人资料已保存')
    expect(screen.queryByLabelText('所属机构')).not.toBeInTheDocument()
    expect(screen.getByText('新机构')).toBeInTheDocument()
  })
  it('管理员有本人检查贡献和复用待检查入口，超级管理员入口直达新标签页', async () => {
    auth.user.role = 'superadmin'; show(<AccountPage />)
    await screen.findByText('他帮助检查的 SC-Wiki 收录的论文')
    await waitFor(() => expect(mocked.get).toHaveBeenCalledWith('/api/account/reviewed-papers'))
    fireEvent.click(screen.getByRole('tab', { name: '待检查' }))
    expect(screen.getByTestId('review-workspace')).toBeInTheDocument()
    for (const section of ['users', 'applications', 'charts', 'news', 'models', 'audit']) {
      const link = document.querySelector(`a[href="/superadmin?section=${section}"]`)
      expect(link).toHaveAttribute('target', '_blank'); expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    }
  })
  it('治理深链直接选择用户或审计分区', async () => {
    const view = show(<SuperAdminGovernance initialSection={1} />)
    await waitFor(() => expect(mocked.get).toHaveBeenCalledWith('/api/superadmin/users'))
    view.rerender(<MemoryRouter><SuperAdminGovernance initialSection={2} /></MemoryRouter>)
    await waitFor(() => expect(mocked.get).toHaveBeenCalledWith('/api/superadmin/audits/governance'))
  })
})

describe('正式邮箱验证改密', () => {
  const open = async () => { show(<AccountSecurity />); fireEvent.click(screen.getByRole('button', { name: /账户安全/ })); await screen.findByLabelText(/当前密码/) }
  const fillIdentity = () => {
    fireEvent.change(screen.getByLabelText(/当前密码/), { target: { value: 'OldPassword123!' } })
    fireEvent.change(screen.getByLabelText(/账户绑定邮箱/), { target: { value: 'owner@example.test' } })
  }
  it('身份验证失败不展示改密步骤，服务成功后才进入验证码输入', async () => {
    await open()
    expect(screen.getByRole('button', { name: '验证并发送验证码' })).toBeDisabled()
    fillIdentity(); mocked.post.mockRejectedValueOnce(new Error('旧密码或绑定邮箱不正确'))
    fireEvent.click(screen.getByRole('button', { name: '验证并发送验证码' }))
    await screen.findByText('旧密码或绑定邮箱不正确')
    expect(screen.queryByLabelText(/邮箱验证码/)).not.toBeInTheDocument()
    mocked.post.mockResolvedValueOnce({ resend_after_seconds: 60, expires_in_seconds: 300 })
    fireEvent.click(screen.getByRole('button', { name: '验证并发送验证码' }))
    await screen.findByLabelText(/邮箱验证码/)
    expect(mocked.post).toHaveBeenCalledWith('/api/account/password-change-code', { current_password: 'OldPassword123!', email: 'owner@example.test' })
    expect(screen.getByRole('button', { name: /秒后重发/ })).toBeDisabled()
  })
  it('验证码失败不退出，成功提交携带完整凭证且清除登录', async () => {
    await open(); fillIdentity()
    mocked.post.mockResolvedValueOnce({ resend_after_seconds: 60, expires_in_seconds: 300 })
    fireEvent.click(screen.getByRole('button', { name: '验证并发送验证码' }))
    fireEvent.change(await screen.findByLabelText(/邮箱验证码/), { target: { value: '123456' } })
    fireEvent.change(screen.getByLabelText(/^新密码/), { target: { value: 'NewPassword123!' } })
    fireEvent.change(screen.getByLabelText(/^确认新密码/), { target: { value: 'DifferentPassword!' } })
    fireEvent.click(screen.getByRole('button', { name: '验证并修改密码' }))
    await screen.findByText('两次输入的新密码不一致'); expect(mocked.post).toHaveBeenCalledTimes(1)
    fireEvent.change(screen.getByLabelText(/^确认新密码/), { target: { value: 'NewPassword123!' } })
    mocked.post.mockRejectedValueOnce(new Error('验证码无效或已过期'))
    fireEvent.click(screen.getByRole('button', { name: '验证并修改密码' }))
    await screen.findByText('验证码无效或已过期'); expect(auth.logout).not.toHaveBeenCalled()
    mocked.post.mockResolvedValueOnce(undefined)
    fireEvent.click(screen.getByRole('button', { name: '验证并修改密码' }))
    await waitFor(() => expect(auth.logout).toHaveBeenCalledTimes(1))
    expect(mocked.post).toHaveBeenLastCalledWith('/api/account/change-password', { current_password: 'OldPassword123!', email: 'owner@example.test', code: '123456', new_password: 'NewPassword123!' })
  })
})
