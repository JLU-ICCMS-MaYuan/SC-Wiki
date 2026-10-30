import { act, renderHook, waitFor, cleanup } from '@testing-library/react'
import { expect,it,afterEach,vi } from 'vitest'
import { api } from '../../frontend/src/lib/api'
import { useWorkdraftRefresh } from '../../frontend/src/components/WorkdraftRefresh'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn()}}))
afterEach(()=>{cleanup();vi.resetAllMocks()})
const target={target:'upload' as const,target_id:'isolated-refresh'}

it('载入期间的新侧栏输入使迟到整稿作废；焦点事件合并且不自动保存',async()=>{
 let inputVersion=0, revision=1, release!: (value:any)=>void
 const apply=vi.fn()
 vi.mocked(api.get).mockImplementation(async url=>{
  if(url.includes('/draft-revision'))return{revision,write_epoch:'same-cycle'}as never
  return new Promise(resolve=>{release=resolve})as never
 })
 const {result}=renderHook(()=>useWorkdraftRefresh(target,{
  enabled:true,busy:()=>false,dirty:()=>false,editVersion:()=>inputVersion,apply,
 }))
 await waitFor(()=>expect(api.get).toHaveBeenCalledTimes(1))
 revision=2
 await act(async()=>{window.dispatchEvent(new Event('focus'));document.dispatchEvent(new Event('visibilitychange'))})
 expect(vi.mocked(api.get).mock.calls.filter(([url])=>url.includes('/draft-revision'))).toHaveLength(2)
 await waitFor(()=>expect(result.current.available).toBe(true))
 let loading!: Promise<void>
 act(()=>{loading=result.current.load()})
 await waitFor(()=>expect(release).toBeDefined())
 inputVersion++
 await act(async()=>{release({draft:{paper:{title:'远程稿'}},revision:2,write_epoch:'same-cycle'});await loading})
 expect(apply).not.toHaveBeenCalled()
 expect(result.current.available).toBe(true)
 expect(api.post).not.toHaveBeenCalled()
})
it('冻结快照不检查更新，保存进行中拒绝载入',async()=>{
 const {unmount}=renderHook(()=>useWorkdraftRefresh(target,{
  enabled:false,busy:()=>true,dirty:()=>false,editVersion:()=>0,apply:vi.fn(),
 }))
 await act(async()=>window.dispatchEvent(new Event('focus')))
 expect(api.get).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled();unmount()
})
