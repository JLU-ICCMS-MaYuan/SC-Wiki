import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import { emptyPropertyModule, emptyPropertyRecord, PROPERTY_MODULES } from '../../frontend/src/lib/propertyModules'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks(); clearFormDefinitionCache() })
const initial = () => PROPERTY_MODULES.map((module, index) => ({ ...emptyPropertyModule(module.code, index), module_key: module.code,
  records: [{ ...emptyPropertyRecord(module.code), record_key: module.code, name_raw: `name-${index}`, value_kind: 'text' as const, value_raw: `value-${index}`, value_text: `value-${index}` }],
}))
const region = (index: number) => screen.getByTestId(`property-module-${PROPERTY_MODULES[index].code}`)
const details = (index: number) => region(index).querySelector<HTMLDetailsElement>('[data-property-module-section]')!
const toggle = (index: number) => fireEvent.click(region(index).querySelector('[data-property-module-toggle]')!)
function mount(readOnly = false, start = initial) {
  vi.mocked(api.get).mockImplementation(async path => {
    const definitions = PROPERTY_MODULES.map(module => ({ definition_key: `record.${module.code}.custom`, version: 1, target_kind: 'property_record', module_code: module.code, record_type: 'property', property_code: 'custom', core_schema: {}, json_schema: { type: 'object', additionalProperties: true }, ui_schema: {}, status: 'published', checksum: 'fixture' }))
    return (path.startsWith('/api/form-definitions?') ? definitions.filter(item => path.includes(item.module_code)) : definitions.find(item => path.includes(item.definition_key))) as never
  })
  const changed = vi.fn()
  function Editor() {
    const [modules, setModules] = useState(start)
    return <PropertyModuleEditor modules={modules} readOnly={readOnly} onChange={next => { changed(next); setModules(next) }} />
  }
  const view = render(<Editor />)
  return { ...view, changed }
}
it('四模块默认折叠，展开互不影响，折叠不修改科学数据', () => {
  const { changed } = mount()
  for (let i = 0; i < 4; i++) {
    expect(details(i).open).toBe(false)
    expect(within(region(i)).getByLabelText('名称')).not.toBeVisible()
    expect(within(region(i)).getByText(PROPERTY_MODULES[i].label, { exact: true })).toBeVisible()
  }
  toggle(1)
  expect(within(region(1)).getByLabelText('名称')).toBeVisible()
  for (const i of [0, 2, 3]) expect(details(i).open).toBe(false)
  toggle(1)
  expect(details(1).open).toBe(false)
  expect(changed).not.toHaveBeenCalled()
})
it('未保存输入和内部记录的折叠状态在模块收起后保留，输入不重新挂载', () => {
  const { changed } = mount()
  toggle(0)
  const input = within(region(0)).getByLabelText('名称')
  fireEvent.change(input, { target: { value: '尚未保存的名称' } })
  const recordHeader = within(region(0)).getByRole('button', { name: /记录 1/ })
  fireEvent.click(recordHeader)
  expect(recordHeader).toHaveAttribute('aria-expanded', 'false')
  toggle(0); toggle(0)
  expect(recordHeader).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(recordHeader)
  expect(within(region(0)).getByLabelText('名称')).toBe(input)
  expect(input).toHaveValue('尚未保存的名称')
  expect(changed).toHaveBeenCalledTimes(1)
})
it('不提供模块移动按钮，折叠不改变已有模块顺序', () => {
  const { changed } = mount()
  expect(screen.queryByLabelText('上移模块')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('下移模块')).not.toBeInTheDocument()
  toggle(0)
  expect(details(0).open).toBe(true)
  expect(details(1).open).toBe(false)
  expect([...document.querySelectorAll<HTMLElement>('[data-module-key]')].map(node => node.dataset.moduleKey)).toEqual(PROPERTY_MODULES.map(module => module.code))
  expect(changed).not.toHaveBeenCalled()
})
it('只读模块也默认折叠且可展开查看，输入继续禁用', () => {
  const { changed } = mount(true)
  expect(details(2).open).toBe(false)
  toggle(2)
  const input = within(region(2)).getByLabelText('名称')
  expect(input).toBeVisible(); expect(input).toBeDisabled()
  toggle(2)
  expect(input).not.toBeVisible()
  expect(changed).not.toHaveBeenCalled()
})
it('折叠标题保留外部校验问题提示', () => {
  render(<PropertyModuleEditor modules={initial()} readOnly onChange={vi.fn()} issues={[{ field: '0.records.0.value_raw', code: 'invalid', message: '请检查当前值' }]} />)
  expect(details(0).open).toBe(false)
  expect(within(region(0)).getByText('1 项待处理：请检查当前值')).toBeVisible()
})

it('新增模块默认折叠且不收起已经展开的模块', () => {
  mount(false, () => initial().slice(0, 1))
  toggle(0)
  fireEvent.mouseDown(screen.getByRole('combobox', { name: '添加物性模块' }))
  fireEvent.click(screen.getByRole('option', { name: '电子性质', exact: true }))
  expect(details(3).open).toBe(false)
  expect(details(0).open).toBe(true)
})
