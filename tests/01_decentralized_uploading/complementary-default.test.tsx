import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import MultiFileUploadPanel from '../../frontend/src/components/MultiFileUploadPanel'
import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn(), put: vi.fn() } }))
vi.mock('../../frontend/src/lib/classifications', () => ({
  loadClassificationCatalogs: vi.fn(async () => ({ material_families: [], structure_families: [], material_dimensionalities: [] })),
  canonicalMaterialKey: (s: string) => s.toLowerCase(),
}))
vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({ default: () => null }))
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); vi.clearAllMocks() })

it('上传 PDF 使用唯一默认流程，界面没有解析方案选择器', async () => {
  localStorage.setItem('auth_token', 'test-session')
  class Xhr {
    upload = {}; status = 200; onload?: () => void
    open() {} setRequestHeader() {} send() { this.onload?.() }
  }
  vi.stubGlobal('XMLHttpRequest', Xhr)
  const task = { task_id: 'test-task', files: [{ file_id: 'test-file' }] }
  vi.mocked(api.post).mockResolvedValue({ ok: true, data: task })
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: task })
  const created = vi.fn()
  const { container } = render(<LanguageProvider><MultiFileUploadPanel onCreated={created} /></LanguageProvider>)
  expect(screen.queryByText('解析方案')).not.toBeInTheDocument()
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['pdf'], 'paper.pdf', { type: 'application/pdf' })] } })
  fireEvent.click(screen.getByRole('button', { name: '开始上传并解析' }))
  await waitFor(() => expect(created).toHaveBeenCalled())
  expect(vi.mocked(api.post).mock.calls[0][1]).toMatchObject({ parser_profile: 'complementary' })
})

it('显示原文解析差异，来源文字作为安全文本渲染', async () => {
  vi.mocked(api.get).mockResolvedValue({ records: [], data: {}, space_groups: [] })
  render(<LanguageProvider><UploadTaskEditor taskId={'6'.repeat(32)} onSubmitted={vi.fn()} draftOverride={{
    paper: { title: 'Hydride', authors: [], paper_type: 'review', material_families: [], keywords_tags: [], methodology: [] },
    material_states: [], structure_candidates: [], classification_evidence: [], field_evidence: {},
    parsing_conflicts: [{ file_id: 'main', pdf_page: 3, kind: 'table', selected_text: 'Tc = 199 K',
      alternatives: [{ text: '<script>window.bad = true</script> Tc = 200 K' }] }],
  }} /></LanguageProvider>)
  fireEvent.click(await screen.findByText('查看来源差异'))
  expect(screen.getByText('Tc = 199 K')).toBeInTheDocument()
  expect(screen.getByText('<script>window.bad = true</script> Tc = 200 K')).toBeInTheDocument()
  expect(document.querySelector('script')).toBeNull()
})
