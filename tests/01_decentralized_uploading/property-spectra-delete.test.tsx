import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { PropertySpectraProvider, UnassignedPropertySpectra } from '../../frontend/src/components/PropertySpectra'
import { api } from '../../frontend/src/lib/api'
import type { PropertySpectrumListing } from '../../frontend/src/lib/propertySpectra'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), del: vi.fn() } }))
let listing: PropertySpectrumListing
beforeEach(() => {
  listing = { version: 'v1', jobs: [], can_edit: true, can_review: false, items: [
    { id: 'spectrum', version: 2, state_key: null, stale: true, source: { source_name: 'SI.pdf', pdf_page: 4 },
      run: { status: 'succeeded' }, review: {}, result: { curves: [], calibration: { curves: [{ kind: 'phonon_dos' }] } } },
    { id: 'attempt', version: 3, state_key: null, stale: true, source: { source_name: 'paper.pdf', pdf_page: 5 },
      run: { status: 'needs_review' }, review: {}, result: { curves: [], failures: ['HTTP 503'] } },
  ] }
  vi.mocked(api.get).mockImplementation(async () => structuredClone(listing) as never)
  vi.mocked(api.del).mockImplementation(async url => {
    listing.items = listing.items.filter(item => !url.includes(`/${item.id}?`))
    return structuredClone(listing) as never
  })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
function mount(readOnly = false, target: 'upload' | 'paper' | 'revision' = 'upload', save?: () => Promise<boolean>) {
  return render(<MemoryRouter><PropertySpectraProvider readOnly={readOnly} context={{ target: { target, target_id: 'task' }, beforeNavigate: save }}>
    <UnassignedPropertySpectra />
  </PropertySpectraProvider></MemoryRouter>)
}

it('两类均有删除入口，取消不写入，确认后更新计数且重新挂载不恢复', async () => {
  const view = mount()
  fireEvent.click(await screen.findByText('谱提取记录 · 1 条未生成曲线或标定'))
  expect(screen.getByRole('button', { name: '删除提取记录' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '删除谱数据' }))
  expect(screen.getByText(/不会随论文提交审核/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(api.del).not.toHaveBeenCalled()
  fireEvent.click(await screen.findByRole('button', { name: '删除谱数据' }))
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(screen.queryByText('待确认归属 · 1 组谱数据')).not.toBeInTheDocument())
  expect(api.del).toHaveBeenCalledWith('/api/rag/spectra/spectrum?target=upload&target_id=task&expected_version=v1&expected_collection_version=2')
  fireEvent.click(screen.getByRole('button', { name: '删除提取记录' }))
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(screen.queryByText('谱提取记录 · 1 条未生成曲线或标定')).not.toBeInTheDocument())
  view.unmount(); mount()
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(4))
  expect(screen.queryByRole('button', { name: /删除/ })).not.toBeInTheDocument()
})

it('版本冲突保留记录并显示具体错误', async () => {
  vi.mocked(api.del).mockRejectedValue(new Error('内容或谱版本已变化，请刷新后重试'))
  mount()
  fireEvent.click(await screen.findByRole('button', { name: '删除谱数据' }))
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('内容或谱版本已变化')
  expect(screen.getByText('待确认归属 · 1 组谱数据')).toBeInTheDocument()
})

it('保存失败不删除；保存成功后使用新目标版本', async () => {
  const save = vi.fn(async () => false)
  mount(false, 'revision', save)
  fireEvent.click(await screen.findByRole('button', { name: '删除谱数据' }))
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('主表单尚未保存')
  expect(api.del).not.toHaveBeenCalled()
  save.mockImplementation(async () => { listing.version = 'v2'; return true })
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(api.del).toHaveBeenCalledWith(expect.stringContaining('target=revision&target_id=task&expected_version=v2')))
})

it.each(['readonly', 'permission', 'paper', 'assigned'])('%s 不显示删除入口', async mode => {
  if (mode === 'permission') listing.can_edit = false
  if (mode === 'assigned') listing.items.forEach(item => { item.state_key = 's1' })
  mount(mode === 'readonly', mode === 'paper' ? 'paper' : 'upload')
  await waitFor(() => expect(api.get).toHaveBeenCalled())
  expect(screen.queryByRole('button', { name: /删除/ })).not.toBeInTheDocument()
})

it('自动提取进行中禁用删除入口', async () => {
  listing.jobs = [{ id: 'job', status: 'running' }]
  mount()
  expect(await screen.findByRole('button', { name: '删除谱数据' })).toBeDisabled()
})
