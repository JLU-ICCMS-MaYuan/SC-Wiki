import '@testing-library/jest-dom/vitest'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SearchPage from '../../frontend/src/pages/SearchPage'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../../frontend/src/components/StructureViewer3D', () => ({
  default: ({ data }: { data: string }) => <div data-testid="structure-viewer">{data}</div>,
}))

const row = {
  record_id: 'tc-hg', paper_id: 9, formula: 'Hg', year: 1911, type: 'experimental',
  pressure: '0 GPa', tc: '4.2 K', space_group: 'R-3m', source: 'Local',
  status: 'Approved', doi: '10.1000/mercury',
}
const renderAt = (path: string) =>
  render(<MemoryRouter initialEntries={[path]}><SearchPage /></MemoryRouter>)

beforeEach(() => {
  vi.mocked(api.post).mockReset().mockResolvedValue({ items: [row], total: 1 })
  vi.mocked(api.get).mockReset().mockResolvedValue({
    id: 9, title: 'Mercury superconductivity', year: 1911, doi: row.doi,
    material_states: [{ id: 1, material: 'Hg', structures: [{
      id: 1, structure_text: 'data_mercury', structure_format: 'cif',
    }] }],
  })
})
afterEach(cleanup)

describe('仅保留本地数据后的搜索回归', () => {
  it.each(['elements_combination_search', 'elements_exact_search', 'elements_contained_search'])(
    '%s 保持元素请求契约，页面不再显示外部来源入口', async (mode) => {
      renderAt(`/search?elements=Hg&mode=${mode}`)
      expect(await screen.findByText('4.2 K')).toBeInTheDocument()
      expect(api.post).toHaveBeenCalledWith('/api/papers/search/records', {
        elements: ['Hg'], mode, limit: 50, offset: 0,
      })
      expect(screen.queryByText(/Alexandria|HTSC-2025|全部来源/)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Local' })).not.toBeInTheDocument()
    },
  )

  it('化学式搜索继续使用本地接口', async () => {
    renderAt('/search')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hg' } })
    fireEvent.click(screen.getByRole('button', { name: '搜索', exact: true }))
    expect(await screen.findByText('4.2 K')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/api/papers/search/records', {
      elements: [], mode: 'formula_search', formula: 'Hg', limit: 50, offset: 0,
    })
  })

  it('筛选和服务端分页保留参数，结果行仍打开论文及结构', async () => {
    vi.mocked(api.post).mockResolvedValue({ items: [row], total: 51 })
    renderAt('/search?elements=Hg')
    await screen.findByText('4.2 K')
    fireEvent.change(screen.getByPlaceholderText('如 LaH10'), { target: { value: 'Hg' } })
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '4' } })
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/api/papers/search/records', {
      elements: ['Hg'], mode: 'elements_combination_search', keyword: 'Hg', tc_min: 4, limit: 50, offset: 0,
    }))
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/api/papers/search/records', {
      elements: ['Hg'], mode: 'elements_combination_search', keyword: 'Hg', tc_min: 4, limit: 50, offset: 50,
    }))
    expect(screen.getByText('第 2/2 页，共 51 条')).toBeInTheDocument()
    fireEvent.click(screen.getByText(row.doi))
    expect(await screen.findByText('Mercury superconductivity')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/papers/9')
    expect(screen.getByTestId('structure-viewer')).toHaveTextContent('data_mercury')
    fireEvent.click(screen.getByRole('button', { name: '返回结果表格' }))
    expect(await screen.findByText('4.2 K')).toBeInTheDocument()
  })

  it('请求失败后仍可重试并显示本地结果', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('暂时不可用'))
    renderAt('/search?elements=Hg')
    expect(await screen.findByText('暂时不可用')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('4.2 K')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledTimes(2)
  })

  it('筛选无匹配时可重置并恢复本地结果', async () => {
    renderAt('/search?elements=Hg')
    await screen.findByText('4.2 K')
    vi.mocked(api.post).mockResolvedValueOnce({ items: [], total: 0 })
    fireEvent.change(screen.getByPlaceholderText('如 LaH10'), { target: { value: '不存在的材料' } })
    expect(await screen.findByText('没有匹配记录')).toBeInTheDocument()
    expect(screen.queryByText('4.2 K')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重置筛选' }))
    expect(await screen.findByText('4.2 K')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('如 LaH10')).toHaveValue('')
    expect(api.post).toHaveBeenLastCalledWith('/api/papers/search/records', {
      elements: ['Hg'], mode: 'elements_combination_search', limit: 50, offset: 0,
    })
  })
})
