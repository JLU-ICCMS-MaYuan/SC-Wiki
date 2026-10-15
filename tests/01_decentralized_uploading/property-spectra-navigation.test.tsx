import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PropertySpectraProvider, PropertySpectrumSection, PropertySpectrumState, MissingPropertySpectrumModules, UnassignedPropertySpectra } from '../../frontend/src/components/PropertySpectra'
import SpectrumDetailPage from '../../frontend/src/pages/SpectrumDetailPage'
import { api } from '../../frontend/src/lib/api'
import { safeSpectrumReturn, spectrumGroups, type PropertySpectrumListing } from '../../frontend/src/lib/propertySpectra'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), download: vi.fn(), put: vi.fn() } }))
const point = { frequency_thz: 1, observed_amplitude: 2, reconstructed_amplitude: 2.2, status: 'observed', detection_mode: 'chromatic' }
const fixture = (): PropertySpectrumListing => ({ version: 'v1', jobs: [], can_edit: true, can_review: false, items: [{ id: 'collection', version: 2, state_key: 'sample', stale: false,
  source: { source_name: 'paper.pdf', pdf_page: 3 }, run: { id: 'run1', status: 'succeeded' }, review: { dos: { status: 'needs_review' }, a2f: { status: 'accepted' } },
  result: { curves: [{ id: 'dos', kind: 'phonon_dos', projection: 'total', unit: 'states/THz', points: [point, { ...point, frequency_thz: 2, observed_amplitude: null, status: 'interpolated' }] }, { id: 'a2f', kind: 'alpha2f', unit: '1', points: [point] }],
    candidates: { dos_normalization: { frequency_thz: [1, 2], components: { total: [3, 4] } }, joint: { frequency_thz: [1], alpha2f: [2.3] } }, quality: { curves: { dos: { observed_fraction: 0.5 } } } } }] })
let listing: PropertySpectrumListing
beforeEach(() => {
  listing = fixture()
  vi.mocked(api.get).mockImplementation(async path => path.includes('/draft') ? { data: { material_states: [{ state_key: 'sample', material: 'LaSc2H24', reported_space_group_symbol: 'P6/mmm', pressure_value_gpa: 150 }] } } as never : structuredClone(listing) as never)
  vi.mocked(api.download).mockResolvedValue(new Blob(['image']))
  vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:source'); static revokeObjectURL = vi.fn() })
})
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })
const address = (extra = '') => `/spectra/collection?target=upload&target_id=task&state_key=sample&curve=dos&collection_version=2&run=run1&return=%2Fupload${extra}`
function mountEdit(saveResult = true) {
  let saved = 'old'
  const save = vi.fn(async (value: string) => { if (saveResult) saved = value; return saveResult })
  function Editor() {
    const [value, setValue] = useState(saved)
    return <><input aria-label="主值" value={value} onChange={event => setValue(event.target.value)} />
      <PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' }, beforeNavigate: () => save(value) }}>
        <PropertySpectrumState stateKey="sample" summary="P6/mmm · LaSc₂H₂₄ · 150 GPa">
          <section aria-label="动力学"><PropertySpectrumSection moduleCode="dynamical_properties" /></section>
          <section aria-label="超导"><PropertySpectrumSection moduleCode="superconductive_properties" /></section>
        </PropertySpectrumState>
      </PropertySpectraProvider></>
  }
  render(<MemoryRouter initialEntries={['/upload']}><Routes><Route path="/upload" element={<Editor />} /><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  return save
}
it('混合集合按曲线归属，跳转前保存，独立详情使用正确曲线且返回保留已保存主值', async () => {
  const save = mountEdit()
  await screen.findByText(/声子 DOS/)
  expect(within(screen.getByRole('region', { name: '动力学' })).queryByText('α²F 谱函数')).not.toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: '超导' })).queryByText(/声子 DOS/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('主值'), { target: { value: 'saved change' } })
  fireEvent.click(within(screen.getByRole('region', { name: '动力学' })).getByRole('button', { name: '查看声子 DOS' }))
  expect(await screen.findByText('声子 DOS解析详情')).toBeInTheDocument()
  expect(save).toHaveBeenCalledWith('saved change')
  expect(screen.getByText('P6/mmm · LaSc₂H₂₄ · 150 GPa')).toBeInTheDocument()
  expect(screen.getByText('短缺口插值')).toBeInTheDocument()
  expect(within(screen.getAllByRole('table').at(-1)!).getAllByText('2.2')).toHaveLength(2)
  expect(screen.getByLabelText('谱候选')).toHaveTextContent('原始重建')
  await userEvent.click(screen.getByLabelText('谱候选'))
  await userEvent.click(screen.getByRole('option', { name: '共同尺度归一化候选' }))
  expect(within(screen.getAllByRole('table').at(-1)!).getByText('3')).toBeInTheDocument()
  expect(await screen.findByAltText('经权限校验读取的谱原图')).toHaveAttribute('src', 'blob:source')
  fireEvent.click(screen.getByText('返回原模块'))
  expect(await screen.findByLabelText('主值')).toHaveValue('saved change')
})
it('保存失败停留编辑页，保留当前输入且不展示详情', async () => {
  mountEdit(false)
  await screen.findByText(/声子 DOS/)
  fireEvent.change(screen.getByLabelText('主值'), { target: { value: 'not saved' } })
  fireEvent.click(screen.getByRole('button', { name: '查看声子 DOS' }))
  expect(await screen.findByText(/主表单尚未保存/)).toBeInTheDocument()
  expect(screen.getByLabelText('主值')).toHaveValue('not saved')
  expect(screen.queryByText('返回原模块')).not.toBeInTheDocument()
})
it.each(['state_key=other', 'collection_version=1', 'run=old'])('直接路由拒绝不匹配身份 %s', async replace => {
  const key = replace.split('=')[0]
  const url = address().replace(new RegExp(`${key}=[^&]*`), replace)
  render(<MemoryRouter initialEntries={[url]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/不可访问|版本已变化/))
  expect(api.download).not.toHaveBeenCalled()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('接口失败明确呈现，不能以示例曲线填充', async () => {
  vi.mocked(api.get).mockRejectedValue(new Error('谱服务尚未迁移'))
  mountEdit()
  expect((await screen.findAllByText(/谱服务尚未迁移/)).length).toBeGreaterThan(0)
  expect(screen.queryByRole('button', { name: '查看声子 DOS' })).not.toBeInTheDocument()
})
it('无标量记录时谱仍出现于正确模块', async () => {
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><PropertySpectrumState stateKey="sample" summary="sample"><MissingPropertySpectrumModules existing={[]} /></PropertySpectrumState></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByText('动力学性质')).toBeInTheDocument()
  expect(screen.getByText('超导性质')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '查看声子 DOS' })).toBeVisible()
  expect(screen.getByRole('button', { name: '查看 α²F' })).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()

})
it('返回地址只允许站内路径', () => {
  for (const value of ['https://evil.test', '//evil.test', '/\\evil.test', '/\nevil.test']) expect(safeSpectrumReturn(value)).toBe('/upload')
  expect(safeSpectrumReturn('/papers/12#material-state-sample')).toBe('/papers/12#material-state-sample')
})

