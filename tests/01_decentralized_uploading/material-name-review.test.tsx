import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import MaterialStatesEditor from '../../frontend/src/components/MaterialStatesEditor'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { currentEvidenceField, evidenceFieldAffected } from '../../frontend/src/lib/evidenceFields'
import { api } from '../../frontend/src/lib/api'
import type { DraftMaterialState } from '../../frontend/src/lib/paperProcessing'
import { collectPropertyRows, collectStructures } from '../../frontend/src/lib/paperDetailView'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
vi.mock('../../frontend/src/components/PropertyModuleEditor', () => ({ default: () => null }))
vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it.each([['Tin', '', 'Tin'], ['', 'Sn', 'Sn'], ['Tin', 'Sn', 'Tin（Sn）']])('公开详情使用材料名和化学式：%s / %s', (material_name, material, label) => {
  const paper = {material_states:[{material_name, material,
    property_modules:[{module_code:'superconductive_properties', records:[{record_key:'tc', record_type:'measured_tc', property_code:'tc', value_number:3.7, canonical_unit:'K'}]}],
    structures:[{structure_text:'data_test',structure_format:'cif'}]}]}
  expect(collectPropertyRows(paper)[0].material).toBe(label)
  expect(collectStructures(paper)[0].material).toBe(label)
})

const formula: EvidenceRecord = {key:'formula', item_key:'formula', state_key:'tin', field:'material_states[0].material',
  label:'材料化学式', current_value:'Sn', status:'uncertain', reason:'论文只写 Tin', evidences:[],
  editable_fields:[{path:'material_states[0].material', label:'材料化学式', value:'Sn', schema:{type:'string'}}]}
const name: EvidenceRecord = {...formula, key:'name', item_key:'name', field:'material_states[0].material_name',
  label:'材料名', current_value:'Tin', editable_fields:[]}

function Editor({save}: {save: (states: DraftMaterialState[]) => Promise<boolean>}) {
  const [states, setStates] = useState<DraftMaterialState[]>([{state_key:'tin', material_name:'Tin', material:'Sn', property_modules:[]}])
  const flow = useEvidenceWorkflow({target:{target:'paper', target_id:'fixture'}, getCurrentValue:r=>currentEvidenceField(r, {}, states), saveCurrent:()=>save(states)})
  return <div data-evidence-scope="name-test">
    <MaterialStatesEditor states={states} onChange={setStates} onScientificEdit={flow.invalidate} catalogs={null} />
    <EvidenceFieldMarkers records={flow.records} scope="name-test" onOpen={flow.openIssue} onChange={flow.invalidate} />
    {flow.dialog}<output data-testid="states">{JSON.stringify(states)}</output>
  </div>
}

it('材料名修改只使对应状态及派生项失效', () => {
  expect(evidenceFieldAffected(formula, 'material_states[0].material_name')).toBe(true)
  expect(evidenceFieldAffected({...formula, field:'material_states[1].material'}, 'material_states[0].material_name')).toBe(false)
})

it('重新查找先保存，删除的化学式不再作为模型重查目标', async () => {
  let records = [formula]
  const save = vi.fn(async () => { records = []; return true })
  vi.mocked(api.post).mockImplementation(async (path) => {
    if (path.endsWith('preflight')) return {version:'v2', records, needs_check:false}
    throw new Error(`已删除字段不应请求 ${path}`)
  })
  render(<Editor save={save} />)
  const user = userEvent.setup()
  await screen.findByRole('button', {name:'化学式'})
  await user.clear(screen.getByLabelText('化学式'))
  await user.click(screen.getByRole('button', {name:'化学式'}))
  await user.click(screen.getByRole('button', {name:'让系统重新查找'}))
  await waitFor(()=>expect(save).toHaveBeenCalledTimes(1))
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining('/jobs'), expect.anything())
})

it('清空化学式后保留材料名，失败保留理由，成功移除旧项再确认当前名称', async () => {
  let fail = true
  let version = 'v1'
  let records = [formula, name]
  vi.mocked(api.post).mockImplementation(async (path, body: any) => {
    if (path.endsWith('preflight')) return {version, records, needs_check:true}
    if (path.endsWith('proposals')) { expect(body.key).toBe('name'); expect(body.expected_version).toBe('v2'); return {draft:body} }
    throw new Error(`意外请求 ${path}`)
  })
  const save = vi.fn(async (states: DraftMaterialState[]) => {
    if (fail) return false
    expect(states[0]).toMatchObject({material_name:'Tin',material:''})
    version = 'v2'; records = [{...name, stale:true}]; return true
  })
  render(<Editor save={save} />)
  const user = userEvent.setup()
  await screen.findByRole('button', {name:'化学式'})
  const inputs = screen.getAllByRole('textbox')
  expect(inputs.indexOf(screen.getByLabelText('材料名'))).toBeLessThan(inputs.indexOf(screen.getByLabelText('化学式')))
  expect(screen.getByText('Tin（Sn）')).toBeVisible()
  await user.clear(screen.getByLabelText('化学式'))
  await user.click(screen.getByRole('button', {name:'化学式'}))
  const drawer = screen.getByRole('dialog')
  expect(within(drawer).getByText('未填写（未知）')).toBeVisible()
  expect(within(drawer).getByLabelText('材料化学式 · 修改前的值')).toBeDisabled()
  await user.type(screen.getByLabelText('人工核对理由'), '论文未提供化学式，因此清空')
  await user.click(screen.getByRole('button', {name:'完成'}))
  expect(await screen.findByText(/当前编辑尚未保存成功/)).toBeVisible()
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('论文未提供化学式，因此清空')
  fail = false
  await user.click(screen.getByRole('button', {name:'完成'}))
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining('/proposals'), expect.anything())
  await user.click(screen.getByRole('button', {name:'材料名'}))
  await user.type(screen.getByLabelText('人工核对理由'), '原文明确标注 Tin')
  await user.click(screen.getByRole('button', {name:'完成'}))
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/proposals'), expect.objectContaining({expected_version:'v2',key:'name',reason:'原文明确标注 Tin',accepted:true})))
  expect(api.post).not.toHaveBeenCalledWith(expect.stringMatching(/jobs|review$/), expect.anything())
})
