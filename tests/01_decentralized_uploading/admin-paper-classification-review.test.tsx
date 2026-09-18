import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AdminPage from '../../frontend/src/pages/AdminPage'
import { api } from '../../frontend/src/lib/api'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'

const reviewer = vi.hoisted(() => ({ role: 'admin' }))

vi.mock('../../frontend/src/context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 7, username: 'reviewer', role: reviewer.role, is_admin: true, is_superadmin: reviewer.role === 'superadmin' },
    replaceUser: vi.fn(),
  }),
}))

vi.mock('../../frontend/src/lib/api', () => ({
  api: {
    get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), download: vi.fn(),
  },
}))

vi.mock('../../frontend/src/lib/classifications', async importOriginal => {
  const original = await importOriginal<typeof import('../../frontend/src/lib/classifications')>()
  const catalogs = {
    material_families: [
      { id: 1, name: '氢基超导体', aliases: ['hydride', '高压氢化物'] },
      { id: 7, name: '重费米子超导体', aliases: ['heavy fermion'] },
    ],
    structure_families: [{ id: 2, name: '笼状结构', aliases: ['clathrate'] }],
    material_dimensionalities: [
      { value: 'three_dimensional' as const, name: '三维' },
      { value: 'unknown' as const, name: '未知' },
    ],
  }
  return {
    ...original,
    loadClassificationCatalogs: vi.fn(async () => catalogs),
    refreshClassificationCatalogs: vi.fn(async () => catalogs),
  }
})

vi.mock('../../frontend/src/components/ChartGroupEditor', () => ({ default: () => null }))
vi.mock('../../frontend/src/components/NewsManager', () => ({ default: () => null }))
vi.mock('../../frontend/src/components/SuperAdminGovernance', () => ({ default: () => null }))
vi.mock('../../frontend/src/components/UsernameField', () => ({ default: () => null }))

const mockedApi = vi.mocked(api)

beforeEach(() => {
  reviewer.role = 'admin'
  mockedApi.get.mockImplementation(async (path: string) => {
    if (path.startsWith('/api/admin/papers/all')) {
      return {
        items: [{
          id: 51, doi: '10.1000/issue51', title: 'Hydride paper', authors: [], journal: 'Test',
          year: 2026, review_status: 'pending', review_comment: null, reviewer_name: null,
          uploader_name: 'author', created_at: '2026-08-25',
          show_in_chart: true, compound_symbols: 'LaH10', article_types: [],
        }],
        total: 1,
      } as never
    }
    if (path === '/api/admin/papers/51') {
      return {
        id: 51,
        review_status: 'pending',
        material_families: [{ id: 1, name: '氢基超导体', status: 'confirmed' }],
        material_states: [{
          id: 501,
          superconductor: { chemical_formula: 'LaH10' },
          element_count: 2,
          material_dimensionality: 'three_dimensional',
          structure_families: [],
        }],
      } as never
    }
    if (path === '/api/admin/papers/51/history') {
      return {
        paper_id: 51,
        events: [
          {
            id: 1, event_type: 'uploaded', paper_revision: 1,
            actor: { username: 'author', unknown: false }, occurred_at: '2026-09-04T09:00:00Z', review: null,
          },
          {
            id: 2, event_type: 'reviewed', paper_revision: 1,
            actor: { username: 'reviewer', unknown: false }, occurred_at: '2026-09-04T10:00:00Z',
            review: { status: 'approved', comment: '证据充分' },
          },
        ],
      } as never
    }
    if (path === '/api/rag/papers/51/review-artifact') {
      return {
        data: {
          ai_values: {
            paper: {
              title: 'Hydride paper', research_motivation: '论文明确称为 hydride',
              material_families: [{ id: 1, name: '氢基超导体', status: 'confirmed' }],
            },
            material_states: [{
              material: 'LaH10',
              structure_families: [],
              material_dimensionality: 'three_dimensional',
            }],
          },
          user_values: {
            paper: {
              title: 'Hydride paper',
              material_families: [{ id: 1, name: '氢基超导体', status: 'confirmed' }],
            },
            material_states: [{
              material: 'LaH10',
              structure_families: [],
              material_dimensionality: 'three_dimensional',
            }],
          },
          evidence: {
            classification_scope: [
              { raw_name: 'LaH10', scope: 'current_paper' },
              { raw_name: 'H3S', scope: 'referenced_work' },
            ],
          },
        },
      } as never
    }
    if (path === '/api/rag/papers/51/candidate-attachments') return { data: [] } as never
    throw new Error(`unexpected GET ${path}`)
  })
  mockedApi.post.mockImplementation(async path => path === '/api/rag/evidence/proposals/prepare' ? {patches:[]} as never : path === '/api/rag/evidence/preflight'
    ? { version: 'checked-version', needs_check: false, records: [], sources: [] } as never
    : { message: '审核完成' } as never)
})

