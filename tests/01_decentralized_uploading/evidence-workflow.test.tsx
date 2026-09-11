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

it('已有原文直接用于裁决，不要求选择片段或编辑引句', async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 'completed', records: [{ ...record, status: 'unsupported' }] })
  render(<Harness />)
  await start()
  await advance()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.getAllByRole('textbox')).toHaveLength(1)
  expect(screen.getByText('查看系统找到的原文').closest('details')).not.toHaveAttribute('open')
  expect(screen.queryByText(/片段 2|文件 main/)).not.toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/jobs', { target: 'paper', target_id: '29', expected_version: 'v1' })
})

it('上传没有出处时只提示重新查找或修改记录，不要求手选证据', async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 'completed', records: [{ ...record, status: 'missing', evidences: [] }] })
  render(<Harness target="upload" />)
  await start()
  await advance()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.getByText('让系统重新查找')).toBeInTheDocument()
  expect(done).not.toHaveBeenCalled()
})

it('重新查找绕过旧疑点缓存，找到证据后自动续提一次', async () => {
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('preflight')
    ? { job_id: 'old-job', version: 'v1', needs_check: false, records: [{ ...record, status: 'missing', evidences: [] }] } as never
    : { id: 'new-job' } as never)
  render(<Harness target="upload" />)
  await start()
  expect(done).not.toHaveBeenCalled()
  await act(async () => fireEvent.click(screen.getByText('让系统重新查找')))
  expect(screen.getByText(/3 秒后/)).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(2)
  await advance()
  expect(api.post).toHaveBeenCalledTimes(3)
  expect(done).toHaveBeenCalledTimes(1)
  expect(done).toHaveBeenCalledWith(expect.objectContaining({ evidence_job_id: 'new-job' }))
})

it('重新查找的倒计时仍可取消，不创建任务或自动续提', async () => {
  vi.mocked(api.post).mockResolvedValue({ job_id: 'old-job', version: 'v1', needs_check: false, records: [{ ...record, status: 'unsupported' }] })
  render(<Harness />)
  await start()
  await act(async () => fireEvent.click(screen.getByText('让系统重新查找')))
  await act(async () => fireEvent.click(screen.getByText('取消')))
  await advance()
  expect(api.post).toHaveBeenCalledTimes(2)
  expect(done).toHaveBeenCalledTimes(1)
  expect(done).toHaveBeenCalledWith(null)
})

it('排队显示动态进度条和持续更新的等待时间，不伪造百分比', async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 'queued' })
  render(<Harness />)
  await start()
  await advance()
  expect(screen.getByRole('progressbar', { name: '原文核对进度' })).not.toHaveAttribute('aria-valuenow')
  expect(screen.getByRole('status')).toHaveTextContent('正在排队')
  await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
  expect(screen.getByText('已等待 0 分 5 秒')).toBeInTheDocument()
  await act(async () => fireEvent.click(screen.getByText('取消')))
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  expect(done).toHaveBeenCalledWith(null)
})

it('按后台完成组数推进百分比，显示当前组且完成后续提', async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 'running', completed_batches: 0, total_batches: 2, current_batch: 1 })
  render(<Harness />)
  await start()
  await advance()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  expect(screen.getByText('正在核对第 1/2 组原文…')).toBeInTheDocument()
  vi.mocked(api.get).mockResolvedValue({ status: 'running', completed_batches: 1, total_batches: 2, current_batch: 2 })
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
  expect(screen.getByText('已核对 1/2 组原文 · 50%')).toBeInTheDocument()
  expect(screen.getByText('正在核对第 2/2 组原文…')).toBeInTheDocument()
  vi.mocked(api.get).mockResolvedValue({ status: 'completed', records: [record], completed_batches: 2, total_batches: 2 })
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(done).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})
