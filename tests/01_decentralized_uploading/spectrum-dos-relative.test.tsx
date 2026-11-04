import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import DosRelativeMetrics, { type DosRelativeReport } from '../../frontend/src/components/spectrumEditor/DosRelativeMetrics'
import { SpectrumMetrics } from '../../frontend/src/components/SpectrumDetailView'

afterEach(cleanup)
const report = (): DosRelativeReport => ({
  method:'dos-relative-v5',
  components:[{curve_id:'La',projection:'La',status:'available',area:4,frequency_interval_thz:[0,1]},
    {curve_id:'H',projection:'H',status:'available',area:5,frequency_interval_thz:[0,1]}],
  shares:{status:'available',total_area:9,fractions:{La:4/9,H:5/9},expected_fractions:{La:1/3,H:2/3}},
  normalization:{status:'available',coefficient:1,primitive_atoms:3,target_modes:9,total_mode_integral:9,
    component_mode_integrals:{La:4,H:5},expected_modes:{La:3,H:6},deviations:{
      La:{absolute_difference:1,relative_difference_pct:100/3},H:{absolute_difference:1,relative_difference_pct:100/6}}}
})
it('同一个系数保留元素偏差，归一化总和不显示验证通过',()=>{
  render(<DosRelativeMetrics report={report()} restricted={false}/>)
  const areas=screen.getByRole('table',{name:'DOS 相对面积'})
  expect(within(areas).getByText('44.44%')).toBeVisible()
  expect(within(areas).getByText('33.33%')).toBeVisible()
  const normalized=screen.getByRole('table',{name:'DOS 归一化模式积分'})
  for(const text of ['4','5','3','6','33.33%','16.67%'])expect(within(normalized).getByText(text)).toBeVisible()
  expect(screen.getByText(/不代表提取准确性已验证/)).toBeVisible()
  expect(screen.queryByText(/验证通过|满足判断/)).toBeNull()
})
it('没有N仍展示面积与比例，部分失败不隐藏其他面积',()=>{
  const r=report();r.normalization={status:'unavailable',reason:'缺少可信原胞原子数 N'}
  const {rerender}=render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByText('4',{exact:true})).toBeVisible()
  expect(screen.getByText('缺少可信原胞原子数 N')).toBeVisible()
  r.components[0]={curve_id:'La',projection:'La',status:'unavailable',reason:'曲线存在缺口'}
  r.shares={status:'unavailable',reason:'部分曲线不能积分'}
  rerender(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByText('5',{exact:true})).toBeVisible()
  expect(screen.getByText('曲线存在缺口')).toBeVisible()
  expect(screen.queryByText('55.56%')).toBeNull()
})
it('历史/失效结果和旧方法不混入当前归一化',()=>{
  const {rerender}=render(<DosRelativeMetrics report={report()} restricted/>)
  expect(screen.queryByRole('table')).toBeNull()
  rerender(<DosRelativeMetrics restricted={false}/>)
  expect(screen.getByText(/请点击重新计算/)).toBeVisible()
})
it('正式03同时展示相对、归一化与独立绝对结果，N不被单位失败隐藏',()=>{
  const item:any={review:{},stale:false,run:{id:'r'},result:{quality:{dos_relative:report(),dos_mode_integral:{status:'unavailable',reason:'没有独立刻度'}}}}
  const curves:any=[{id:'La',kind:'phonon_dos',points:[{frequency_thz:0,observed_amplitude:0},{frequency_thz:1,observed_amplitude:0}]}]
  render(<SpectrumMetrics item={item} curves={curves} history={false}/>)
  expect(screen.getByText('3 / 9')).toBeVisible()
  expect(screen.getByText('原始绝对密度积分（独立检查）')).toBeVisible()
  expect(screen.getByRole('table',{name:'DOS 相对面积'})).toBeVisible()
  expect(screen.getByText('没有独立刻度')).toBeVisible()
})

