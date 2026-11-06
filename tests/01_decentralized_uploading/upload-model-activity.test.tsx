import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import UploadModelActivity from '../../frontend/src/components/UploadModelActivity'
import type { UploadTaskState } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/context/LanguageContext', () => ({useLanguage: () => ({t: (key: string, params?: Record<string, unknown>) => key + (params ? JSON.stringify(params) : '')})}))
afterEach(() => {cleanup();vi.unstubAllGlobals()})
const task: UploadTaskState={task_id:'a'.repeat(32),status:'reading',stage:'extracting',stage_index:2,stage_total:5,processing_status:'processing',completed_chunks:0,total_chunks:0,model_activity:{status:'retry_wait',phase:'structure_reading',attempt:7,error:{status_code:503,message:'service unavailable',request_id:'req-7',output_started:false},retry_at:Date.now()/1000+20}}
it('shows real error and posts pause once; displays resume after reread',async()=>{
  const updated=vi.fn()
  const fetch=vi.fn(async()=>new Response(JSON.stringify({ok:true,data:{...task,status:'paused',processing_status:'paused'}}),{headers:{'Content-Type':'application/json'}}))
  vi.stubGlobal('fetch',fetch)
  const view=render(<UploadModelActivity task={task} onUpdated={updated} onRetry={vi.fn()} onManual={vi.fn()} />)
  expect(screen.getByText(/service unavailable/)).toBeVisible()
  expect(screen.getByText(/req-7/)).toBeVisible()
  fireEvent.click(screen.getByRole('button',{name:'upload.stopAndKeep'}))
  await waitFor(()=>expect(updated).toHaveBeenCalledOnce())
  expect(String(fetch.mock.calls[0][0])).toContain(`/api/upload-tasks/${task.task_id}/pause`)
  view.rerender(<UploadModelActivity task={{...task,status:'paused',processing_status:'paused'}} onUpdated={updated} onRetry={vi.fn()} onManual={vi.fn()} />)
  expect(screen.queryByRole('button',{name:'upload.stopAndKeep'})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'upload.continueParsing'}))
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2))
  expect(String(fetch.mock.calls[1][0])).toContain('/resume')
})
it('keeps paused controls and error when resume fails',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:{message:'当前草稿已变化'}}),{status:409,headers:{'Content-Type':'application/json'}})))
  const updated=vi.fn()
  render(<UploadModelActivity task={{...task,status:'paused',processing_status:'paused'}} onUpdated={updated} onRetry={vi.fn()} onManual={vi.fn()} />)
  fireEvent.click(screen.getByRole('button',{name:'upload.continueParsing'}))
  await waitFor(()=>expect(screen.getByText('当前草稿已变化')).toBeVisible())
  expect(updated).not.toHaveBeenCalled()
  expect(screen.getByRole('button',{name:'upload.continueParsing'})).toBeEnabled()
})
it('ignores a completed action after the target task changes',async()=>{
  let finish!: (response: Response) => void
  vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{finish=resolve})))
  const updated=vi.fn()
  const view=render(<UploadModelActivity task={task} onUpdated={updated} onRetry={vi.fn()} onManual={vi.fn()} />)
  fireEvent.click(screen.getByRole('button',{name:'upload.stopAndKeep'}))
  view.rerender(<UploadModelActivity task={{...task,task_id:'b'.repeat(32)}} onUpdated={updated} onRetry={vi.fn()} onManual={vi.fn()} />)
  finish(new Response(JSON.stringify({ok:true,data:{...task,status:'paused'}}),{headers:{'Content-Type':'application/json'}}))
  await new Promise(resolve=>setTimeout(resolve,20))
  expect(updated).not.toHaveBeenCalled()
})
it('loads older real process records only on explicit request',async()=>{
  const history=Array.from({length:100},(_,index)=>({status:'requesting',phase:'structure_reading',updated_at:index+2,attempt:index+1}))
  const fetch=vi.fn(async()=>new Response(JSON.stringify({ok:true,data:{events:[{status:'retry_wait',phase:'workflow_selection',updated_at:1,error:{message:'earlier failure',request_id:'earlier-request'}}],has_more:false}}),{headers:{'Content-Type':'application/json'}}))
  vi.stubGlobal('fetch',fetch)
  render(<UploadModelActivity task={{...task,model_activity:{...task.model_activity!,history}}} onUpdated={vi.fn()} onRetry={vi.fn()} onManual={vi.fn()} />)
  expect(fetch).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('upload.modelHistory'))
  fireEvent.click(await screen.findByRole('button',{name:'upload.modelEarlier'}))
  await waitFor(()=>expect(screen.getByText(/earlier failure/)).toBeVisible())
  expect(String(fetch.mock.calls[0][0])).toContain('/model-activity?before=2')
  expect(screen.queryByRole('button',{name:'upload.modelEarlier'})).not.toBeInTheDocument()
})
