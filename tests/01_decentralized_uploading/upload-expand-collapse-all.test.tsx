import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import { MaterialStateControlsContext } from '../../frontend/src/context/MaterialStateControlsContext'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { normalizeUploadDraft } from '../../frontend/src/lib/paperProcessing'
import { PROPERTY_MODULES } from '../../frontend/src/lib/propertyModules'
import { api } from '../../frontend/src/lib/api'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import fixture from '../fixtures/issue141/draft.json'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn() } }))
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async path => {
    const definitions = PROPERTY_MODULES.map(module => ({ definition_key: `record.${module.code}.custom`, version: 1,
      target_kind: 'property_record', module_code: module.code, record_type: 'property', property_code: 'custom',
      core_schema: {}, json_schema: { type: 'object', additionalProperties: true }, ui_schema: {}, status: 'published', checksum: 'fixture' }))
    return (path.startsWith('/api/form-definitions?') ? definitions.filter(item => path.includes(item.module_code))
      : definitions.find(item => path.includes(item.definition_key))) as never
  })
})
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); clearFormDefinitionCache() })

function mount({ empty = false, readOnly = false, portal = true } = {}) {
  const changed = vi.fn()
  function Editor() {
    const [states, setStates] = useState(() => empty ? [] : normalizeUploadDraft(fixture).material_states)
    const [slot, setSlot] = useState<HTMLDivElement | null>(null)
    return <LanguageProvider>
      <div data-testid="toolbar"><div ref={portal ? setSlot : undefined} /><a href="/upload">返回上传记录</a></div>
      <MaterialStateControlsContext.Provider value={slot}>
        <MaterialStatesEditor states={states} catalogs={null} readOnly={readOnly}
          onChange={next => { changed(next); setStates(next) }} />
      </MaterialStateControlsContext.Provider>
      <details open data-testid="outside-module" data-property-module-section><summary>其他区域</summary></details>
    </LanguageProvider>
  }
  return { ...render(<Editor />), changed }
}
const modules = () => [...document.querySelectorAll<HTMLDetailsElement>('[data-property-modules] [data-property-module-section]')]
const stateHeaders = () => [...document.querySelectorAll<HTMLElement>('[aria-controls^="material-state-"]')]
const button = (name: string) => screen.getByRole('button', { name, exact: true })

it('顶部只有一组按钮，一次切换两材料的八个模块；重复点击和单项操作仍有效', async () => {
  const { changed } = mount()
  expect(within(screen.getByTestId('toolbar')).getByRole('button', { name: '全部折叠' })).toBeVisible()
  expect(screen.getAllByRole('button', { name: '全部展开' })).toHaveLength(1)
  expect(modules()).toHaveLength(8)
  expect(stateHeaders()).toHaveLength(2)
  expect(modules().every(item => !item.open)).toBe(true)
  fireEvent.click(button('全部展开'))
  expect(modules().every(item => item.open)).toBe(true)
  expect(stateHeaders().every(item => item.getAttribute('aria-expanded') === 'true')).toBe(true)
  fireEvent.click(modules()[3].querySelector('summary')!)
  expect(modules()[3].open).toBe(false)
  fireEvent.click(button('全部展开'))
  expect(modules().every(item => item.open)).toBe(true)
  fireEvent.click(button('全部折叠'))
  expect(stateHeaders().every(item => item.getAttribute('aria-expanded') === 'false')).toBe(true)
  expect(modules().every(item => !item.open)).toBe(true)
  fireEvent.click(stateHeaders()[0])
  await waitFor(() => expect(screen.getAllByLabelText('化学式')[0]).toBeVisible())
  expect(modules().every(item => !item.open)).toBe(true)
  fireEvent.click(button('全部折叠'))
  expect(stateHeaders()[0]).toHaveAttribute('aria-expanded', 'false')
  expect(changed).not.toHaveBeenCalled()
})

it('保留未保存输入、输入节点和内部记录状态，不影响晶体结构及其他区域', async () => {
  const { changed } = mount()
  fireEvent.click(button('全部展开'))
  const region = screen.getAllByTestId('property-module-superconductive_properties')[0]
  const input = within(region).getByLabelText('名称')
  fireEvent.change(input, { target: { value: '未保存输入' } })
  const record = within(region).getByRole('button', { name: /记录 1/ })
  fireEvent.click(record)
  const structure = screen.getAllByRole('button', { name: /晶体结构/ })[0]
  expect(structure).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(structure)
  fireEvent.click(button('全部折叠'))
  fireEvent.click(button('全部展开'))
  expect(structure).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByTestId('outside-module')).toHaveAttribute('open')
  expect(record).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(record)
  await waitFor(() => expect(input).toBeVisible())
  expect(within(region).getByLabelText('名称')).toBe(input)
  expect(input).toHaveValue('未保存输入')
  expect(changed).toHaveBeenCalledTimes(1)
})

it('空状态和只读模式的顶部按钮禁用，保持只读卡片展开', () => {
  const empty = mount({ empty: true })
  expect(button('全部折叠')).toBeDisabled()
  expect(button('全部展开')).toBeDisabled()
  empty.unmount()
  const { changed } = mount({ readOnly: true })
  expect(button('全部折叠')).toBeDisabled()
  expect(button('全部展开')).toBeDisabled()
  expect(stateHeaders().every(item => item.getAttribute('aria-expanded') === 'true')).toBe(true)
  expect(changed).not.toHaveBeenCalled()
})

it('无顶部槽位时保留表单内入口，仍统一控制两层', () => {
  mount({ portal: false })
  expect(within(screen.getByTestId('toolbar')).queryByRole('button')).not.toBeInTheDocument()
  fireEvent.click(button('全部展开'))
  expect(modules().every(item => item.open)).toBe(true)
  fireEvent.click(button('全部折叠'))
  expect(modules().every(item => !item.open)).toBe(true)
})

it('英文按钮可通过键盘操作，重新挂载任务不继承折叠状态', async () => {
  localStorage.setItem('sc-wiki.language', 'en')
  const first = mount()
  const keyboard = userEvent.setup()
  button('Expand all').focus()
  await keyboard.keyboard('{Enter}')
  expect(modules().every(item => item.open)).toBe(true)
  button('Collapse all').focus()
  await keyboard.keyboard(' ')
  expect(stateHeaders().every(item => item.getAttribute('aria-expanded') === 'false')).toBe(true)
  first.unmount(); mount()
  expect(stateHeaders().every(item => item.getAttribute('aria-expanded') === 'true')).toBe(true)
  expect(modules().every(item => !item.open)).toBe(true)
})