it('无需N即可对照近似元素比和化学式，不再显示频段确认门槛',()=>{
  const r=report()
  r.shares.element_ratio={status:'available',elements:['La','H'],reference_element:'La',
    estimated_ratio:[1,1.25],expected_ratio:[1,2],formula:'LaH2',reference_label:'化学式比例',max_share_difference_pp:100/9}
  r.normalization={status:'unavailable',reason:'缺少可信原胞原子数 N'}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  const summary=screen.getByTestId('dos-element-ratio')
  expect(within(summary).getByText('面积估计：1 : 1.25')).toBeVisible()
  expect(within(summary).getByText('化学式比例（LaH2）：1 : 2')).toBeVisible()
  expect(within(summary).getByText('最大原子占比差：11.11 个百分点')).toBeVisible()
  expect(screen.queryByText(/完整频段|完整振动频段/)).toBeNull()
  expect(screen.getByText('缺少可信原胞原子数 N')).toBeVisible()
})
it('投影元素不匹配时不展示伪造元素比，仍保留原始面积',()=>{
  const r=report();r.shares.element_ratio={status:'unavailable',reason:'分波元素与化学计量元素集合不一致'}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.queryByTestId('dos-element-ratio')).toBeNull()
  expect(screen.getByText('分波元素与化学计量元素集合不一致')).toBeVisible()
  expect(screen.getByRole('table',{name:'DOS 相对面积'})).toBeVisible()
})

it('旧方法保存的频段失败提示不再展示，提示重新计算当前结果',()=>{
  const r=report();r.method='dos-relative-v1'
  r.normalization={status:'unavailable',reason:'La：原图完整频段尚待核对'}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.queryByText(/原图完整频段尚待核对/)).toBeNull()
  expect(screen.getByText(/请点击重新计算/)).toBeVisible()
})


it("TDOS 独立显示归一化，保留范围且元素列留空",()=>{
  const r=report()
  r.spectrum_type="total"
  r.components=[{curve_id:"tdos",projection:"total",status:"available",area:4,frequency_interval_thz:[3.6556,58.648]}]
  r.shares={status:"unavailable",reason:"当前为 TDOS，未提供元素分波，暂不计算元素占比"}
  r.normalization={status:"available",coefficient:5.25,primitive_atoms:7,target_modes:21,total_mode_integral:21,
    component_mode_integrals:{tdos:21},expected_modes:{},deviations:{}}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  const row=within(screen.getByRole("table",{name:"DOS 相对面积"})).getAllByRole("row")[1]
  expect(within(row).getByText("TDOS（总态密度）")).toBeVisible()
  expect(within(row).getByText("3.6556–58.648")).toBeVisible()
  expect(within(row).getAllByText("—")).toHaveLength(2)
  expect(screen.getByText("归一化系数 C：5.25 · 总模式数：21（目标 3N：21）")).toBeVisible()
  expect(screen.queryByTestId("dos-element-ratio")).toBeNull()
  expect(screen.queryByRole("table",{name:"DOS 归一化模式积分"})).toBeNull()
  expect(screen.queryByText(/元素投影完整性|共同幅值尺度|所有元素共用/)).toBeNull()
})

it("旧 v3 的元素门槛提示只要求重算，不冒充 v4 总谱规则",()=>{
  const r=report();r.method="dos-relative-v3"
  r.normalization={status:"unavailable",reason:"元素投影完整性尚待核对"}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByText(/请点击重新计算/)).toBeVisible()
  expect(screen.queryByText("元素投影完整性尚待核对")).toBeNull()
})


it("当前纵轴任意单位积分独立显示，缺N和未知身份不隐藏结果",()=>{
  const r=report()
  r.components=[{curve_id:"source",projection:"source",status:"available",area:6.308648445665745,
    unit:"arbitrary_units·THz",amplitude_basis:{kind:"calibrated_values"},frequency_interval_thz:[3.6556,58.648]}]
  r.shares={status:"unavailable",reason:"元素投影完整性尚待核对"}
  r.normalization={status:"unavailable",reason:"缺少可信原胞原子数 N"}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  const table=screen.getByRole("table",{name:"DOS 相对面积"})
  expect(within(table).getByText("6.30865")).toBeVisible()
  expect(within(table).getByRole("columnheader",{name:"积分值（任意单位·THz · 纵轴刻度）"})).toBeVisible()
  expect(screen.getByText("缺少可信原胞原子数 N")).toBeVisible()
  expect(within(table).queryByText(/像素·THz/)).toBeNull()
})

