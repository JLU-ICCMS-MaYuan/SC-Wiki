import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useEvidenceWorkflow } from '../../frontend/src/components/EvidenceWorkflow'
import { api } from '../../frontend/src/lib/api'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import { TextField } from '@mui/material'
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }))
const done = vi.fn()
const record = { key:'47', field:'records[47]', label:'SnHg Tc 4.29 K', status:'supported', reason:'原文支持', evidences:[{ file_id:'main',chunk_index:1,quote:'source' }] }
function Harness({target='paper'}:{target?:'upload'|'paper'}) { const flow=useEvidenceWorkflow();return <><button onClick={()=>void flow.run({target,target_id:'29'}).then(done)}>开始</button>{flow.dialog}</> }
beforeEach(()=>{
 vi.useFakeTimers();done.mockReset()
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('preflight') ? {version:'v1',needs_check:true,records:[record],sources:[]} as never : path.endsWith('save-draft') ? {version:'v2'} as never : {id:'job'} as never)
 vi.mocked(api.get).mockResolvedValue({status:'completed',records:[record]})
 vi.mocked(api.del).mockResolvedValue({})
})
afterEach(()=>{cleanup();vi.useRealTimers();vi.clearAllMocks()})

it('无核对记录的字段标签仍可查看空侧栏，不触发模型或保存', async () => {
  vi.mocked(api.post).mockResolvedValue({version:'empty',needs_check:false,records:[]})
  function Empty() {
    const f=useEvidenceWorkflow({target:{target:'upload',target_id:'empty'}})
    return <div data-evidence-scope="empty"><TextField label="期号" value="" onChange={()=>{}} />
      <EvidenceFieldMarkers records={f.records} scope="empty" onOpen={f.openIssue} onChange={f.invalidate}/>{f.dialog}</div>
  }
  await act(async()=>render(<Empty/>))
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'期号'})))
  expect(screen.getByText('暂无证据或建议')).toBeInTheDocument()
  expect(screen.queryByRole('button',{name:'完成',exact:true})).not.toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('已接受记录只在字段侧栏显示待提交状态，顶部不再堆放按钮', async () => {
  vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:false,records:[{...record,proposal_draft:{values:{},accepted:true,reason:'确认'}}]})
  function Accepted() {const f=useEvidenceWorkflow({target:{target:'paper',target_id:'29'}});return <>{f.dialog}</>}
  await act(async()=>render(<Accepted/>))
  expect(screen.queryByText(/已接受，待提交/)).not.toBeInTheDocument()
})

it('关闭右侧抽屉保留红框，重新打开保留理由且不调用模型', async () => {
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('preflight')
    ? { version:'v1', needs_check:false, records:[{...record,status:'unsupported',current_value:'4.29 K'}] } as never : {} as never)
  function MarkedForm() {
    const flow = useEvidenceWorkflow({target:{target:'paper',target_id:'29'}})
    return <div data-evidence-scope="test"><div data-issue-field="records[47]">4.29 K</div><EvidenceFieldMarkers records={flow.records} scope="test" onOpen={flow.openIssue} onChange={flow.invalidate}/>{flow.dialog}</div>
  }
  await act(async () => render(<MarkedForm/>))
  const trigger = screen.getByRole('button',{name:'SnHg Tc 4.29 K：查看来源核对（1）'})
  expect(trigger.closest('[data-issue-field]')).toHaveAttribute('data-evidence-problem','true')
  await act(async () => fireEvent.click(trigger))
  expect(screen.getByRole('dialog')).toHaveClass('MuiDrawer-paperAnchorRight')
  await act(async () => fireEvent.change(screen.getByLabelText('人工核对理由'),{target:{value:'核验全文'}}))
  await act(async () => fireEvent.click(screen.getByLabelText('关闭来源详情')))
  await act(async () => { await vi.advanceTimersByTimeAsync(300) })
  expect(trigger.closest('[data-issue-field]')).toHaveAttribute('data-evidence-problem','true')
  await act(async () => fireEvent.click(trigger))
  expect(screen.getByLabelText('人工核对理由')).toHaveValue('核验全文')
  expect(api.post).toHaveBeenCalledTimes(2)
  expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals',expect.objectContaining({key:'47',reason:'核验全文',accepted:false}))
})

