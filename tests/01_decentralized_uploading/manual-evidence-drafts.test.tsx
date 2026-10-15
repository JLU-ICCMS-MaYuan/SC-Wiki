import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import ManualEvidenceSection from '../../frontend/src/components/ManualEvidenceSection'
import { createManualEvidenceDrafts, manualDraftKey } from '../../frontend/src/lib/manualEvidenceDrafts'
import { currentEvidenceField } from '../../frontend/src/lib/evidenceFields'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn(), download: vi.fn() } }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })
const record = { key: 'title', item_key: 'a'.repeat(64), field: 'paper.title', label: '标题', current_value: '人工标题', status: 'supported' as const, reason: '', evidences: [] }
const target = { target: 'upload' as const, target_id: 'task' }
const empty = { changed: true, status: 'draft', reason: '', no_evidence_reason: '', items: [] }

it('数值未变但压强等条件改变时，不复用旧物性理由；其他物性改动不影响身份', () => {
  const scientific = { ...record, state_key: 'Sn', module_key: 'tc', record_key: 'r', field: 'material_states[0].property_modules[0].records[0]' }
  const states = [{ state_key: 'Sn', material: 'Sn', pressure_value_gpa: 1, property_modules: [{ module_key: 'tc', records: [{ record_key: 'r', value_number: 3.7 }, { record_key: 'other', value_number: 4 }] }] }]
  const identity = () => manualDraftKey(target, scientific, currentEvidenceField(scientific, {}, states)?.manualValue)
  const original = identity()
  states[0].property_modules[0].records[1].value_number = 8
  expect(identity()).toBe(original)
  states[0].pressure_value_gpa = 2
  expect(identity()).not.toBe(original)
})

it('新字段取得服务端身份后，保存中的旧身份仍指向同一份草稿', () => {
  const store = createManualEvidenceDrafts()
  const temporary = { ...record, item_key: undefined }
  const from = manualDraftKey(target, temporary, '新值'), to = manualDraftKey(target, record, '新值')
  const file = new File(['notes'], 'notes.txt')
  store.edit(from, { reason: '新字段理由', files: [file] })
  store.adopt(from, to)
  expect(store.read(to)).toBe(store.read(from))
  store.acknowledge(from, empty, store.read(from).revision, file)
  expect(store.read(to).files).toEqual([])
  expect(store.read(to).dirty).toBe(false)
})

it('文件大小和五项上限在待上传阶段同样生效', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: { ...empty, items: Array.from({ length: 4 }, (_, i) => ({ id: String(i), kind: 'pdf', filename: `${i}.pdf`, source_description: '旧材料' })) } } as never)
  render(<ManualEvidenceSection target={target} record={record} version="v1" />)
  await screen.findByLabelText('人工修改判断理由（必填）')
  const large = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.pdf')
  fireEvent.drop(screen.getByRole('region'), { dataTransfer: { files: [large, new File(['a'], 'a.txt'), new File(['b'], 'b.txt')] } })
  expect(screen.getByRole('alert')).toHaveTextContent(/不能超过 10 MiB.*最多 5 项/)
  expect(screen.getByText('待上传：a.txt')).toBeInTheDocument()
  expect(screen.queryByText('待上传：b.txt')).not.toBeInTheDocument()
})

it('侧栏重开、切换字段和整体版本更新不覆盖当前理由、选择或待上传文件', async () => {
  const drafts = createManualEvidenceDrafts()
  vi.mocked(api.get).mockResolvedValue({ data: empty } as never)
  const props = { target, record, version: 'v1', drafts }
  const view = render(<ManualEvidenceSection {...props} />)
  fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'), { target: { value: '保留理由 A' } })
  fireEvent.click(screen.getByLabelText('提供证据'))
  const file = new File(['evidence'], 'notes.txt', { type: 'text/plain' })
  fireEvent.drop(screen.getByRole('region'), { dataTransfer: { files: [file] } })
  view.rerender(<ManualEvidenceSection {...props} record={{ ...record, item_key: 'b'.repeat(64), key: 'other', field: 'paper.summary' }} />)
  fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'), { target: { value: '字段 B 理由' } })
  view.rerender(<ManualEvidenceSection {...props} version="v2" />)
  await waitFor(() => expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('保留理由 A'))
  expect(screen.getByText(/待上传：notes.txt/)).toBeInTheDocument()
  view.unmount()
  render(<ManualEvidenceSection {...props} version="v3" />)
  expect(await screen.findByLabelText('人工修改判断理由（必填）')).toHaveValue('保留理由 A')
  expect(screen.getByLabelText('提供证据')).toBeChecked()
  expect(drafts.read(manualDraftKey(target, record, record.current_value)).files).toEqual([file])
})

it('首次读取迟到也不能覆盖期间输入的理由', async () => {
  let release!: (value: unknown) => void
  vi.mocked(api.get).mockImplementationOnce(() => new Promise(resolve => { release = resolve }) as never)
  render(<ManualEvidenceSection target={target} record={record} version="v1" localChanged />)
  fireEvent.change(screen.getByLabelText('人工修改判断理由（必填）'), { target: { value: '较新输入' } })
  await act(async () => release({ data: { ...empty, reason: '服务端旧值' } }))
  expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('较新输入')
})

