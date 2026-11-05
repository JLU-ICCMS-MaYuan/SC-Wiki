import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AccountReviews from '../../frontend/src/components/AccountReviews'
import MyPapersList from '../../frontend/src/components/MyPapersList'
import AdminPage from '../../frontend/src/pages/AdminPage'
import AdminWorkspacePage from '../../frontend/src/pages/AdminWorkspacePage'
import PaperTitle from '../../frontend/src/components/PaperTitle'
import PaperMaterialsSection from '../../frontend/src/components/PaperMaterialsSection'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => ({ user: { id: 7, role: 'superadmin', is_approved: true } }) }))
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() } }))
const mocked = vi.mocked(api)
const papers = Array.from({ length: 45 }, (_, n) => ({ id: n + 1, title: 'Paper ' + (n + 1), year: 2026, review_status: 'approved', workflow_status: 'pending' }))
beforeEach(() => {
  mocked.get.mockImplementation(async url => {
    const u = new URL(url, 'http://isolated.test')
    if (u.pathname.includes('papers')) {
      const offset = Number(u.searchParams.get('offset') || 0), limit = Number(u.searchParams.get('limit') || 20)
      return { items: papers.slice(offset, offset + limit), total: 45 } as never
    }
    return { items: [], records: [] } as never
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.restoreAllMocks() })
const host = (node: React.ReactNode, path = '/') => render(<LanguageProvider><MemoryRouter initialEntries={[path]}>{node}</MemoryRouter></LanguageProvider>)

it.each(['admin', 'superadmin'] as const)('%s 个人页两页签每页3篇，无内部滚动并承接页签', async role => {
  host(<AccountReviews role={role} />)
  await screen.findByText('Paper 3')
  expect(screen.queryByText('Paper 4')).not.toBeInTheDocument()
  expect(document.querySelector('[data-paper-list-scroll]')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }))
  await screen.findByText('Paper 4')
  expect(screen.getByRole('link', { name: '打开检查工作区' })).toHaveAttribute('href', '/' + role + '?section=papers&review_tab=history')
  fireEvent.click(screen.getByRole('tab', { name: '待检查' }))
  await screen.findByText('Paper 3')
  expect(screen.queryByText('Paper 4')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '打开检查工作区' })).toHaveAttribute('href', '/' + role + '?section=papers&review_tab=pending')
  expect(mocked.get.mock.calls.some(([url]) => url.includes('/admin/papers/all?limit=3&offset=0'))).toBe(true)
})

it.each(['history', 'pending'])('独立工作区承接%s页签，每页20篇并内部滚动', async tab => {
  host(<AdminWorkspacePage mode="superadmin" />, '/superadmin?section=papers&review_tab=' + tab)
  await screen.findByText('Paper 20')
  expect(screen.queryByText('Paper 21')).not.toBeInTheDocument()
  expect(screen.getByRole('tab', { name: tab === 'history' ? '已检查记录' : '待检查' })).toHaveAttribute('aria-selected', 'true')
  expect(document.querySelector('[data-paper-list-scroll="true"]')).not.toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }))
  await screen.findByText('Paper 21')
})

it('已检查列表展示当前状态，旧拒绝只在文章历史，不再提供待审筛选', async () => {
  mocked.get.mockResolvedValue({items:[{id:1208,title:'CaH6',review_status:'approved',workflow_status:'approved',checked_status:'rejected'}],total:1})
  host(<MyPapersList kind="reviews" />)
  await screen.findByText('CaH6')
  expect(screen.getByText('审核完成')).toBeInTheDocument()
  expect(screen.queryByText('已拒绝')).not.toBeInTheDocument()
  fireEvent.mouseDown(screen.getByRole('combobox',{name:'检查状态'}))
  expect(screen.queryByRole('option',{name:'待审核',exact:true})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('option',{name:'已拒绝',exact:true}))
  await waitFor(() => expect(mocked.get.mock.calls.some(([url])=>url.includes('review_status=rejected'))).toBe(true))
})

it('已批准稿从小锤子拒绝，不先领取已交出的工作稿', async () => {
  mocked.get.mockResolvedValue({ items: [{ ...papers[0], workflow_status: 'approved' }], total: 1 })
  mocked.post.mockResolvedValue({ ok: true })
  host(<AdminPage embedded />)
  fireEvent.click(await screen.findByRole('button', { name: '审核', exact: true }))
  await screen.findByText('拒绝后，原上传者可返修；新版批准前继续展示旧批准版。')
  expect(mocked.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '确认审核', exact: true }))
  await waitFor(() => expect(mocked.post).toHaveBeenCalledWith('/api/rag/evidence/review-commit', expect.objectContaining({ paper_id: 1, status: 'rejected' })))
})

it('标题仅实际截断时悬停显示完整题目', async () => {
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(600)
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(250)
  host(<PaperTitle title="Full paper title" />)
  fireEvent.mouseOver(screen.getByText('Full paper title'))
  expect(await screen.findByRole('tooltip')).toHaveTextContent('Full paper title')
})

it('大纲删除前项后按稳定身份定位，压力更新同步显示', () => {
  const a = { state_key: 'a', material: 'CaH6', reported_space_group_symbol: 'Im-3m', pressure_value_gpa: 0 }
  const b = { ...a, state_key: 'b', pressure_value_gpa: 150 }
  const view = (states: typeof a[]) => <LanguageProvider><div data-paper-detail>
    <PaperMaterialsSection states={states} />
    {states.map((state, index) => <div key={state.state_key} data-material-state-index={index} data-state-key={state.state_key} />)}
  </div></LanguageProvider>
  const { rerender } = render(view([a, b]))
  const original = document.querySelector('[data-state-key="b"]') as HTMLElement
  const scroll = vi.fn(); original.scrollIntoView = scroll
  rerender(view([{ ...b, pressure_value_gpa: 180 }]))
  fireEvent.click(screen.getByRole('button', { name: '#1 · Im-3m · CaH₆ · 180 GPa', exact: true }))
  expect(document.querySelector('[data-state-key="b"]')).toBe(original)
  expect(scroll).toHaveBeenCalledTimes(1)
  expect(screen.queryByText(/150 GPa/)).not.toBeInTheDocument()
})