it('修改字段使旧结果失效，不能用旧理由批准', async () => {
  vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:false,records:[{...record,status:'unsupported',resolution:'旧理由'}]})
  function Form() { const f=useEvidenceWorkflow({target:{target:'paper',target_id:'29'}});return <><button onClick={()=>f.invalidate('records[47]')}>修改</button><button onClick={()=>f.openIssue('47')}>查看</button>{f.dialog}</> }
  await act(async()=>render(<Form/>))
  await act(async()=>fireEvent.click(screen.getByText('修改')))
  await act(async()=>fireEvent.click(screen.getByText('查看')))
  expect(screen.getByText(/数据已修改/)).toBeInTheDocument()
  expect(screen.queryByText('确认原文并继续批准')).not.toBeInTheDocument()
})
async function start(){await act(async()=>{fireEvent.click(screen.getByText('开始'))})}
async function advance(){for(let i=0;i<3;i++)await act(async()=>{await vi.advanceTimersByTimeAsync(1000)})}
it('三秒内取消不创建模型任务',async()=>{render(<Harness/>);await start();expect(screen.getByText(/3 秒后/)).toBeInTheDocument();await act(async()=>fireEvent.click(screen.getByText('取消')));await advance();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(null)})
it('核对完成返回任务与版本，不发送审核请求',async()=>{render(<Harness/>);await start();await advance();expect(done).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith({evidence_job_id:'job',expected_evidence_version:'v1',evidence_resolutions:{}})})
it('后台已保存结果后无需浏览器再写草稿，返回任务版本',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',version:'v2',records:[record]});render(<Harness target="upload"/>);await start();await advance();expect(done).toHaveBeenCalledWith({evidence_job_id:'job',expected_evidence_version:'v2',evidence_resolutions:{}})})
it('上传语义疑点显示抽屉等待手动提交',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'unsupported'}]});render(<Harness target="upload"/>);await start();await advance();expect(done).toHaveBeenCalledWith(expect.objectContaining({evidence_job_id:'job'}))})
it('核对存在疑点只显示处理抽屉，完成不会自动批准',async()=>{
 vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'unsupported',reason:'4.29 K 是测量温度'}]})
 vi.mocked(api.post).mockImplementation(async (path,body)=>path.endsWith('preflight')?{version:'v1',needs_check:true,records:[record]} as never:path.endsWith('proposals')?{draft:body} as never:{id:'job'} as never)
 render(<Harness/>);await start();await advance()
 expect(done).toHaveBeenCalledTimes(1)
 expect(screen.queryByText('确认原文并继续批准')).not.toBeInTheDocument()
 await act(async()=>fireEvent.change(screen.getByLabelText('人工核对理由'),{target:{value:'对照完整原文人工判断'}}))
 await act(async()=>fireEvent.click(screen.getByText('完成')))
 expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals',expect.objectContaining({accepted:true,reason:'对照完整原文人工判断'}))
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/review'))).toBe(false)
})
it('没有有效出处不能点击完成',async()=>{vi.mocked(api.get).mockResolvedValue({status:'completed',records:[{...record,status:'missing',evidences:[]}]});render(<Harness/>);await start();await advance();expect(screen.getByText('完成')).toBeDisabled()})

