import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'

const state = (overrides: Partial<DraftMaterialState> = {}): DraftMaterialState => ({
  state_key: 'fixture-105-a', material: 'Sn', element_count: 1,
  material_dimensionality: 'three_dimensional', structure_families: [], property_modules: [],
  crystal_system: 'cubic', reported_space_group_symbol: 'Fm-3m', reported_space_group_number: 225,
  ...overrides,
})
const cleared = { crystal_system: 'unknown', reported_space_group_symbol: null, reported_space_group_number: null } satisfies Partial<DraftMaterialState>

function setup(initial = [state()], readOnly = false) {
  const changes = vi.fn(), edits = vi.fn()
  function Harness() {
    const [states, setStates] = useState(initial)
    return <MaterialStatesEditor states={states} onChange={next => { changes(next); setStates(next) }}
      onScientificEdit={edits} catalogs={null} readOnly={readOnly}
      spaceGroups={[{ number: 225, symbol: 'Fm-3m' }, { number: 139, symbol: 'I4/mmm' }]} />
  }
  render(<Harness />)
  return { changes, edits }
}

async function selectCrystal(name: string) {
  fireEvent.mouseDown(screen.getAllByRole('combobox', { name: '晶系' })[0])
  fireEvent.click(await screen.findByRole('option', { name, exact: true }))
}

afterEach(cleanup)

describe('Issue #105：晶系未知联动', () => {
  it('一次清空三字段，其他材料状态、结构和物性保持不变', async () => {
    const first = state({ structure: { space_group_symbol: 'Fm-3m', space_group_number: 225 } })
    const second = state({ state_key: 'fixture-105-b', material: 'Pb' })
    const { changes, edits } = setup([first, second])
    await selectCrystal('未知')
    expect(changes).toHaveBeenCalledTimes(1)
    const next = changes.mock.calls[0][0]
    expect(next[0]).toEqual({ ...first, ...cleared })
    expect(next[0].structure).toBe(first.structure)
    expect(next[0].property_modules).toBe(first.property_modules)
    expect(next[1]).toBe(second)
    expect(screen.getAllByRole('combobox', { name: '空间群符号' })[0]).toHaveValue('')
    expect(screen.getAllByLabelText('空间群号')[0]).toHaveValue(null)
    expect(edits.mock.calls.map(([field]) => field).sort()).toEqual([
      'material_states[0].crystal_system', 'material_states[0].reported_space_group_number',
      'material_states[0].reported_space_group_symbol',
    ])
  })

  it('加载不清理，已经未知时再次选择才清空残留空间群', async () => {
    const { changes, edits } = setup([state({ crystal_system: 'unknown' })])
    expect(changes).not.toHaveBeenCalled()
    expect(screen.getByRole('combobox', { name: '空间群符号' })).toHaveValue('Fm-3m')
    await selectCrystal('未知')
    expect(changes).toHaveBeenCalledTimes(1)
    expect(changes.mock.calls[0][0][0]).toMatchObject(cleared)
    expect(edits).not.toHaveBeenCalledWith('material_states[0].crystal_system')
  })

  it('符号本地输入、失焦及再次聚焦都不会恢复清空前的文本', async () => {
    const user = userEvent.setup()
    const { changes } = setup([state({ crystal_system: 'unknown', reported_space_group_symbol: null })])
    const symbol = screen.getByRole('combobox', { name: '空间群符号' })
    await user.type(symbol, 'old-symbol')
    await user.click(screen.getByRole('combobox', { name: '晶系' }))
    await user.click(await screen.findByRole('option', { name: '未知', exact: true }))
    await user.click(symbol)
    await user.tab()
    expect(symbol).toHaveValue('')
    expect(changes.mock.calls.at(-1)?.[0][0]).toMatchObject(cleared)
  })

  it('非未知晶系切换保留现有空间群，避免扩展清空范围', async () => {
    const { changes } = setup()
    await selectCrystal('四方')
    expect(changes.mock.calls.at(-1)?.[0][0]).toMatchObject({
      crystal_system: 'tetragonal', reported_space_group_symbol: 'Fm-3m', reported_space_group_number: 225,
    })
  })

  it('清空后填写合法群号恢复既有正向联动', async () => {
    const { changes } = setup()
    await selectCrystal('未知')
    fireEvent.change(screen.getByLabelText('空间群号'), { target: { value: '139' } })
    expect(changes.mock.calls.at(-1)?.[0][0]).toMatchObject({
      crystal_system: 'tetragonal', reported_space_group_symbol: 'I4/mmm', reported_space_group_number: 139,
    })
    expect(screen.getByRole('combobox', { name: '空间群符号' })).toHaveValue('I4/mmm')
  })

  it('清空后选择标准符号恢复既有正向联动', async () => {
    const user = userEvent.setup()
    const { changes } = setup()
    await selectCrystal('未知')
    await user.type(screen.getByRole('combobox', { name: '空间群符号' }), 'I4')
    await user.click(await screen.findByRole('option', { name: 'I4/mmm' }))
    expect(changes.mock.calls.at(-1)?.[0][0]).toMatchObject({
      crystal_system: 'tetragonal', reported_space_group_symbol: 'I4/mmm', reported_space_group_number: 139,
    })
  })

  it('重复清空保持空值且不产生虚假的核对字段变化', async () => {
    const { changes, edits } = setup([state(cleared)])
    await selectCrystal('未知')
    expect(changes.mock.calls.at(-1)?.[0][0]).toMatchObject(cleared)
    expect(edits).not.toHaveBeenCalled()
  })

  it('只读状态即使事件送到选择控件也不发出修改', async () => {
    const { changes, edits } = setup([state({ crystal_system: 'unknown' })], true)
    await selectCrystal('未知')
    expect(changes).not.toHaveBeenCalled()
    expect(edits).not.toHaveBeenCalled()
  })
})