afterEach(() => {
  cleanup()
  localStorage.removeItem('sc-wiki.language')
  vi.clearAllMocks()
})

describe('论文快速审核三状态', () => {
  const openApproval = async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><AdminPage /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '论文审核' }))
    await screen.findByText('Hydride paper')
    await user.click(screen.getByRole('button', { name: '审核' }))
    await user.click(screen.getByRole('combobox', { name: '审核结果' }))
    await user.click(screen.getByRole('option', { name: /通过/ }))
    return user
  }

  it('读取失败不发起批准，审核失败保留输入，提交中不能重复点击', async () => {
    const originalGet = mockedApi.get.getMockImplementation()!
    mockedApi.get.mockImplementation(async (path, ...args) => {
      if (path === '/api/rag/papers/51/review-artifact') throw Object.assign(new Error('读取服务失败'), { status: 500 })
      return originalGet(path, ...args)
    })
    const user = await openApproval()
    await user.type(screen.getByLabelText('审核意见'), '已核对')
    await user.click(screen.getByRole('button', { name: '确认审核' }))
    expect(await screen.findByText(/读取服务失败/)).toBeVisible()
    expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))).toHaveLength(0)
    expect(screen.getByLabelText('审核意见')).toHaveValue('已核对')
    mockedApi.get.mockImplementation(originalGet)
    let rejectRequest!: (reason: Error) => void
    mockedApi.post.mockImplementation(path => path === '/api/rag/evidence/proposals/prepare' ? {patches:[]} as never : path === '/api/rag/evidence/preflight'
      ? Promise.resolve({ version: 'checked-version', needs_check: false, records: [], sources: [] } as never)
      : new Promise((_, reject) => { rejectRequest = reject }))
    await user.click(screen.getByRole('button', { name: '确认审核' }))
    await waitFor(() => expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))).toHaveLength(1))
    expect(screen.getByRole('button', { name: '确认审核' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '取消' })).toBeDisabled()
    rejectRequest(new Error('物性记录缺少可解析 Evidence'))
    expect(await screen.findByText(/物性记录缺少可解析 Evidence/)).toBeVisible()
    expect(screen.getByLabelText('审核意见')).toHaveValue('已核对')
    expect(screen.getByRole('combobox', { name: '审核结果' })).toHaveTextContent('通过')
  })

  it('同版本旧快照不能覆盖已保存分类或按位置串换材料状态', async () => {
    const originalGet = mockedApi.get.getMockImplementation()!
    mockedApi.get.mockImplementation(async (path, ...args) => {
      if (path === '/api/admin/papers/51') return {
        id: 51, content_revision: 1, review_status: 'pending', superconductor_kind: 'unconventional',
        material_families: [{ id: 7, name: '已保存家族' }],
        material_states: [{ id: 502, material_dimensionality: 'two_dimensional', structure_families: [] }],
      }
      if (path === '/api/rag/papers/51/review-artifact') return { data: { user_values: {
        paper: { superconductor_kind: 'conventional', material_families: [{ id: 1, name: '旧家族' }] },
        material_states: [{ id: 501, material_dimensionality: 'three_dimensional',
          structure_families: [{ id: 2, name: '旧结构', is_primary: true }] }],
      } } }
      return originalGet(path, ...args)
    })
    const user = await openApproval()
    await user.click(screen.getByRole('button', { name: '确认审核' }))
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/api/admin/papers/51/review', expect.objectContaining({
      superconductor_kind: 'unconventional', material_families: [{ id: 7, name: '已保存家族' }],
      material_states: [{ id: 502, material_dimensionality: 'two_dimensional', structure_families: [] }],
    })))
  })

  it.each(['approved', 'pending'])('正式分类可直接用于批准，缺少快照不阻断（%s）', async status => {
    const originalGet = mockedApi.get.getMockImplementation()!
    mockedApi.get.mockImplementation(async (path, ...args) => {
      if (path === '/api/admin/papers/51') return {
        id: 51, review_status: status, superconductor_kind: 'conventional',
        material_families: [{ id: 7, name_zh: '重费米子超导体' }],
        material_states: [{ id: 501, material_dimensionality: 'three_dimensional',
          structure_families: [{ structure_family_id: 2, structure_family: { name: '笼状结构' }, is_primary: true }] }],
      }
      if (path === '/api/rag/papers/51/review-artifact') throw Object.assign(new Error('没有快照'), { status: 404 })
      return originalGet(path, ...args)
    })
    const user = await openApproval()
    await user.click(screen.getByRole('button', { name: '确认审核' }))
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/api/admin/papers/51/review', expect.objectContaining({
      superconductor_kind: 'conventional', material_families: [{ id: 7, name: '重费米子超导体' }],
      material_states: [{ id: 501, material_dimensionality: 'three_dimensional', structure_families: [{ id: 2, name: '笼状结构', is_primary: true }] }],
    })))
    if (status === 'approved') expect(mockedApi.get.mock.calls.some(([path]) => String(path).includes('review-artifact'))).toBe(false)
  })

  it.each([false, true])('首次快速批准先保存家族，保存失败不发审核请求（失败=%s）', async fail => {
    const originalGet = mockedApi.get.getMockImplementation()!
    let saved = false
    mockedApi.get.mockImplementation(async (path, ...args) => {
      if (path === '/api/admin/papers/51') return {
        id: 51, paper_type: 'review', review_status: 'pending', superconductor_kind: 'unknown',
        material_families: saved ? [{ id: 21, name: '新家族' }] : [], material_states: [],
      }
      if (path === '/api/rag/papers/51/review-artifact') return { data: { user_values: {
        paper: { material_families: [{ name: '新家族', status: 'pending' }] }, material_states: [],
      } } }
      return originalGet(path, ...args)
    })
    mockedApi.put.mockImplementation(async (path, body: any) => {
      expect(path).toBe('/api/rag/papers/51/scientific-draft')
      expect(body.material_families[0].name).toBe('新家族')
      if (fail) throw new Error('目录保存失败')
      saved = true
      return { ok: true, data: {} }
    })
    const user = await openApproval()
    await user.click(screen.getByRole('button', { name: '确认审核' }))
    if (fail) {
      expect(await screen.findByText(/目录保存失败/)).toBeVisible()
      expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))).toHaveLength(0)
    } else {
      await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/api/admin/papers/51/review', expect.objectContaining({
        material_families: [{ id: 21, name: '新家族' }],
      })))
      const reviewIndex = mockedApi.post.mock.calls.findIndex(([path]) => path.endsWith('/review'))
      expect(mockedApi.put.mock.invocationCallOrder[0]).toBeLessThan(mockedApi.post.mock.invocationCallOrder[reviewIndex])
    }
  })

  it.each([
    ['admin', 'zh'], ['superadmin', 'zh'], ['admin', 'en'], ['superadmin', 'en'],
  ] as const)('%s 工作台提供三个状态并携带已保存分类批准（%s）', async (mode, lang) => {
    reviewer.role = mode
    localStorage.setItem('sc-wiki.language', lang)
    const user = userEvent.setup()
    render(<LanguageProvider><MemoryRouter><AdminPage mode={mode} /></MemoryRouter></LanguageProvider>)
    await user.click(screen.getByRole('button', { name: lang === 'zh' ? '论文审核' : 'Paper Review' }))
    await screen.findByText('Hydride paper')
    await user.click(screen.getByRole('button', { name: lang === 'zh' ? '审核' : 'Review' }))
    await user.click(screen.getByRole('combobox', { name: lang === 'zh' ? '审核结果' : 'Review Result' }))
    expect(screen.getAllByRole('option').map(option => option.getAttribute('data-value'))).toEqual(['approved', 'pending', 'rejected'])
    await user.click(screen.getAllByRole('option')[0])
    await user.click(screen.getByRole('button', { name: lang === 'zh' ? '确认审核' : 'Confirm Review' }))
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/api/admin/papers/51/review', expect.objectContaining({
      status: 'approved', superconductor_kind: 'unknown',
      material_families: [{ id: 1, name: '氢基超导体' }],
      material_states: [{ id: 501, material_dimensionality: 'three_dimensional', structure_families: [] }],
    })))
    expect(mockedApi.put).not.toHaveBeenCalled()
  })

  it.each(['zh', 'en'])('历史名称覆盖审核、修改、未知上传者和空意见（%s）', async lang => {
    localStorage.setItem('sc-wiki.language', lang)
    const originalGet = mockedApi.get.getMockImplementation()!
    const longComment = '已核对证据'.repeat(50)
    mockedApi.get.mockImplementation(async (path, ...args) => {
      if (path !== '/api/admin/papers/51/history') return originalGet(path, ...args)
      return {
        paper_id: 51,
        events: [
          { id: 1, event_type: 'uploaded', paper_revision: 1, actor: { username: null, unknown: true }, occurred_at: '2026-09-04T09:05:00', review: null },
          { id: 2, event_type: 'modified', paper_revision: 2, actor: { username: 'editor', unknown: false }, occurred_at: '2026-09-04T10:06:00', review: null },
          { id: 3, event_type: 'reviewed', paper_revision: 2, actor: { username: 'reviewer', unknown: false }, occurred_at: '2026-09-04T11:07:00', review: { status: 'approved', comment: `  证据充分\n\t${longComment}  ` } },
          { id: 4, event_type: 'reviewed', paper_revision: 2, actor: { username: null, unknown: false }, occurred_at: 'invalid', review: { status: 'pending', comment: ' \n ' } },
        ],
      } as never
    })
    const user = userEvent.setup()
    render(<LanguageProvider><MemoryRouter><AdminPage /></MemoryRouter></LanguageProvider>)
    await user.click(screen.getByRole('button', { name: lang === 'zh' ? '论文审核' : 'Paper Review' }))
    await screen.findByText('Hydride paper')
    await user.click(screen.getByRole('button', { name: lang === 'zh' ? '历史' : 'History' }))
    const upload = lang === 'zh' ? '历史导入，上传者未知-上传' : 'Imported history, uploader unknown-Uploaded'
    expect(await screen.findByText(`2026-09-04-09-05-v1-${upload}`)).toBeVisible()
    expect(screen.getByText(`2026-09-04-10-06-v2-editor-${lang === 'zh' ? '修改' : 'Modified'}`)).toBeVisible()
    const reviewName = screen.getByText(`2026-09-04-11-07-v2-reviewer-证据充分 ${longComment}`)
    expect(reviewName).toBeVisible()
    expect(reviewName).toHaveStyle({ overflowWrap: 'anywhere' })
    expect(screen.getByText(`${lang === 'zh' ? '已通过' : 'Approved'} · 证据充分 ${longComment}`)).toBeVisible()
    expect(screen.getByText(lang === 'zh'
      ? '时间未知-v2-未知审核人-未填写审核意见'
      : 'Unknown time-v2-Unknown reviewer-No review comment provided')).toBeVisible()
  })

  it('在操作区域显示上传者和历史入口，不显示物性记录列', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><AdminPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: '论文审核' }))
    expect(await screen.findByText('Hydride paper')).toBeVisible()
    expect(screen.queryByRole('columnheader', { name: '上传者' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: '记录' })).not.toBeInTheDocument()
    const uploaderLink = screen.getByRole('link', { name: 'author' })
    expect(uploaderLink).toBeVisible()
    expect(uploaderLink).toHaveAttribute('href', '/users/author')

    await user.click(screen.getByRole('button', { name: '历史' }))
    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledWith('/api/admin/papers/51/history'))
    const historyDialog = await screen.findByRole('dialog')
    expect(historyDialog).toHaveTextContent('上传')
    expect(historyDialog).toHaveTextContent('审核')
    expect(historyDialog).toHaveTextContent('已通过 · 证据充分')
  })

  it('保留简洁弹窗，选择退回时只提交结果和审核意见', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><AdminPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: '论文审核' }))
    expect(await screen.findByText('Hydride paper')).toBeVisible()
    expect(screen.queryByRole('tab', { name: '分类建议' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '分类目录' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '审核' }))

    expect(screen.queryByText('确认材料状态分类')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'LaH10 的材料家族' })).not.toBeInTheDocument()

    fireEvent.mouseDown(screen.getByRole('combobox', { name: '审核结果' }))
    expect(screen.getByRole('option', { name: /通过/ })).toBeVisible()
    await user.click(await screen.findByRole('option', { name: /退回待审核/ }))
    await user.click(screen.getByRole('button', { name: '确认审核' }))

    await waitFor(() => expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))).toHaveLength(1))
    const [path, body] = mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))[0]
    expect(path).toBe('/api/admin/papers/51/review')
    expect(body).toMatchObject({
      status: 'pending',
      comment: '',
    })
    expect(mockedApi.put).not.toHaveBeenCalled()
  })

  it.each(['pending', 'rejected'])('非批准审核不触发详情或审核产物加载（%s）', async status => {
    const user = userEvent.setup()
    render(<MemoryRouter><AdminPage /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '论文审核' }))
    expect(await screen.findByText('Hydride paper')).toBeVisible()
    await user.click(screen.getByRole('button', { name: '审核' }))

    fireEvent.mouseDown(screen.getByRole('combobox', { name: '审核结果' }))
    await user.click(await screen.findByRole('option', { name: status === 'pending' ? /退回待审核/ : /拒绝/ }))
    await user.click(screen.getByRole('button', { name: '确认审核' }))

    await waitFor(() => expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))).toHaveLength(1))
    expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))[0][1]).toMatchObject({ status })
    expect(mockedApi.post.mock.calls.filter(([path]) => path.endsWith('/review'))[0][1]).not.toHaveProperty('material_families')
    expect(mockedApi.get.mock.calls.some(([path]) => String(path).includes('/review-artifact'))).toBe(false)
    expect(mockedApi.get.mock.calls.some(([path]) => String(path).includes('/api/admin/papers/51'))).toBe(false)
  })
})
