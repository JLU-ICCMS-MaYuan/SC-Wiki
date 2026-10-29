import { beforeEach, expect, it, vi } from 'vitest'
import { createFieldDraftSaver } from '../../frontend/src/lib/fieldDrafts'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),patch:vi.fn()}}))
const original={paper:{title:'old',year:2025},material_states:[{state_key:'s',pressure_value_gpa:150,
  property_modules:[{module_key:'m',records:[{record_key:'r',value_kind:'number',value_number:220,value_raw:'220',
    payload:{parameters:{mu_star:.13}}}]}]}]}
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.get).mockResolvedValue({version:'v1',draft:structuredClone(original)})
  vi.mocked(api.patch).mockResolvedValue({version:'v2',changed:true})})

it('仅保存当前字段，不推进其他输入基线；随后全表保存仍提交其差异',async()=>{
  const saver=createFieldDraftSaver({target:'upload',target_id:'task'})
  saver.initialize(original)
  const edited=structuredClone(original);edited.paper.title='new'
  edited.material_states[0].property_modules[0].records[0].payload.parameters.mu_star=.1
  await saver.saveField(edited,'material_states[0].property_modules[0].records[0].payload.parameters.mu_star')
  const first=vi.mocked(api.patch).mock.calls[0][1] as any
  expect(first.changes).toHaveLength(1)
  expect(first.changes[0].path.at(-1)).toBe('mu_star')
  expect(first.changes[0].value).toBe(.1)
  expect(first.field_scope).toBe(true)
  expect(saver.hasChanges(edited)).toBe(true)
  await saver.save(edited)
  expect((vi.mocked(api.patch).mock.calls[1][1] as any).changes).toEqual([{path:['paper','title'],before:'old',value:'new'}])
})

it('同值字段零请求，失败不推进基线且可重试',async()=>{
  const saver=createFieldDraftSaver({target:'paper',target_id:'7'});saver.initialize(original)
  await saver.saveField(original,'paper.title')
  expect(api.get).not.toHaveBeenCalled();expect(api.patch).not.toHaveBeenCalled()
  const edited={...original,paper:{...original.paper,title:'changed'}}
  vi.mocked(api.patch).mockRejectedValueOnce(new Error('network'))
  await expect(saver.saveField(edited,'paper.title')).rejects.toThrow('network')
  await saver.saveField(edited,'paper.title')
  expect((vi.mocked(api.patch).mock.calls[1][1] as any).changes[0].before).toBe('old')
})

it('共享参数保存对应组的同一字段，不保存另一点的未提交 μ*',async()=>{
  const start=structuredClone(original) as any
  const row=start.material_states[0].property_modules[0].records[0]
  row.payload.parameters.lambda_ep=2.69;row.payload.tc_group={version:1,group_key:'g',method_key:'m'}
  start.material_states[0].property_modules[0].records.push({...structuredClone(row),record_key:'r2'})
  const changed=structuredClone(start)
  changed.material_states[0].property_modules[0].records.forEach((r:any)=>{r.payload.parameters.lambda_ep=3})
  changed.material_states[0].property_modules[0].records[1].payload.parameters.mu_star=.1
  const saver=createFieldDraftSaver({target:'upload',target_id:'task'});saver.initialize(start)
  await saver.saveField(changed,'material_states[0].property_modules[0].records[0].payload.parameters.lambda_ep')
  expect((vi.mocked(api.patch).mock.calls[0][1] as any).changes.map((c:any)=>c.path.at(-1))).toEqual(['lambda_ep','lambda_ep'])
  await saver.save(changed)
  expect((vi.mocked(api.patch).mock.calls[1][1] as any).changes.map((c:any)=>c.path.at(-1))).toEqual(['mu_star'])
})