it('管理员可对未核对项填写理由完成，连续输入合并且失败不循环报错', async () => {
 const unchecked = {...record,status:'unchecked',evidences:[],reason:'尚未核对'}
 let fail = true
 vi.mocked(api.post).mockImplementation(async (path, body) => {
  if(path.endsWith('preflight')) return {version:'v1',needs_check:true,records:[unchecked]} as never
  if(fail) throw new Error('保存暂不可用')
  return {draft:body} as never
 })
 function Form(){const f=useEvidenceWorkflow({target:{target:'paper',target_id:'29'}});return <><button onClick={()=>f.openIssue('47')}>查看</button>{f.dialog}</>}
 await act(async()=>render(<Form/>));await act(async()=>fireEvent.click(screen.getByText('查看')))
 expect(screen.getByText(/这项尚未完成来源核对/)).toBeInTheDocument()
 expect(screen.getByText('完成')).toBeDisabled()
 for(const value of ['根','根据','根据元素定义，Sn 只有一种元素']) await act(async()=>fireEvent.change(screen.getByLabelText('人工核对理由'),{target:{value}}))
 expect(api.post).toHaveBeenCalledTimes(1)
 await act(async()=>vi.advanceTimersByTimeAsync(500))
 expect(api.post).toHaveBeenCalledTimes(2)
 expect(screen.getByText(/输入已保留，自动重试已暂停/)).toBeInTheDocument()
 await act(async()=>fireEvent.change(screen.getByLabelText('人工核对理由'),{target:{value:'根据物理定义再次确认'}}))
 await act(async()=>vi.advanceTimersByTimeAsync(3000))
 expect(api.post).toHaveBeenCalledTimes(2)
 fail=false
 await act(async()=>fireEvent.click(screen.getByText('重试保存')))
 expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals',expect.objectContaining({reason:'根据物理定义再次确认',accepted:false}))
 await act(async()=>fireEvent.click(screen.getByText('完成')))
 expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals',expect.objectContaining({reason:'根据物理定义再次确认',accepted:true}))
 await act(async()=>vi.advanceTimersByTimeAsync(400))
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
 await act(async()=>fireEvent.click(screen.getByText('查看')))
 expect(screen.getByText('撤销接受并修改')).toBeInTheDocument()
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs')||path.endsWith('/review'))).toBe(false)
})
it('服务失败不提交并可重试',async()=>{vi.mocked(api.get).mockResolvedValue({status:'failed',error:{message:'模型服务异常'}});render(<Harness/>);await start();await advance();expect(screen.getByText('模型服务异常')).toBeInTheDocument();expect(done).not.toHaveBeenCalled()})
it('离页停止续提但后台继续持久保存',async()=>{vi.mocked(api.get).mockResolvedValue({status:'running'});const {unmount}=render(<Harness/>);await start();await advance();await act(async()=>unmount());expect(api.del).not.toHaveBeenCalled();expect(done).toHaveBeenCalledWith(null)})
it('缓存有效无需倒计时或调用模型',async()=>{vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:false,records:[record],sources:[]});render(<Harness target="upload"/>);await start();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledTimes(1)})
it('复用尚未落库的任务结果仍携带服务端任务身份',async()=>{vi.mocked(api.post).mockResolvedValue({job_id:'cached-job',version:'v1',needs_check:false,records:[record],sources:[]});render(<Harness target="upload"/>);await start();expect(api.post).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(expect.objectContaining({evidence_job_id:'cached-job'}))})
it('请求返回前离页也会取消迟到的后台任务',async()=>{
 let deliver!: (value: unknown) => void
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('preflight')?{version:'v1',needs_check:true,records:[record],sources:[]} as never:new Promise(resolve=>{deliver=resolve}) as never)
 const {unmount}=render(<Harness/>);await start();await advance();await act(async()=>unmount());await act(async()=>deliver({id:'late-job'}));expect(api.del).not.toHaveBeenCalled();expect(done).toHaveBeenCalledTimes(1);expect(done).toHaveBeenCalledWith(null)
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
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/jobs', { target: 'paper', target_id: '29', expected_version: 'v1', purpose: 'review_all' })
})

it('上传没有出处时只提示重新查找或修改记录，不要求手选证据', async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 'completed', records: [{ ...record, status: 'missing', evidences: [] }] })
  render(<Harness target="upload" />)
  await start()
  await advance()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.getByText('让系统重新查找')).toBeInTheDocument()
  expect(screen.getByText('完成')).toBeDisabled()
})

it('重新查找绕过旧疑点缓存，找到证据后仍等待手动提交', async () => {
  vi.mocked(api.post).mockImplementation(async path => path.endsWith('preflight')
    ? { job_id: 'old-job', version: 'v1', needs_check: false, records: [{ ...record, status: 'missing', evidences: [] }] } as never
    : { id: 'new-job' } as never)
  render(<Harness target="upload" />)
  await start()
  expect(done).toHaveBeenCalledTimes(1)
  await act(async () => fireEvent.click(screen.getByText('让系统重新查找')))
  expect(screen.getByText(/3 秒后/)).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledTimes(2)
  await advance()
  expect(api.post).toHaveBeenCalledTimes(3)
  expect(api.post).not.toHaveBeenCalledWith('/api/rag/evidence/jobs/new-job/save-draft')
  expect(done).toHaveBeenCalledTimes(1)
  expect(api.get).toHaveBeenCalledWith('/api/rag/evidence/jobs/new-job')
})

