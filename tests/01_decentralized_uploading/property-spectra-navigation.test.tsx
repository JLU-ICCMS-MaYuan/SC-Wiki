import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PropertySpectraProvider, PropertySpectrumSection, PropertySpectrumState, MissingPropertySpectrumModules } from '../../frontend/src/components/PropertySpectra'
import SpectrumDetailPage from '../../frontend/src/pages/SpectrumDetailPage'
import { api } from '../../frontend/src/lib/api'
import { safeSpectrumReturn, type PropertySpectrumListing } from '../../frontend/src/lib/propertySpectra'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), download: vi.fn() } }))
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
  fireEvent.click(within(screen.getByRole('region', { name: '动力学' })).getByText('查看详情'))
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
  fireEvent.click(screen.getAllByText('查看详情')[0])
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
  expect(screen.queryByText('查看详情')).not.toBeInTheDocument()
})
it('无标量记录时谱仍出现于正确模块', async () => {
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><PropertySpectrumState stateKey="sample" summary="sample"><MissingPropertySpectrumModules existing={[]} /></PropertySpectrumState></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByText('动力学性质')).toBeInTheDocument()
  expect(screen.getByText('超导性质')).toBeInTheDocument()
  expect(screen.getAllByText('查看详情')).toHaveLength(2)
  const sections = document.querySelectorAll<HTMLDetailsElement>('[data-property-module-section]')
  expect([...sections].map(section => section.open)).toEqual([false, false])
  fireEvent.click(sections[0].querySelector('summary')!)
  const links = screen.getAllByText('查看详情')
  expect(links[0]).toBeVisible()
  expect(links[1]).not.toBeVisible()

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
