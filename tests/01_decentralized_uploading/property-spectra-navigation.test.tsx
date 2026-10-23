import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PropertySpectraProvider, PropertySpectrumSection, PropertySpectrumState, MissingPropertySpectrumModules, UnassignedPropertySpectra } from '../../frontend/src/components/PropertySpectra'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import { emptyPropertyModule } from '../../frontend/src/lib/propertyModules'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import SpectrumDetailPage from '../../frontend/src/pages/SpectrumDetailPage'
import { api } from '../../frontend/src/lib/api'
import { safeSpectrumReturn, spectrumGroups, spectrumInterval, type PropertySpectrumListing } from '../../frontend/src/lib/propertySpectra'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), download: vi.fn(), put: vi.fn() } }))
const point = { frequency_thz: 1, observed_amplitude: 2, reconstructed_amplitude: 2.2, status: 'observed', detection_mode: 'chromatic' }
const fixture = (): PropertySpectrumListing => ({ version: 'v1', jobs: [], can_edit: true, can_review: false, items: [{ id: 'collection', version: 2, state_key: 'sample', stale: false,
  source: { source_name: 'paper.pdf', pdf_page: 3 }, run: { id: 'run1', status: 'succeeded' }, review: { dos: { status: 'needs_review' }, a2f: { status: 'accepted' } },
  result: { curves: [{ id: 'dos', kind: 'phonon_dos', projection: 'total', unit: 'states/THz', points: [point, { ...point, frequency_thz: 2, observed_amplitude: null, status: 'interpolated' }] }, { id: 'a2f', kind: 'alpha2f', unit: '1', points: [point] }],
    candidates: { dos_normalization: { frequency_thz: [1, 2], components: { total: [3, 4] } }, joint: { frequency_thz: [1], alpha2f: [2.3] } }, quality: { curves: { dos: { observed_fraction: 0.5 } } } } }] })
