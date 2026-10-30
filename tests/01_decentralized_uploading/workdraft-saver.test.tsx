import { expect, it, vi } from 'vitest'
import { fieldChanges, createFieldDraftSaver } from '../../frontend/src/lib/fieldDrafts'
import { api } from '../../frontend/src/lib/api'

it('删除与重排只传稳定操作，保留未修改旧值', () => {
  const old = [{ record_key: 'a', value_number: 1 }, { record_key: 'b', value_number: 2 }]
  expect(fieldChanges(old, [old[1]], ['material_states'])).toEqual([
    { op: 'remove_item', path: ['material_states'], identity: { key: 'record_key', value: 'a' } }])
  expect(fieldChanges(old, [...old].reverse(), ['material_states'])).toEqual([
    { op: 'reorder', path: ['material_states'], key: 'record_key', order: ['b', 'a'] }])
})

it('首次新增稳定列表使用插入；在途新输入留待下次保存，无变化零请求', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({version:'v1'})
  let resolve!: (value:any) => void
  const patch = vi.spyOn(api, 'patch').mockImplementationOnce(() => new Promise(r => {resolve=r})).mockResolvedValue({version:'v3'})
  const saver = createFieldDraftSaver({target:'upload',target_id:'isolated'})
  const before = {paper:{title:'a'},material_states:[]}
  saver.initialize(before)
  await saver.save(before)
  expect(get).not.toHaveBeenCalled()
  expect(patch).not.toHaveBeenCalled()
  const next = structuredClone(before); next.paper.title = 'b'
  const saving = saver.save(next)
  await vi.waitFor(() => expect(patch).toHaveBeenCalledTimes(1))
  next.paper.title = 'c'
  resolve({version:'v2',changed:true}); await saving
  expect(saver.hasChanges(next)).toBe(true)
  await saver.save(next)
  expect(patch.mock.calls[1][1]).toMatchObject({changes:[{path:['paper','title'],before:'b',value:'c'}]})
  expect(fieldChanges([], [{state_key:'s'}], ['material_states'])).toEqual([
    {op:'insert',path:['material_states'],key:'state_key',after:null,value:{state_key:'s'}}])
  vi.restoreAllMocks()
})
