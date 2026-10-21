import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import UploadRoleReview from '../../frontend/src/components/UploadRoleReview'
import { api } from '../../frontend/src/lib/api'
import type { UploadTaskState } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({ api: { post: vi.fn() } }))

afterEach(() => { cleanup(); vi.clearAllMocks() })

it('歧义任务提交完整文件角色和当前版本后继续解析', async () => {
  const task = {
    task_id: 'a'.repeat(32), status: 'needs_role_review', revision: 4,
    files: [
      { file_id: 'si', original_filename: 'paper-SI.pdf', role: 'main' },
      { file_id: 'article', original_filename: 'paper.pdf', role: 'attachment' },
    ],
    role_assessment: {
      status: 'needs_review', main_file_id: null, source_hash: 'hash', reason: '无法可靠确定唯一正文',
      files: [
        { file_id: 'si', declared_role: 'main', effective_role: null, article_signals: [], supplement_signals: ['补充材料'], readable: true },
        { file_id: 'article', declared_role: 'attachment', effective_role: null, article_signals: ['论文标题'], supplement_signals: [], readable: true },
      ],
    },
  } as UploadTaskState
  const onResolved = vi.fn()
  vi.mocked(api.post).mockResolvedValue({ ok: true, data: { ...task, status: 'queued' } } as never)
  render(<UploadRoleReview task={task} onResolved={onResolved} />)
  expect(screen.getByText('无法可靠确定唯一正文')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '确认角色并继续解析' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    `/api/upload-tasks/${task.task_id}/resolve-roles`,
    { expected_revision: 4, roles: [{ file_id: 'si', role: 'main' }, { file_id: 'article', role: 'attachment' }] },
  ))
  expect(onResolved).toHaveBeenCalled()
})