let listing: PropertySpectrumListing
beforeEach(() => {
  listing = fixture()
  vi.mocked(api.get).mockImplementation(async path => path.startsWith('/api/form-definitions') ? [] as never : path.includes('/draft') ? { data: { material_states: [{ state_key: 'sample', material: 'LaSc2H24', reported_space_group_symbol: 'P6/mmm', pressure_value_gpa: 150 }] } } as never : structuredClone(listing) as never)
  vi.mocked(api.download).mockResolvedValue(new Blob(['image']))
  vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:source'); static revokeObjectURL = vi.fn() })
})
afterEach(() => { cleanup(); clearFormDefinitionCache(); vi.clearAllMocks(); vi.unstubAllGlobals() })
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
it('新标签链接不保存主表单，保留未保存输入并携带谱身份', async () => {
  const save = mountEdit(false)
  await screen.findByRole('link', { name: '查看声子 DOS' })
  fireEvent.change(screen.getByLabelText('主值'), { target: { value: 'not saved' } })
  const link = screen.getByRole('link', { name: '查看声子 DOS' })
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  expect(link.getAttribute('href')).toContain('curve=dos')
  expect(link.getAttribute('href')).toContain('state_key=sample')
  expect(save).not.toHaveBeenCalled()
  expect(screen.getByLabelText('主值')).toHaveValue('not saved')
})
it('旧合并与新拆分只产生每类一个入口，旧集合保留历史且 α²F 不借累计零点', async () => {
  const old = listing.items[0]
  old.recorded_at = '2026-10-15T12:00:00'
  old.result.curves.push({ ...old.result.curves[1], id: 'lambda', kind: 'cumulative_lambda', points: [{ ...point, frequency_thz: 0, status: 'boundary_assumption' }] })
  listing.items.push({ ...structuredClone(old), id: 'new-alpha', recorded_at: '2026-10-15T13:00:00', result: { curves: old.result.curves.filter(c => c.kind !== 'phonon_dos') } })
  listing.items.push({ ...structuredClone(old), id: 'new-dos', recorded_at: '2026-10-15T13:00:00', result: { curves: old.result.curves.filter(c => c.kind === 'phonon_dos') } })
  const groups = spectrumGroups(listing.items, 'sample')
  expect(groups).toHaveLength(2)
  expect(groups.map(g => g.item.id)).toEqual(['new-dos', 'new-alpha'])
  expect(groups.every(g => g.history[0].id === old.id)).toBe(true)
  expect(spectrumInterval(groups[1].curves)).toBe('1–1 THz')
  mountEdit()
  await screen.findByRole('link', { name:'查看 α²F' })
  expect(screen.getAllByRole('link', { name:'查看 α²F' })).toHaveLength(1)
  expect(screen.getAllByRole('link', { name:'查看声子 DOS' })).toHaveLength(1)
})
it('DOS 比较展示未归一化积分的绝对与相对偏差，不给满足判断', async () => {
  listing.items[0].result.quality = { dos_mode_integral: { status:'available', primitive_atoms:27, target_modes:81, integral:80.245, absolute_difference:.755, relative_difference_pct:.932098765 } }
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await screen.findByText('80.245')
  expect(screen.getByText('0.755')).toBeInTheDocument()
  expect(screen.getByText('0.93%')).toBeInTheDocument()
  expect(screen.queryByText('核验结果')).not.toBeInTheDocument()
  expect(screen.queryByText('满足 3N')).not.toBeInTheDocument()
})
it('历史读取失败保留当前谱，成功后使用历史运行并禁止当前比较', async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, init) => {
    if (path.includes('/history?')) return { items: [{ id:'old-run', status:'succeeded', created_at:'2026-10-01', caption:'历史原始标定' }] } as never
    if (path.includes('/runs/old-run')) return { ...structuredClone(listing.items[0]), historical:true, stale:true, recorded_caption:'历史原始标定', run:{id:'old-run',status:'succeeded'} } as never
    return original(path, init)
  })
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await userEvent.click(await screen.findByRole('button', {name:'查看提取历史'}))
  await userEvent.click(await screen.findByRole('button', {name:/2026-10-01.*历史原始标定/}))
  expect(await screen.findByText('历史原始标定', {selector:'p'})).toBeInTheDocument()
  expect(screen.getByText('材料条件已变化或正在查看历史，当前 3N 对比不可用。')).toBeInTheDocument()
})
it('正式详情移除候选与重复审核，点表定高显示真实状态和绝对差', async () => {
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await screen.findByText('声子 DOS解析详情')
  expect(screen.getByRole('heading', { name: '02 · 原图与提取结果' })).toBeInTheDocument()
  expect(screen.queryByLabelText('谱候选')).not.toBeInTheDocument()
  expect(screen.queryByText('原图叠加、标定校对与逐谱审核')).not.toBeInTheDocument()
  expect(screen.getByText('短缺口插值')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: '可滚动的逐点数据表' })).toHaveStyle({ overflow: 'auto' })
  expect(within(screen.getAllByRole('table').at(-1)!).getByText('0.2')).toBeInTheDocument()
})
it('有歧义的彩边和多轨迹保留待核对状态，不展示插值伪值', async () => {
  listing.items[0].result.curves[0].points = [
    { ...point, observed_amplitude:null, reconstructed_amplitude:null, status:'missing', detection_mode:'ambiguous_components' },
    { ...point, frequency_thz:2, observed_amplitude:null, reconstructed_amplitude:null, status:'missing', detection_mode:'unsupported_chromatic' },
  ]
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('多条轨迹，待核对')).toBeInTheDocument()
  expect(screen.getByText('彩边证据不足，待核对')).toBeInTheDocument()
  expect(within(screen.getAllByRole('table').at(-1)!).queryByText('2.2')).not.toBeInTheDocument()
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
  expect(screen.queryByRole('link', { name: '查看声子 DOS' })).not.toBeInTheDocument()
})
it('无标量记录时谱仍出现于正确模块', async () => {
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><PropertySpectrumState stateKey="sample" summary="sample"><MissingPropertySpectrumModules existing={[]} /></PropertySpectrumState></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByText('动力学性质')).toBeInTheDocument()
  expect(screen.getByText('超导性质')).toBeInTheDocument()
  const dos = screen.getByText('查看声子 DOS'), alpha = screen.getByText('查看 α²F')
  expect(dos).not.toBeVisible()
  expect(alpha).not.toBeVisible()
  const dynamicModule = screen.getByTestId('property-module-dynamical_properties')
  const superconductiveModule = screen.getByTestId('property-module-superconductive_properties')
  fireEvent.click(dynamicModule.querySelector('summary')!)
  expect(dos).toBeVisible()
  expect(alpha).not.toBeVisible()
  fireEvent.click(superconductiveModule.querySelector('summary')!)
  expect(alpha).toBeVisible()
  fireEvent.click(dynamicModule.querySelector('summary')!)
  expect(dos).not.toBeVisible()
  expect(alpha).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()

})
it('返回地址只允许站内路径', () => {
  for (const value of ['https://evil.test', '//evil.test', '/\\evil.test', '/\nevil.test']) expect(safeSpectrumReturn(value)).toBe('/upload')
  expect(safeSpectrumReturn('/papers/12#material-state-sample')).toBe('/papers/12#material-state-sample')
})