it('独立详情可展开共用原图叠加、校对与逐谱审核', async () => {
  const raw = listing.items[0] as any
  raw.source.size_px = [160, 100]
  raw.result.curves = [Object.assign(raw.result.curves[0], {
    axis_calibration: { amplitude: { slope: -.01, intercept: 1 } },
    frequency_direction: 'x', clipped_frequencies_thz: [],
    points: [{ ...point, frequency_pixel: 20 }],
  })]
  raw.result.calibration = { panel_id: 'p', state_key: 'sample', curves: [] }
  listing.can_review = true
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await screen.findByText('声子 DOS解析详情')
  fireEvent.click(screen.getByText('原图叠加、标定校对与逐谱审核'))
  expect(await screen.findByText('修正标定并重提取')).toBeInTheDocument()
  expect(screen.getByLabelText('原图叠加提取曲线')).toBeChecked()
  expect(screen.getByText('保存本条谱审核')).toBeInTheDocument()
})

it('同状态的多个投影共用入口，累计 λ 与 α²F 同组，其他压力和集合不合并', async () => {
  const item = listing.items[0]
  item.result.curves.push({ ...item.result.curves[0], id: 'h-dos', projection: 'H' }, { ...item.result.curves[1], id: 'lambda', kind: 'cumulative_lambda' })
  listing.items.push({ ...structuredClone(item), id: 'other-pressure', state_key: 'other' })
  expect(spectrumGroups(listing.items, 'sample').map(group => group.curves.length)).toEqual([2, 2])
  mountEdit()
  expect(await screen.findByRole('button', { name: '查看声子 DOS' })).toBeVisible()
  expect(screen.getAllByRole('button', { name: '查看声子 DOS' })).toHaveLength(1)
  expect(screen.getAllByRole('button', { name: '查看 α²F' })).toHaveLength(1)
  expect(screen.getByText('2 条曲线')).toBeInTheDocument()
  expect(screen.getByText('含累计 λ')).toBeInTheDocument()
})

