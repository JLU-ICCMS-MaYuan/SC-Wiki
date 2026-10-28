import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { api } from '../../frontend/src/lib/api'
import type { UploadDraft } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn() } }))
vi.mock('../../frontend/src/lib/classifications', async original => ({
  ...await original<typeof import('../../frontend/src/lib/classifications')>(),
  loadClassificationCatalogs: vi.fn(async () => ({ material_families: [{id:1,name:'氢基超导体'}], structure_families: [], material_dimensionalities: [] })),
}))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks() })
it.each([false, true])('实际提交确认展示具体 DOI 差异并绑定版本，继续=%s', async accepted => {
  const message = '上传文件的身份信息存在以下差异：\n\nDOI：\npaper.pdf：10.1000/main\nSI.pdf：10.1000/other'
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(accepted)
  const submitted = vi.fn(), calls: unknown[] = []
  vi.mocked(api.get).mockResolvedValue({items:[],jobs:[],records:[],version:'v',space_groups:[]} as never)
  vi.mocked(api.put).mockResolvedValue({ok:true} as never)
  vi.mocked(api.post).mockImplementation(async (path, body: any) => {
    if (path.endsWith('/submit')) {
      calls.push(body)
      if (!body.consistency_acknowledged) throw Object.assign(new Error(message), {code:'consistency_ack_required',consistencyVersion:'current-files'})
      return {ok:true,paper_id:99} as never
    }
    return {status:'completed',version:'v',records:[],needs_check:false} as never
  })
  const draft = {paper:{title:'Example review',year:2026,authors:[],paper_type:'review',superconductor_kind:'unknown',
    material_families:[{id:1,name:'氢基超导体',status:'confirmed'}],keywords_tags:[],methodology:[]},material_states:[],structure_candidates:[],field_evidence:{}} as unknown as UploadDraft
  render(<MemoryRouter><UploadTaskEditor taskId="isolated" draftOverride={draft} onSubmitted={submitted}/></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button',{name:'提交审核'}))
  await waitFor(() => expect(confirm).toHaveBeenCalled(),{timeout:10000})
  expect(confirm.mock.calls[0][0]).toContain(message)
  expect(confirm.mock.calls[0][0]).not.toContain('标题、DOI 或作者')
  if (accepted) {
    await waitFor(() => expect(submitted).toHaveBeenCalledWith(99))
    expect(calls[1]).toMatchObject({consistency_acknowledged:true,consistency_version:'current-files'})
  } else {
    expect(calls).toHaveLength(1);expect(submitted).not.toHaveBeenCalled()
  }
})
