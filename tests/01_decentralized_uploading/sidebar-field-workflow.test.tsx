import '@testing-library/jest-dom/vitest'
import React from 'react'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {useEvidenceWorkflow} from '../../frontend/src/components/EvidenceWorkflow'
import {LanguageProvider} from '../../frontend/src/context/LanguageContext'
import {api} from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api',()=>({api:{get:vi.fn(),post:vi.fn(),del:vi.fn()}}))
const target={target:'upload' as const,target_id:'task'},key='a'.repeat(64)
const record={key,item_key:key,field:'paper.title',label:'标题',current_value:'Title',status:'uncertain' as const,reason:'待核对',evidences:[]}
let flow:ReturnType<typeof useEvidenceWorkflow>,value:string,reviewed:any,changeCurrent=false,release:(v:any)=>void
beforeEach(()=>{
 value='Title';reviewed=record;changeCurrent=false
 vi.mocked(api.post).mockImplementation(async path=>{
  if(path.endsWith('/jobs'))return {id:'job',status:'queued'} as never
  return {version:'global',records:[record],needs_check:true} as never
 })
 vi.mocked(api.get).mockImplementation(async path=>{
  if(path.includes('/field-detail'))return {record:reviewed,review_token:'token',approval_state:'ready'} as never
  if(path.includes('/field-input'))return {version:'local',field_token:'local',records:[record]} as never
  if(path.includes('/jobs/'))return new Promise(resolve=>{release=resolve})
  return {} as never
 })
})
afterEach(()=>{cleanup();vi.clearAllMocks()})
function Host(){
 const save=async()=>{
  // 保存完成的内部通知；同页用户不在遮罩下操作其他字段。
  if(changeCurrent)value='Changed'
  flow.invalidate(changeCurrent?'paper.title':'paper.year')
  return true
 }
 flow=useEvidenceWorkflow({target,getCurrentValue:()=>({value,field:'paper.title'}),saveCurrent:save,saveField:save})
 return <><button onClick={()=>flow.openIssue(key)}>打开字段</button>{flow.dialog}</>
}
async function start(){
 render(<LanguageProvider><Host/></LanguageProvider>)
 await waitFor(()=>expect(flow.records).toHaveLength(1))
 fireEvent.click(screen.getByText('打开字段'))
 await screen.findByRole('button',{name:'大模型核对',exact:true})
 fireEvent.click(screen.getByRole('button',{name:'大模型核对',exact:true}))
}
it('内部无关编辑通知和摘要刷新不会阻断当前字段核对',async()=>{
 await start()
 await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/jobs',expect.objectContaining({expected_field_token:'local',retry_keys:[key]})))
 await act(async()=>{await flow.restore(target)})
 reviewed={...record,status:'supported',reason:'原文支持当前值',stale:false,pending_review:false}
 await act(async()=>release({id:'job',status:'completed',records:[reviewed]}))
 await screen.findByText('核对通过（结果已保存）')
 expect(screen.getByText('原文支持当前值')).toBeVisible()
 expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith('/summary'))).toHaveLength(1)
})
it('真正当前字段变化仍拒绝启动',async()=>{
 changeCurrent=true
 await start()
 await screen.findAllByText(/保存期间内容又发生变化/)
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs'))).toBe(false)
})