it('单图支持原图、提取及叠加三种显示方式', async () => {
  const raw = listing.items[0] as any
  raw.source.size_px = [160,100]
  Object.assign(raw.result.curves[0], { roi:[10,20,80,90], frequency_direction: 'y', axis_calibration: { amplitude: {slope:1,intercept:0}, frequency: {slope:-1,intercept:90} } })
  raw.result.curves[0].points.forEach((p: any) => { p.frequency_pixel = 90 - p.frequency_thz })
  render(<MemoryRouter initialEntries={[address()]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  await screen.findByText('声子 DOS解析详情')
  expect(screen.getByRole('img', { name: /频率沿竖轴/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', {name:'仅原图'}))
  expect(await screen.findByRole('img', {name:'论文谱原图'})).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', {name:'原图与数据叠加'}))
  expect(screen.getByRole('img', {name:'原图与提取数据叠加'})).toBeInTheDocument()
  expect(screen.getAllByRole('img')).toHaveLength(1)
})

it('同状态的多个投影共用入口，累计 λ 与 α²F 同组，其他压力和集合不合并', async () => {
  const item = listing.items[0]
  item.result.curves.push({ ...item.result.curves[0], id: 'h-dos', projection: 'H' }, { ...item.result.curves[1], id: 'lambda', kind: 'cumulative_lambda' })
  listing.items.push({ ...structuredClone(item), id: 'other-pressure', state_key: 'other' })
  expect(spectrumGroups(listing.items, 'sample').map(group => group.curves.length)).toEqual([2, 2])
  mountEdit()
  expect(await screen.findByRole('link', { name: '查看声子 DOS' })).toBeVisible()
  expect(screen.getAllByRole('link', { name: '查看声子 DOS' })).toHaveLength(1)
  expect(screen.getAllByRole('link', { name: '查看 α²F' })).toHaveLength(1)
  expect(screen.getByText('2 条曲线')).toBeInTheDocument()
  expect(screen.getByText('含累计 λ')).toBeInTheDocument()
})

it('无该状态谱时显示禁用空态，不串用其他压力', async () => {
  listing.items[0].state_key = 'other'
  mountEdit()
  expect(await screen.findByRole('button', { name: '暂无声子 DOS' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂无 α²F' })).toBeDisabled()
  expect(screen.queryByRole('link', { name: '查看声子 DOS' })).not.toBeInTheDocument()
})

it('未归属空结果在独立详情显示失败和真实来源，不挂载假曲线', async () => {
  listing.items[0].state_key = null
  listing.items[0].result.curves = []
  listing.items[0].result.quality = { limitations: ['无法明确压力'] }
  const unassigned = '/spectra/collection?target=upload&target_id=task&state_key=unassigned&collection_version=2&run=run1&return=%2Fupload'
  render(<MemoryRouter initialEntries={[unassigned]}><Routes><Route path="/spectra/:collectionId" element={<SpectrumDetailPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('谱提取记录')).toBeInTheDocument()
  expect(screen.queryByText('这组谱尚未归属到当前材料状态')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', {name:'仅原图'}))
  expect(await screen.findByAltText('论文谱原图')).toBeInTheDocument()
  expect(screen.getByText(/无法明确压力/)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByRole('img', { name: /谱曲线/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '确认归属并重新计算' })).not.toBeInTheDocument()
})

it('未归属候选只显示摘要，点击才读取原图和点表', async () => {
  listing.items[0].state_key = null
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><UnassignedPropertySpectra /></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByRole('link', { name: '核对归属' })).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(api.download).not.toHaveBeenCalled()
})

it('六条失败记录不计入一组待确认谱，保留原因及详情入口', async () => {
  const spectrum = listing.items[0]
  spectrum.state_key = null
  for (let index = 0; index < 6; index++) listing.items.push({ ...structuredClone(spectrum), id: `failed-${index}`,
    run: { id: `run-${index}`, status: 'needs_review' }, result: { curves: [], failures: [`第 ${index} 次标定 HTTP 503`] } })
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><UnassignedPropertySpectra /></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByText('待确认归属 · 1 组谱数据')).toBeVisible()
  expect(screen.getByText('谱提取记录 · 6 条未生成曲线或标定')).toBeVisible()
  expect(screen.getAllByRole('link', { name: '核对归属' })).toHaveLength(1)
  const history = screen.getByText('谱提取记录 · 6 条未生成曲线或标定')
  fireEvent.click(history)
  expect(screen.getByText('第 0 次标定 HTTP 503')).toBeVisible()
  expect(screen.getAllByRole('link', { name: '查看提取记录' })).toHaveLength(6)
  expect(api.download).not.toHaveBeenCalled()
})

it('只有失败记录时不声称存在待分配谱；有真实标定但未生成曲线仍可核对归属', async () => {
  listing.items[0].state_key = null
  listing.items[0].result = { curves: [], failures: ['未发现谱图'] }
  const view = render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><UnassignedPropertySpectra /></PropertySpectraProvider></MemoryRouter>)
  await screen.findByText('谱提取记录 · 1 条未生成曲线或标定')
  expect(screen.queryByText(/待确认归属 ·/)).not.toBeInTheDocument()
  view.unmount()
  listing.items[0].result.calibration = { curves: [{ id: 'a', kind: 'alpha2f' }] }
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}><UnassignedPropertySpectra /></PropertySpectraProvider></MemoryRouter>)
  expect(await screen.findByText('待确认归属 · 1 组谱数据')).toBeVisible()
  expect(screen.getByRole('link', { name: '核对归属' })).toBeVisible()
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
  expect(await screen.findByText('当前为只读或缺少有效标定，不能凭图片猜测材料归属。')).toBeInTheDocument()
  expect(screen.queryByLabelText('选择归属材料状态')).not.toBeInTheDocument()
  expect(api.put).not.toHaveBeenCalled()
})

it('重新计算尚无数值时仍按真实标定保留类型入口，不伪造曲线', async () => {
  listing.items[0].run.status = 'queued'
  listing.items[0].result.curves = []
  listing.items[0].result.calibration = { curves: [{ id: 'h', kind: 'phonon_dos' }, { id: 'a', kind: 'alpha2f' }] }
  mountEdit()
  expect(await screen.findByRole('link', { name: '查看声子 DOS' })).toBeVisible()
  expect(screen.getByRole('link', { name: '查看 α²F' })).toBeVisible()
  expect(screen.getAllByText('尚无数值曲线，可查看原图与提取状态。')).toHaveLength(2)
  expect(screen.getByRole('link', { name: '查看声子 DOS' })).toHaveAttribute('target', '_blank')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('只有累计 λ 时入口如实标明，不冒充存在 α²F', async () => {
  listing.items[0].result.curves = [{ ...listing.items[0].result.curves[1], kind: 'cumulative_lambda' }]
  mountEdit()
  expect(await screen.findByRole('link', { name: '查看累计 λ' })).toBeVisible()
  expect(screen.queryByRole('link', { name: '查看 α²F' })).not.toBeInTheDocument()
})

it.each([false, true])('已有模块内的谱入口与空态随模块折叠，readOnly=%s', async readOnly => {
  const changed = vi.fn()
  const modules = [emptyPropertyModule('dynamical_properties', 0), emptyPropertyModule('superconductive_properties', 1)]
  render(<MemoryRouter><PropertySpectraProvider context={{ target: { target: 'upload', target_id: 'task' } }}>
    <PropertySpectrumState stateKey="sample" summary="150 GPa"><PropertyModuleEditor modules={modules} readOnly={readOnly} onChange={changed} /></PropertySpectrumState>
    <PropertySpectrumState stateKey="empty" summary="300 GPa"><div data-testid="empty-spectra-state"><PropertyModuleEditor modules={modules} readOnly={readOnly} onChange={changed} /></div></PropertySpectrumState>
  </PropertySpectraProvider></MemoryRouter>)
  const dos = await screen.findByText('查看声子 DOS'), alpha = screen.getByText('查看 α²F')
  const empty = screen.getByTestId('empty-spectra-state')
  const noDos = within(empty).getByText('暂无声子 DOS'), noAlpha = within(empty).getByText('暂无 α²F')
  for (const element of [dos, alpha, noDos, noAlpha]) expect(element).not.toBeVisible()
  const allDynamic = screen.getAllByTestId('property-module-dynamical_properties')
  fireEvent.click(allDynamic[0].querySelector('summary')!)
  expect(dos).toBeVisible()
  expect(alpha).not.toBeVisible()
  fireEvent.click(allDynamic[0].querySelector('summary')!)
  expect(dos).not.toBeVisible()
  fireEvent.click(allDynamic[1].querySelector('summary')!)
  expect(noDos).toBeVisible()
  expect(noAlpha).not.toBeVisible()
  fireEvent.click(screen.getAllByTestId('property-module-superconductive_properties')[1].querySelector('summary')!)
  expect(noAlpha).toBeVisible()
  expect(changed).not.toHaveBeenCalled()
  expect(api.download).not.toHaveBeenCalled()
})