it('重新查找的倒计时仍可取消，不创建任务或自动续提', async () => {
  vi.mocked(api.post).mockResolvedValue({ job_id: 'old-job', version: 'v1', needs_check: false, records: [{ ...record, status: 'unsupported' }] })
  render(<Harness target="upload" />)
  await start()
  await act(async () => fireEvent.click(screen.getByText('让系统重新查找')))
  await act(async () => fireEvent.click(screen.getByText('取消')))
  await advance()
  expect(api.post).toHaveBeenCalledTimes(2)
  expect(done).toHaveBeenCalledTimes(1)
  expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs'))).toBe(false)
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

it('按后台完成组数推进百分比，显示当前组且完成后结束进度', async () => {
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


it('提交门禁拒绝未核对内容且绝不启动模型', async () => {
  vi.mocked(api.post).mockResolvedValue({version:'v1',needs_check:true,records:[{...record,status:'unchecked'}]})
  function Gate(){const f=useEvidenceWorkflow();return <><button onClick={()=>void f.gate({target:'paper',target_id:'29'}).then(done)}>提交</button>{f.dialog}</>}
  render(<Gate/>);await act(async()=>fireEvent.click(screen.getByText('提交')))
  expect(done).toHaveBeenCalledWith(null)
  expect(api.post).toHaveBeenCalledTimes(1)
  expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/preflight',{target:'paper',target_id:'29'})
  expect(screen.getByText(/提交不会自动启动模型/)).toBeInTheDocument()
})

it('建议可编辑、持久接受和撤销，保存失败不显示完成', async () => {
  const candidate={...record,status:'unsupported',current_value:'4.29 K',editable_fields:[{path:'',label:'建议内容',value:'4.29 K',schema:{type:'string'}}],proposal:{values:{'':'测量温度为 4.29 K'},supported:true,evidences:record.evidences}}
  vi.mocked(api.post).mockImplementation(async(path,body)=>path.endsWith('preflight')?{version:'v1',needs_check:false,records:[candidate]} as never:{draft:body} as never)
  function Form(){const f=useEvidenceWorkflow({target:{target:'paper',target_id:'29'}});return <><button onClick={()=>f.openIssue('47')}>查看</button>{f.dialog}</>}
  await act(async()=>render(<Form/>));await act(async()=>fireEvent.click(screen.getByText('查看')))
  expect(screen.getByLabelText('建议内容')).toHaveValue('测量温度为 4.29 K')
  await act(async()=>fireEvent.change(screen.getByLabelText('建议内容'),{target:{value:'在 4.29 K 下测量'}}))
  await act(async()=>vi.advanceTimersByTimeAsync(500))
  expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/proposals',expect.objectContaining({values:{'':'在 4.29 K 下测量'},accepted:false}))
  vi.mocked(api.post).mockRejectedValueOnce(new Error('保存失败'))
  await act(async()=>fireEvent.click(screen.getByText('完成')))
  expect(screen.getByText(/保存失败/)).toBeInTheDocument()
  expect(screen.queryByText('撤销接受并修改')).not.toBeInTheDocument()
  await act(async()=>fireEvent.click(screen.getByText('完成')))
  await act(async()=>vi.advanceTimersByTimeAsync(400))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await act(async()=>fireEvent.click(screen.getByText('查看')))
  expect(screen.getByText('撤销接受并修改')).toBeInTheDocument()
  await act(async()=>fireEvent.click(screen.getByText('撤销接受并修改')))
  expect(screen.getByLabelText('建议内容')).not.toBeDisabled()
  expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs')||path.endsWith('/review'))).toBe(false)
})

it('提交先准备已接受补丁，保存失败时不绑定；成功后只读恢复', async () => {
 const save=vi.fn().mockResolvedValue(false)
 vi.mocked(api.post).mockImplementation(async path=>path.endsWith('/preflight')?{version:'v1',needs_check:false,records:[record]} as never:path.endsWith('/prepare')?{preparation_id:'p1',patches:[{field:'paper.summary',values:{'':'new'}}]} as never:{} as never)
 function Form(){const f=useEvidenceWorkflow();return <button onClick={()=>void f.applyAccepted({target:'paper',target_id:'29'},save).then(done)}>提交修改</button>}
 render(<Form/>);await act(async()=>fireEvent.click(screen.getByText('提交修改')))
 expect(save).toHaveBeenCalledWith([{field:'paper.summary',values:{'':'new'}}],'p1',undefined)
 expect(api.post).not.toHaveBeenCalledWith('/api/rag/evidence/proposals/finalize',expect.anything())
 expect(done).toHaveBeenCalledWith(false)
 save.mockResolvedValue(true)
 await act(async()=>fireEvent.click(screen.getByText('提交修改')))
 expect(api.post).toHaveBeenCalledWith('/api/rag/evidence/proposals/finalize',{target:'paper',target_id:'29',preparation_id:'p1'})
 expect(api.post).toHaveBeenLastCalledWith('/api/rag/evidence/preflight',{target:'paper',target_id:'29'})
 expect(vi.mocked(api.post).mock.calls.some(([path])=>path.endsWith('/jobs')||path.endsWith('/review'))).toBe(false)
})
