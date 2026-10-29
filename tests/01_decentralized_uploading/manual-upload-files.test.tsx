import '@testing-library/jest-dom/vitest'
import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import MultiFileUploadPanel from '../../frontend/src/components/MultiFileUploadPanel'
import UploadPage from '../../frontend/src/pages/UploadPage'
import { AuthProvider } from '../../frontend/src/context/AuthContext'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import { api } from '../../frontend/src/lib/api'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn(), get: vi.fn() } }))
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.clearAllMocks() })

const file = (name: string) => new File([name], name, { type: name.endsWith('.pdf') ? 'application/pdf' : 'text/plain' })
const area = (name: string) => screen.getByRole('region', { name })
const select = (name: string, files: File[]) => fireEvent.change(area(name).querySelector('input')!, { target: { files } })
const panel = () => render(<LanguageProvider><MultiFileUploadPanel onCreated={vi.fn()} /></LanguageProvider>)

it('三个指定区域拒绝错区和重复正文，保留原选择，选择时无请求', () => {
  panel()
  select('论文正文', [file('paper-SI.pdf')])
  fireEvent.drop(area('补充材料'), { dataTransfer: { files: [file('si.pdf'), file('correction.md')] } })
  select('源数据文件', [file('cell.cif'), file('POSCAR')])
  expect(within(area('论文正文')).getByText('paper-SI.pdf')).toBeVisible()
  expect(within(area('补充材料')).getByText('correction.md')).toBeVisible()
  expect(within(area('源数据文件')).getByText('POSCAR')).toBeVisible()
  select('论文正文', [file('second.pdf')])
  expect(screen.getByRole('alert')).toHaveTextContent('只能上传一个正文')
  expect(screen.queryByText('second.pdf')).not.toBeInTheDocument()
  select('源数据文件', [file('misplaced.pdf')])
  expect(screen.getByRole('alert')).toHaveTextContent('结构')
  expect(screen.queryByText('misplaced.pdf')).not.toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
  expect(api.get).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '移除 si.pdf' }))
  expect(screen.queryByText('si.pdf')).not.toBeInTheDocument()
  expect(screen.getByText('correction.md')).toBeVisible()
})

it('没有正文时开始上传给出错误，不创建任务；正文批量拖入不静默选第一份', () => {
  panel()
  select('补充材料', [file('si.pdf')])
  fireEvent.click(screen.getByRole('button', { name: '开始上传并解析' }))
  expect(screen.getByRole('alert')).toHaveTextContent('恰好')
  fireEvent.drop(area('论文正文'), { dataTransfer: { files: [file('one.pdf'), file('two.pdf')] } })
  expect(screen.queryByText('one.pdf')).not.toBeInTheDocument()
  expect(screen.queryByText('two.pdf')).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
})

it('完整 UploadPage 用三个区域创建一个任务，五个角色准确且仅三路并发', async () => {
  const user = { id: 7, username: 'fixture', role: 'user', is_approved: true, is_email_verified: true, account_status: 'active' }
  localStorage.setItem('auth_token', 'isolated')
  localStorage.setItem('auth_user', JSON.stringify(user))
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ user }), { headers: { 'Content-Type': 'application/json' } })))
  let active = 0, peak = 0
  const requests: (() => void)[] = []
  class Xhr {
    upload = {}; status = 200; onload?: () => void
    open() {}
    setRequestHeader() {}
    send() { active++; peak = Math.max(peak, active); requests.push(() => { active--; this.onload?.() }) }
  }
  vi.stubGlobal('XMLHttpRequest', Xhr)
  const names = ['main.pdf', 'si.pdf', 'correction.txt', 'cell.cif', 'cell.vasp']
  const task = { task_id: '1'.repeat(32), status: 'queued', files: names.map((_, i) => ({ file_id: String(i) })) }
  vi.mocked(api.get).mockResolvedValue({ ok: true, data: [] } as never)
  vi.mocked(api.post).mockResolvedValue({ ok: true, data: task } as never)
  render(<MemoryRouter><AuthProvider><LanguageProvider><UploadPage /></LanguageProvider></AuthProvider></MemoryRouter>)
  await screen.findByRole('region', { name: '论文正文' })
  select('论文正文', [file(names[0])])
  select('补充材料', names.slice(1, 3).map(file))
  select('源数据文件', names.slice(3).map(file))
  fireEvent.click(screen.getByRole('button', { name: '开始上传并解析' }))
  await waitFor(() => expect(requests).toHaveLength(3))
  expect(api.post).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.post).mock.calls[0][1] as { files: { role: string; filename: string }[] }
  expect(body.files.map(x => [x.filename, x.role])).toEqual(names.map((name, i) => [name, i === 0 ? 'main' : i < 3 ? 'supplementary' : 'attachment']))
  expect(screen.getByRole('button', { name: '上传中…' })).toBeDisabled()
  requests.shift()!()
  await waitFor(() => expect(requests).toHaveLength(3))
  requests.shift()!()
  await waitFor(() => expect(requests).toHaveLength(3))
  requests.splice(0).forEach(finish => finish())
  await waitFor(() => expect(screen.queryByText('main.pdf')).not.toBeInTheDocument())
  expect(screen.queryByRole('button', { name: '上传中…' })).not.toBeInTheDocument()
  expect(peak).toBe(3)
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining('resolve-roles'), expect.anything())
})

it('清空只移除本地选择，源数据兼容命名有效', () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  panel()
  select('论文正文', [file('main.txt')])
  select('源数据文件', ['cell.poscar', 'cell.vasp', 'CONTCAR'].map(file))
  fireEvent.click(screen.getByRole('button', { name: '清空' }))
  expect(screen.queryByText('main.txt')).not.toBeInTheDocument()
  expect(screen.queryByText('CONTCAR')).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
})
