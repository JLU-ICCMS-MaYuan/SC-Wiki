import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
const done = vi.fn()
const record = { key:'47', field:'records[47]', label:'SnHg Tc 4.29 K', status:'supported', reason:'原文支持', evidences:[{ file_id:'main',chunk_index:1,quote:'source' }] }
function Harness({target='paper'}:{target?:'upload'|'paper'}) { const flow=useEvidenceWorkflow();return <><button onClick={()=>void flow.run({target,target_id:'29'}).then(done)}>开始</button>{flow.dialog}</> }
beforeEach(()=>{
 vi.useFakeTimers();done.mockReset()
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('preflight') ? {version:'v1',needs_check:true,records:[record],sources:[]} as never : {id:'job'} as never)
 vi.mocked(api.get).mockResolvedValue({status:'completed',records:[record]})
 vi.mocked(api.del).mockResolvedValue({})
})
afterEach(()=>{cleanup();vi.useRealTimers();vi.clearAllMocks()})
async function start(){await act(async()=>{fireEvent.click(screen.getByText('开始'))})}
async function advance(){for(let i=0;i<3;i++)await act(async()=>{await vi.advanceTimersByTimeAsync(1000)})}
it('三秒内取消不创建模型任务',async()=>{render(<Harness/>);await start();expect(screen.getByText(/3 秒后/)).toBeInTheDocument();await act(async()=>fireEvent.click(screen.getByText('取消')));await advance();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(null)})
it('成功只续提一次并带任务与版本',async()=>{render(<Harness/>);await start();await advance();expect(done).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith({evidence_job_id:'job',expected_evidence_version:'v1',evidence_resolutions:{}})})
it('上传语义疑点自动进入待审',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'unsupported'}]});render(<Harness target="upload"/>);await start();await advance();expect(done).toHaveBeenCalledWith(expect.objectContaining({evidence_job_id:'job'}))})
it('审核语义疑点必须逐条填写人工理由',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'unsupported',reason:'4.29 K 是测量温度'}]});render(<Harness/>);await start();await advance();expect(done).not.toHaveBeenCalled();expect(screen.queryByText('确认原文并继续批准')).not.toBeInTheDocument();fireEvent.change(screen.getByLabelText('人工核对理由（此条必填）'),{target:{value:'对照完整原文人工判断'}});await act(async()=>fireEvent.click(screen.getByText('确认原文并继续批准')));expect(done).toHaveBeenCalledWith(expect.objectContaining({evidence_resolutions:{'47':'对照完整原文人工判断'}}))})
it('没有有效出处不可人工绕过',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'missing',evidences:[]}]});render(<Harness/>);await start();await advance();expect(done).not.toHaveBeenCalled();expect(screen.queryByText('确认原文并继续批准')).not.toBeInTheDocument()})
it('服务失败不提交并可重试',async()=>{vi.mocked(api.get).mockResolvedValue({status:'failed',error:{message:'模型服务异常'}});render(<Harness/>);await start();await advance();expect(screen.getByText('模型服务异常')).toBeInTheDocument();expect(done).not.toHaveBeenCalled()})
it('离页取消后台任务且不续提',async()=>{vi.mocked(api.get).mockResolvedValue({status:'running'});const {unmount}=render(<Harness/>);await start();await advance();await act(async()=>unmount());expect(api.del).toHaveBeenCalledWith('/api/rag/evidence/jobs/job');expect(done).toHaveBeenCalledWith(null)})
it('缓存有效无需倒计时或调用模型',async()=>{vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:false,records:[record],sources:[]});render(<Harness/>);await start();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledTimes(1)})
it('复用尚未落库的任务结果仍携带服务端任务身份',async()=>{vi.mocked(api.post).mockResolvedValue({job_id:'cached-job',version:'v1',needs_check:false,records:[record],sources:[]});render(<Harness/>);await start();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(expect.objectContaining({evidence_job_id:'cached-job'}))})
it('请求返回前离页也会取消迟到的后台任务',async()=>{
 let deliver!: (value: unknown) => void
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('preflight')?{version:'v1',needs_check:true,records:[record],sources:[]} as never:new Promise(resolve=>{deliver=resolve}) as never)
 const {unmount}=render(<Harness/>);await start();await advance();await act(async()=>unmount());await act(async()=>deliver({id:'late-job'}));expect(api.del).toHaveBeenCalledWith('/api/rag/evidence/jobs/late-job');expect(done).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(null)
})