it('同一字段换值时保留旧输入供只读查看，不能自动为新值背书', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: empty } as never)
  const drafts = createManualEvidenceDrafts()
  const view = render(<ManualEvidenceSection target={target} record={record} drafts={drafts} version="v1" />)
  fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'), { target: { value: '只适用于旧值的理由' } })
  view.rerender(<ManualEvidenceSection target={target} record={record} value="另一个值" drafts={drafts} version="v2" localChanged />)
  expect(screen.getByLabelText('人工修改判断理由（必填）')).toHaveValue('')
  expect(screen.getByText('只适用于旧值的理由')).toBeInTheDocument()
})

it('部分文件上传失败只保留失败项，重试不再上传已成功项', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: empty } as never)
  vi.mocked(api.put).mockResolvedValue({ data: { ...empty, reason: '完整理由' } } as never)
  vi.mocked(api.post).mockResolvedValueOnce({ data: { ...empty, items: [{ id: 'one', kind: 'text_file', filename: 'one.txt', source_description: 'one.txt' }] } } as never)
    .mockRejectedValueOnce(new Error('连接中断')).mockResolvedValue({ data: { ...empty, items: [] } } as never)
  render(<ManualEvidenceSection target={target} record={record} version="v1" />)
  fireEvent.change(await screen.findByLabelText('人工修改判断理由（必填）'), { target: { value: '完整理由' } })
  fireEvent.click(screen.getByLabelText('提供证据'))
  const one = new File(['1'], 'one.txt'), two = new File(['2'], 'two.txt')
  fireEvent.drop(screen.getByRole('region'), { dataTransfer: { files: [one, two] } })
  fireEvent.click(screen.getByText('上传人工证据'))
  await screen.findByText(/上传证据文件：连接中断/)
  expect(screen.getByText(/人工理由已保存/)).toBeInTheDocument()
  expect(screen.queryByText(/待上传：one.txt/)).not.toBeInTheDocument()
  expect(screen.getByText(/待上传：two.txt/)).toBeInTheDocument()
  fireEvent.click(screen.getByText('上传人工证据'))
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(3))
  expect(vi.mocked(api.post).mock.calls.map(([, body]) => (body as FormData).get('file'))).toEqual([one, two, two])
})

it('拖拽/图片粘贴共用校验，普通文本粘贴不拦截，待上传图片可预览', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: empty } as never)
  const create = vi.fn().mockReturnValue('blob:screenshot'), revoke = vi.fn()
  vi.stubGlobal('URL', class extends URL { static createObjectURL = create; static revokeObjectURL = revoke })
  const view = render(<ManualEvidenceSection target={target} record={record} version="v1" />)
  await screen.findByLabelText('人工修改判断理由（必填）')
  fireEvent.click(screen.getByLabelText('提供证据'))
  const region = screen.getByRole('region')
  const textEvent = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(textEvent, 'clipboardData', { value: { items: [{ kind: 'string', type: 'text/plain' }] } })
  fireEvent(region, textEvent)
  expect(textEvent.defaultPrevented).toBe(false)
  const image = new File(['png'], 'image.png', { type: 'image/png' })
  fireEvent.paste(region, { clipboardData: { items: [{ kind: 'file', type: 'image/png', getAsFile: () => image }] } })
  expect(await screen.findByAltText('人工提供的截图')).toHaveAttribute('src', 'blob:screenshot')
  expect(screen.getByText(/screenshot-.*\.png/)).toBeInTheDocument()
  fireEvent.drop(region, { dataTransfer: { files: [new File(['x'], 'bad.exe'), new File([], 'empty.pdf')] } })
  expect(screen.getByRole('alert')).toHaveTextContent(/不支持的文件类型.*bad.exe.*文件不能为空/)
  expect(screen.getByAltText('人工提供的截图')).toBeInTheDocument()
  fireEvent.click(screen.getByText('保存人工修改说明'))
  expect(await screen.findByText(/请先上传或移除待上传文件/)).toBeInTheDocument()
  expect(api.put).not.toHaveBeenCalled()
  view.unmount()
  expect(revoke).toHaveBeenCalledWith('blob:screenshot')
})

it('保存响应和旧读取都不能清除在途请求期间的新输入', async () => {
  vi.mocked(api.get).mockResolvedValue({ data: empty } as never)
  let release!: (value: unknown) => void
  vi.mocked(api.put).mockImplementationOnce(() => new Promise(resolve => { release = resolve }) as never)
  render(<ManualEvidenceSection target={target} record={record} version="v1" />)
  const input = await screen.findByLabelText('人工修改判断理由（必填）')
  fireEvent.change(input, { target: { value: '送出的理由' } })
  fireEvent.click(screen.getByText('保存人工修改说明'))
  await waitFor(() => expect(api.put).toHaveBeenCalled())
  fireEvent.change(input, { target: { value: '请求期间的新理由' } })
  await act(async () => release({ data: { ...empty, reason: '送出的理由' } }))
  expect(input).toHaveValue('请求期间的新理由')
})