it("无刻度的像素积分明确保留单位，v4旧结果要求重算",()=>{
  const r=report();r.components[0].unit="pixel·THz";r.components[0].amplitude_basis={kind:"source_pixels"}
  const {rerender}=render(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.getByRole("columnheader",{name:"积分值（像素·THz · 相对像素）"})).toBeVisible()
  r.method="dos-relative-v4";rerender(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(screen.queryByRole("table")).toBeNull()
  expect(screen.getByText(/请点击重新计算/)).toBeVisible()
})


it("总谱五列表格列出所有材料元素，无分波不伪造积分",()=>{
  const r=report();r.spectrum_type="total"
  r.components=[{curve_id:"S15_150GPa_total_phonon_dos",projection:"total",status:"available",area:6.308648445665745,
    unit:"arbitrary_units·THz",amplitude_basis:{kind:"calibrated_values"},frequency_interval_thz:[3.6556,58.648]}]
  r.composition={fractions:{Ca:1/7,H:6/7}}
  r.shares={status:"unavailable",reason:"未提供元素分波"}
  const {rerender}=render(<DosRelativeMetrics report={r} restricted={false}/>)
  const table=screen.getByRole("table",{name:"DOS 相对面积"})
  expect(within(table).getAllByRole("columnheader").map(e=>e.textContent)).toEqual(["元素 / TDOS","积分范围（THz）","积分值（任意单位·THz · 纵轴刻度）","面积占比","原子数占比"])
  const rows=within(table).getAllByRole("row")
  expect(rows).toHaveLength(4)
  const total=within(rows[1]).getAllByRole("cell")
  expect(total[0]).toHaveTextContent("TDOS（总态密度）")
  expect(total[1]).toHaveTextContent("3.6556–58.648")
  expect(total[2]).toHaveTextContent(/^6\.30865$/)
  expect(total[2].querySelector("span")).toBeNull()
  expect(within(table).queryByText("S15_150GPa_total_phonon_dos")).toBeNull()
  for(const [index,element,share] of [[2,"Ca","14.29%"],[3,"H","85.71%"]] as const){
    const cells=within(rows[index]).getAllByRole("cell")
    expect(cells).toHaveLength(5);expect(cells[0]).toHaveTextContent(element)
    expect(cells.slice(1,4).map(e=>e.textContent)).toEqual(["—","—","—"])
    expect(cells[4]).toHaveTextContent(share)
  }
  r.components[0].projection=r.components[0].curve_id;r.spectrum_type="projected"
  rerender(<DosRelativeMetrics report={r} restricted={false}/>)
  expect(within(table).getByText("待确认")).toBeVisible()
  expect(within(table).queryByText("S15_150GPa_total_phonon_dos")).toBeNull()
})

it("旧v5可靠结构计数也能列全元素，投影不完整仍显示已知原子数占比",()=>{
  const r=report();r.components=r.components.slice(0,1)
  r.shares={status:"unavailable",reason:"元素投影完整性尚待核对"}
  r.normalization={status:"unavailable",reason:"元素投影完整性尚待核对",structure_evidence:{species_counts:{La:1,H:2}}}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  const table=screen.getByRole("table",{name:"DOS 相对面积"})
  expect(within(table).getAllByRole("row")).toHaveLength(3)
  expect(within(table).getByText("33.33%")).toBeVisible()
  expect(within(table).getByText("66.67%")).toBeVisible()
  const h=within(table).getByText("H").closest("tr")!
  expect(within(h).getAllByRole("cell").slice(1,4).map(e=>e.textContent)).toEqual(["—","—","—"])
})


it("不同积分单位分别放入对应表头，不混用单位或丢失独立数值",()=>{
  const r=report()
  r.components[0].unit="arbitrary_units·THz";r.components[0].amplitude_basis={kind:"calibrated_values"}
  r.components[1].unit="pixel·THz";r.components[1].amplitude_basis={kind:"source_pixels"}
  r.shares={status:"unavailable",reason:"各曲线幅值单位不一致"}
  r.normalization={status:"unavailable",reason:"各曲线幅值单位不一致"}
  render(<DosRelativeMetrics report={r} restricted={false}/>)
  const tables=screen.getAllByRole("table",{name:"DOS 相对面积"})
  expect(tables).toHaveLength(2)
  for(const [index,label,value] of [[0,"任意单位·THz · 纵轴刻度","4"],[1,"像素·THz · 相对像素","5"]] as const){
    expect(within(tables[index]).getByRole("columnheader",{name:"积分值（"+label+"）"})).toBeVisible()
    expect(within(tables[index]).getByRole("columnheader",{name:"积分范围（THz）"})).toBeVisible()
    const cells=within(within(tables[index]).getAllByRole("row")[1]).getAllByRole("cell")
    expect(cells[1]).toHaveTextContent(/^0–1$/)
    expect(cells[2]).toHaveTextContent(value)
    expect(cells[2]).not.toHaveTextContent(/像素|任意单位|THz/)
  }
})
