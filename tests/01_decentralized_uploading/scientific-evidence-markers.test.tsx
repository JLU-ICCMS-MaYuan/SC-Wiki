import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { FormControl, InputLabel, MenuItem, Select, TextField } from '@mui/material'
import EvidenceFieldMarkers, { EvidenceRecordList } from '../../frontend/src/components/EvidenceFieldMarkers'
import type { EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'

afterEach(cleanup)

it('作者标签合并作者角色证据，隐藏菜单不使证据失去入口', async () => {
  const onOpen=vi.fn()
  const record: EvidenceRecord={key:'roles',field:'paper.corresponding_authors',label:'通讯作者',status:'supported',reason:'原文声明',evidences:[]}
  render(<div data-evidence-scope="authors"><TextField label="作者" data-issue-field="paper.authors" />
    <EvidenceFieldMarkers records={[record]} scope="authors" onOpen={onOpen} onChange={()=>{}} /></div>)
  fireEvent.click(await screen.findByRole('button',{name:'作者'}))
  expect(onOpen).toHaveBeenCalledWith('roles',['roles'])
})

it('结构参数只读标签使用精确结构来源并支持键盘', async () => {
  const onOpen = vi.fn()
  const record: EvidenceRecord = {key:'structure',state_key:'Sn',structure_hash:'hash',field:'material_states[0].structures[0]',label:'结构',status:'supported',reason:'来源已核验',evidences:[]}
  render(<div data-evidence-scope="structure"><div data-state-key="Sn"><div data-scientific-structure data-structure-hash="hash">
    <h3>文件</h3><dl><dt data-evidence-readonly>a (Å)</dt><dd>5</dd></dl>
  </div></div><EvidenceFieldMarkers records={[record]} scope="structure" onOpen={onOpen} onChange={()=>{}} /></div>)
  const label = await screen.findByRole('button',{name:'a (Å)'})
  fireEvent.keyDown(label,{key:'Enter'})
  expect(onOpen).toHaveBeenCalledWith('structure',['structure'])
})

it.each(['text', 'multiline', 'select', 'readonly'])('红框使用 %s 控件的标签缺口，解除问题恢复正常边框', async kind => {
  const record: EvidenceRecord = { key: 'border', field: 'value', label: '内容', status: 'missing', reason: '没有证据', evidences: [] }
  const form = (records: EvidenceRecord[]) => <div data-evidence-scope="border">
    <TextField label="内容" defaultValue="sample" multiline={kind === 'multiline'} select={kind === 'select'}
      disabled={kind === 'readonly'} data-issue-field="value">
      {kind === 'select' ? <MenuItem value="sample">sample</MenuItem> : undefined}
    </TextField>
    <EvidenceFieldMarkers records={records} scope="border" onOpen={() => {}} onChange={() => {}} />
  </div>
  const view = render(form([record]))
  await screen.findByRole('button', { name: '内容' })
  const control = view.container.querySelector<HTMLElement>('.MuiOutlinedInput-root')!
  const border = control.querySelector('fieldset')!
  expect(getComputedStyle(control).outline).toBe('none')
  expect(getComputedStyle(border).borderTopColor).toBe('rgb(211, 47, 47)')
  expect(getComputedStyle(border).borderTopWidth).toBe('2px')
  expect(border.querySelector('legend')).toHaveTextContent('内容')
  view.rerender(form([{ ...record, status: 'supported' }]))
  await waitFor(() => expect(control).not.toHaveAttribute('data-evidence-problem'))
  expect(getComputedStyle(border).borderTopColor).not.toBe('rgb(211, 47, 47)')
})

it('排序后按稳定身份标记原记录，修改仍映射到对应核对项', async () => {
  const onOpen = vi.fn(), onChange = vi.fn()
  const record: EvidenceRecord = { key: 'original', state_key: 'Sn', module_key: 'tc', record_key: 'r1', field: 'material_states[0].property_modules[0].records[0]', label: 'Sn Tc', status: 'unsupported', reason: '这是测量温度', evidences: [] }
  function Form({ reversed = false }) {
    return <div data-evidence-scope="test">
      {(reversed ? ['Pb', 'Sn'] : ['Sn', 'Pb']).map((state, index) => <div key={state} data-state-key={state}>
        <div data-module-key="tc"><div data-record-key="r1" data-testid={state} data-issue-field={`material_states[${index}].property_modules[0].records[0]`}>
          <input aria-label={`${state}值`} data-issue-field={`material_states[${index}].property_modules[0].records[0].value_number`} />
        </div></div>
      </div>)}
      <EvidenceFieldMarkers records={[record]} scope="test" onOpen={onOpen} onChange={onChange} />
    </div>
  }
  const view = render(<Form />)
  await waitFor(() => expect(screen.getByTestId('Sn')).toHaveAttribute('data-evidence-problem', 'true'))
  view.rerender(<Form reversed />)
  await waitFor(() => expect(screen.getByTestId('Sn')).toHaveAttribute('data-evidence-problem', 'true'))
  expect(screen.getByTestId('Pb')).not.toHaveAttribute('data-evidence-problem')
  fireEvent.click(screen.getByRole('button', {name: 'Sn Tc：查看来源核对（1）'}))
  expect(onOpen).toHaveBeenCalledWith('original', ['original'])
  fireEvent.input(screen.getByLabelText('Sn值'), {target: {value: '3.78'}})
  await waitFor(() => expect(onChange).toHaveBeenCalledWith(record.field, 'snapshot'))
  fireEvent.change(screen.getByLabelText('Sn值'))
  await new Promise(resolve => setTimeout(resolve, 10))
  expect(onChange).toHaveBeenCalledTimes(1)
})

it('科学差异忽略排序和补证，只失效被编辑记录', async () => {
  const { changedScientificFields } = await import('../../frontend/src/lib/evidenceFields')
  const first = { state_key: 'Sn', property_modules: [{ module_key: 'm', records: [{record_key:'a', value_number: 3.78}, {record_key:'b', value_number: 4.29}] }] }
  const second = { state_key: 'Pb', property_modules: [] }
  expect(changedScientificFields([first, second], [second, first], 'material_states')).toEqual([])
  const changed = structuredClone(first)
  changed.property_modules[0].records[1].value_number = 6
  expect(changedScientificFields([first, second], [changed, second], 'material_states')).toEqual(['material_states[0].property_modules[0].records[1].value_number'])
  expect(changedScientificFields({value_number:3.78}, {value_number:3.78,evidences:[{quote:'3.78'}]}, 'record')).toEqual([])
})


it('同框问题聚合为一个文字入口，已接受后仍可查看', async () => {
  const onOpen = vi.fn()
  const first: EvidenceRecord = { key:'a',field:'paper.summary',fields:['paper.summary','paper.summary'],label:'总结',status:'uncertain',reason:'条件冲突',evidences:[] }
  const second: EvidenceRecord = {...first,key:'b',reason:'结论歧义'}
  const form = (records: EvidenceRecord[]) => <div data-evidence-scope="group"><div data-issue-field="paper.summary" data-testid="field"><textarea aria-label="总结" /></div><EvidenceFieldMarkers records={records} scope="group" onOpen={onOpen} onChange={()=>{}} /></div>
  const view = render(form([first,second]))
  const button = await screen.findByRole('button',{name:'总结：查看来源核对（2）'})
  expect(screen.getAllByRole('button')).toHaveLength(1)
  expect(button.querySelector('svg')).toBeNull()
  expect(button).toHaveTextContent('总结')
  fireEvent.click(button)
  expect(onOpen).toHaveBeenCalledWith('a',['a','b'])
  view.rerender(form([first,second].map(r=>({...r,proposal_draft:{values:{},accepted:true,reason:'确认'}}))))
  await waitFor(()=>expect(screen.getByRole('button')).toBeInTheDocument())
  expect(screen.getByTestId('field')).not.toHaveAttribute('data-evidence-problem')
})

it.each(['总结', 'Summary'])('复用现有 %s 浮动标签，点击和键盘打开全部问题，解决后保留查看入口', async label => {
  const onOpen = vi.fn()
  const record: EvidenceRecord = { key: 'summary', field: 'paper.summary', label, status: 'uncertain', evidences: [] }
  const form = (records: EvidenceRecord[]) => <div data-evidence-scope="label">
    <TextField id="summary" label={label} multiline defaultValue="Original content" data-issue-field="paper.summary" />
    <EvidenceFieldMarkers records={records} scope="label" onOpen={onOpen} onChange={() => {}} />
  </div>
  const view = render(form([record, { ...record, key: 'second' }]))
  const trigger = await screen.findByRole('button', { name: label })
  expect(trigger).toHaveAttribute('aria-description', `${label}：查看来源核对（2）`)
  expect(trigger.tagName).toBe('LABEL')
  expect(trigger).toHaveAttribute('for', 'summary')
  expect(screen.getAllByRole('button')).toHaveLength(1)
  expect(screen.getByRole('textbox')).toHaveAccessibleName(label)
  fireEvent.click(trigger)
  fireEvent.keyDown(trigger, { key: 'Enter' })
  fireEvent.keyDown(trigger, { key: ' ' })
  expect(onOpen).toHaveBeenCalledTimes(3)
  expect(onOpen).toHaveBeenLastCalledWith('summary', ['summary', 'second'])
  expect(trigger).toHaveFocus()
  fireEvent.click(screen.getByRole('textbox'))
  expect(onOpen).toHaveBeenCalledTimes(3)
  view.rerender(form([{ ...record, status: 'supported' }]))
  await waitFor(() => expect(trigger).toHaveAttribute('role', 'button'))
  expect(trigger).toHaveAttribute('tabindex', '0')
  expect(trigger).toHaveAttribute('data-evidence-key', 'summary')
  expect(trigger).toHaveAttribute('for', 'summary')
  fireEvent.click(trigger)
  expect(onOpen).toHaveBeenCalledTimes(4)
})

it('选择框复用自己的标签，区域问题使用标题，快速审核仅保留标题按钮', async () => {
  const onOpen = vi.fn()
  const records: EvidenceRecord[] = [
    { key: 'system', field: 'crystal_system', label: 'Crystal system', status: 'uncertain', evidences: [] },
    { key: 'structure', field: 'structure', label: '结构', status: 'missing', evidences: [] },
  ]
  const view = render(<div data-evidence-scope="select">
    <FormControl data-issue-field="crystal_system"><InputLabel id="system-label">Crystal system</InputLabel><Select labelId="system-label" label="Crystal system" defaultValue="cubic"><MenuItem value="cubic">Cubic</MenuItem></Select></FormControl>
    <section data-issue-field="structure"><h3>原始结构文件</h3><TextField data-issue-field="structure.name" label="文件名" defaultValue="sample.cif" /></section>
    <EvidenceFieldMarkers records={records} scope="select" onOpen={onOpen} onChange={() => {}} />
  </div>)
  const trigger = await screen.findByRole('button', { name: 'Crystal system' })
  fireEvent.click(trigger)
  expect(onOpen).toHaveBeenLastCalledWith('system', ['system'])
  expect(screen.getByRole('combobox')).toHaveAccessibleName('Crystal system')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '原始结构文件' }))
  expect(onOpen).toHaveBeenLastCalledWith('structure', ['structure'])
  expect(screen.getByLabelText('文件名')).toHaveValue('sample.cif')
  view.unmount()
  render(<EvidenceRecordList records={records} onOpen={onOpen} />)
  expect(screen.getAllByRole('button')).toHaveLength(2)
  const title = screen.getByRole('button', { name: 'Crystal system' })
  expect(title).toHaveTextContent('Crystal system')
  expect(title.querySelector('svg')).toBeNull()
  fireEvent.click(title)
  expect(onOpen).toHaveBeenLastCalledWith('system')
})