it('无该状态谱时显示禁用空态，不串用其他压力', async () => {
  listing.items[0].state_key = 'other'
  mountEdit()
  expect(await screen.findByRole('button', { name: '暂无声子 DOS' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂无 α²F' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '查看声子 DOS' })).not.toBeInTheDocument()
})

it('未归属空结果在独立详情显示失败和真实来源，不挂载假曲线', async () => {
  listing.items[0].state_key = null
  listing.items[0].result.curves = []
  listing.items[0].result.quality = { limitations: ['无法明确压力'] }
  const unassigned = '/spectra/collection?target=upload&target_id=task&state_key=unassigned&collection_version=2&run=run1&return=%2Fupload'
  render(<MemoryRouter initialEntries={[unassigned]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('这组谱尚未归属到当前材料状态')).toBeInTheDocument()
  expect(await screen.findByAltText('经权限校验读取的谱原图')).toBeInTheDocument()
  expect(screen.getByText(/无法明确压力/)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByRole('img', { name: /谱曲线/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '确认归属并重新计算' })).not.toBeInTheDocument()
})

it('未归属候选只显示摘要，点击才读取原图和点表', async () => {
  listing.items[0].state_key = null
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><UnassignedPropertySpectra /></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByRole('button', { name: '核对归属' })).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(api.download).not.toHaveBeenCalled()
})

it('归属确认复用原标定接口及双版本，保留标定并返回选择的状态', async () => {
  listing.items[0].state_key = null
  const calibration = { panel_id: 'p', state_key: null, curves: [{ id: 'dos', kind: 'phonon_dos', frequency_ticks: [[0, 1], [1, 2]] }] }
  listing.items[0].result.calibration = calibration
  vi.mocked(api.put).mockResolvedValue({ job_id: 'new-run' })
  render(<MemoryRouter initialEntries={[address().replace('state_key=sample', 'state_key=unassigned')]}><Routes>
    <Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /><Route path="/upload" element={<div>返回材料状态列表</div>} />
  </Routes></MemoryRouter>)
  const select = await screen.findByLabelText('选择归属材料状态')
  expect(screen.getByRole('button', { name: '确认归属并重新计算' })).toBeDisabled()
  await userEvent.click(select)
  await userEvent.click(screen.getByRole('option', { name: 'P6/mmm · LaSc₂H₂₄ · 150 GPa' }))
  await userEvent.click(screen.getByRole('button', { name: '确认归属并重新计算' }))
  expect(await screen.findByText('返回材料状态列表')).toBeInTheDocument()
  expect(api.put).toHaveBeenCalledWith('/api/rag/spectra/collection/calibration', {
    target: 'upload', target_id: 'task', expected_version: 'v1', expected_collection_version: 2,
    calibration: { ...calibration, state_key: 'sample' },
  })
  expect(calibration.state_key).toBeNull()
})

it('归属保存冲突不跳转且保留当前选择', async () => {
  listing.items[0].state_key = null
  listing.items[0].result.calibration = { panel_id: 'p', curves: [{ id: 'dos' }] }
  vi.mocked(api.put).mockRejectedValue(new Error('内容或谱版本已变化'))
  render(<MemoryRouter initialEntries={[address().replace('state_key=sample', 'state_key=unassigned')]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await userEvent.click(await screen.findByLabelText('选择归属材料状态'))
  await userEvent.click(screen.getByRole('option', { name: 'P6/mmm · LaSc₂H₂₄ · 150 GPa' }))
  await userEvent.click(screen.getByRole('button', { name: '确认归属并重新计算' }))
  expect(await screen.findByText('内容或谱版本已变化')).toBeInTheDocument()
  expect(screen.getByLabelText('选择归属材料状态')).toHaveTextContent('150 GPa')
})

it('只读谱不能提供归属写入按钮', async () => {
  listing.can_edit = false
  listing.items[0].state_key = null
  listing.items[0].result.calibration = { panel_id: 'p', curves: [{ id: 'dos' }] }
  render(<MemoryRouter initialEntries={[address().replace('state_key=sample', 'state_key=unassigned')]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('当前为只读查看，归属须由有编辑权限的用户确认。')).toBeInTheDocument()
  expect(screen.queryByLabelText('选择归属材料状态')).not.toBeInTheDocument()
  expect(api.put).not.toHaveBeenCalled()
})

it('重新计算尚无数值时仍按真实标定保留类型入口，不伪造曲线', async () => {
  listing.items[0].run.status = 'queued'
  listing.items[0].result.curves = []
  listing.items[0].result.calibration = { curves: [{ id: 'h', kind: 'phonon_dos' }, { id: 'a', kind: 'alpha2f' }] }
  mountEdit()
  expect(await screen.findByRole('button', { name: '查看声子 DOS' })).toBeVisible()
  expect(screen.getByRole('button', { name: '查看 α²F' })).toBeVisible()
  expect(screen.getAllByText('尚无数值曲线，可查看原图与提取状态。')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: '查看声子 DOS' }))
  expect(await screen.findByText('谱图候选 · 核对归属')).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('只有累计 λ 时入口如实标明，不冒充存在 α²F', async () => {
  listing.items[0].result.curves = [{ ...listing.items[0].result.curves[1], kind: 'cumulative_lambda' }]
  mountEdit()
  expect(await screen.findByRole('button', { name: '查看累计 λ' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '查看 α²F' })).not.toBeInTheDocument()
})
