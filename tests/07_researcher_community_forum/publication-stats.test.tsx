import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import PublicationStats from '../../frontend/src/components/community/PublicationStats'
import SharePage from '../../frontend/src/pages/share'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))
const authState = vi.hoisted(() => ({ user: null as { id: number } | null }))
vi.mock('../../frontend/src/context/AuthContext', () => ({ useAuth: () => authState }))
vi.mock('../../frontend/src/components/StructureViewer3D', () => ({ default: () => null }))

const snapshot = {
  families: [
    { family_id: 1, name_zh: '铜基', name_en: 'Cuprate', paper_count: 4, unknown_year_count: 1,
      years: [{ year: 2020, paper_count: 2 }, { year: 2021, paper_count: 0 }, { year: 2022, paper_count: 1 }] },
    { family_id: 2, name_zh: '铁基', name_en: 'Iron-based', paper_count: 2, unknown_year_count: 0,
      years: [{ year: 2024, paper_count: 2 }] },
    { family_id: 3, name_zh: '自建家族', name_en: '', paper_count: 1, unknown_year_count: 1, years: [] },
    { family_id: 0, name_zh: '未分类', name_en: 'Unclassified', paper_count: 0, unknown_year_count: 0, years: [] },
  ],
  generated_at: '2026-09-24T00:00:00Z',
}

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  authState.user = null
  vi.mocked(api.get).mockResolvedValue(snapshot)
})
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('家族论文数量和年度图', () => {
  it('真实柱图支持展开、切换、补零、未知年份和两种收起方式', async () => {
    const user = userEvent.setup()
    render(<PublicationStats />)
    const copper = await screen.findByRole('button', { name: '铜基：4 篇' })
    expect(screen.queryByRole('region', { name: /年度发文量/ })).not.toBeInTheDocument()
    await user.click(copper)
    expect(copper).toHaveAttribute('aria-pressed', 'true')
    const annual = screen.getByRole('region', { name: '铜基 · 年度发文量' })
    expect(within(annual).getByText('年份未知：1 篇')).toBeInTheDocument()
    expect(within(annual).getByLabelText('2021：0 篇')).toBeInTheDocument()
    expect(within(annual).getByLabelText('2020：2 篇')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '铁基：2 篇' }))
    expect(screen.getByRole('region', { name: '铁基 · 年度发文量' })).toBeInTheDocument()
    expect(screen.queryByText('2021')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '铁基：2 篇' }))
    expect(screen.queryByRole('region', { name: /年度发文量/ })).not.toBeInTheDocument()
    await user.click(copper)
    await user.click(screen.getByRole('button', { name: '收起年度图' }))
    expect(copper).toHaveAttribute('aria-pressed', 'false')
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('零篇家族可用键盘选择，全部年份未知有明确提示', async () => {
    const user = userEvent.setup()
    render(<PublicationStats />)
    const empty = await screen.findByRole('button', { name: '未分类：0 篇' })
    empty.focus()
    await user.keyboard('{Enter}')
    expect(screen.getByText('该家族暂无已审核通过的论文')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '自建家族：1 篇' }))
    expect(screen.getByText('暂无有效发表年份')).toBeInTheDocument()
    expect(screen.getByText('年份未知：1 篇')).toBeInTheDocument()
  })

  it('首次加载、全空数据及首次失败重试不伪造计数', async () => {
    let reject!: (reason: Error) => void
    vi.mocked(api.get).mockReturnValueOnce(new Promise((_, fail) => { reject = fail }))
    render(<PublicationStats />)
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    await act(async () => { reject(new Error('offline')) })
    expect(screen.getByRole('alert')).toHaveTextContent('论文统计加载失败')
    expect(screen.queryByText('暂无已审核通过的论文')).not.toBeInTheDocument()
    vi.mocked(api.get).mockResolvedValueOnce({ ...snapshot, families: snapshot.families.map(f => ({ ...f, paper_count: 0, unknown_year_count: 0, years: [] })) })
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('暂无已审核通过的论文')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '铜基：0 篇' })).toBeInTheDocument()
  })

  it('刷新失败保留快照与选中家族，重试同时更新总量及年度', async () => {
    const user = userEvent.setup()
    render(<PublicationStats />)
    await user.click(await screen.findByRole('button', { name: '铜基：4 篇' }))
    vi.mocked(api.get).mockRejectedValueOnce(new Error('offline'))
    await user.click(screen.getByRole('button', { name: '刷新论文统计' }))
    expect(screen.getByRole('alert')).toHaveTextContent('论文统计加载失败')
    expect(screen.getByRole('button', { name: '铜基：4 篇' })).toHaveAttribute('aria-pressed', 'true')
    const next = { ...snapshot, families: [{ ...snapshot.families[0], paper_count: 5, years: [{ year: 2020, paper_count: 4 }] }] }
    vi.mocked(api.get).mockResolvedValueOnce(next)
    await user.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByRole('button', { name: '铜基：5 篇' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('2020：4 篇')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(api.get).toHaveBeenLastCalledWith('/api/community/publication-stats?refresh=true')
  })

  it('每小时刷新完整快照且卸载清理定时器', async () => {
    vi.useFakeTimers()
    const view = render(<PublicationStats />)
    await act(async () => {})
    expect(api.get).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(60 * 60 * 1000) })
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenLastCalledWith('/api/community/publication-stats')
    view.unmount()
    await vi.advanceTimersByTimeAsync(60 * 60 * 1000)
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('旧请求晚返回不会覆盖手动刷新结果', async () => {
    let resolveOld!: (value: typeof snapshot) => void
    vi.mocked(api.get).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
    const view = render(<PublicationStats refreshToken={0} />)
    view.rerender(<PublicationStats refreshToken={1} />)
    await screen.findByRole('button', { name: '铜基：4 篇' })
    await act(async () => { resolveOld({ ...snapshot, families: [] }) })
    expect(screen.getByRole('button', { name: '铜基：4 篇' })).toBeInTheDocument()
  })

  it('英文使用规范名，用户自建家族英文缺失回退中文', async () => {
    localStorage.setItem('sc-wiki.language', 'en')
    render(<LanguageProvider><PublicationStats /></LanguageProvider>)
    expect(await screen.findByRole('button', { name: 'Cuprate: 4 papers' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '自建家族: 1 papers' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Unclassified: 0 papers' })).toBeInTheDocument()
  })

  it.each([false, true])('排行榜保留贡献榜及登录身份（登录=%s），现有刷新按钮同时刷新论文统计', async loggedIn => {
    authState.user = loggedIn ? { id: 7 } : null
    vi.mocked(api.get).mockImplementation(async url => {
      if (url.startsWith('/api/community/publication-stats')) return snapshot
      if (url.startsWith('/api/community/contributions')) return {
        participant_count: 25, upload_leaderboard: [], review_leaderboard: [], generated_at: snapshot.generated_at,
        current_user: { upload: { rank: 25, contribution_count: 1 }, review: null },
      }
      if (url === '/api/classification-catalogs') return { material_families: [] }
      throw new Error(`Unexpected API: ${url}`)
    })
    render(<MemoryRouter><SharePage section="rankings" /></MemoryRouter>)
    await screen.findByRole('button', { name: '铜基：4 篇' })
    expect(screen.getByText('贡献上传榜 Top 20')).toBeInTheDocument()
    expect(screen.getByText('贡献审核榜 Top 20')).toBeInTheDocument()
    if (loggedIn) {
      expect(screen.getByTestId('current-user-ranking')).toHaveTextContent('第 25 名 · 1 篇')
    } else {
      expect(screen.queryByTestId('current-user-ranking')).not.toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: '刷新榜单' }))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/community/publication-stats?refresh=true'))
    expect(api.get).toHaveBeenCalledWith('/api/community/contributions?refresh=true')
  })
})
