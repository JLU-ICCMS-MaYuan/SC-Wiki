import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import PaperEditView from '../../frontend/src/components/PaperEditView'

vi.mock('../../frontend/src/components/CrystalStructureView', () => ({
  default: ({ data }: { data: string }) => <div data-testid="detail-structure-model">{data}</div>,
}))
afterEach(cleanup)

it('论文只读详情结构默认收起，文件及模型在展开后显示，重开保持挂载', () => {
  const view = render(<PaperEditView paper={{ id: 1, title: '结构示例', material_states: [{ state_key: 'sn', material: 'Sn', structures: [{ id: 2, filename: 'Sn.cif', structure_text: 'fixture', structure_format: 'cif' }] }] }} onBack={() => undefined} />)
  const title = screen.getByText('晶体结构')
  const section = title.closest('details')!
  const toggle = section.querySelector('summary')!
  const model = screen.getByTestId('detail-structure-model')
  expect(section).not.toHaveAttribute('open')
  expect(model).toBeInTheDocument()
  expect(model).not.toBeVisible()
  fireEvent.click(toggle)
  expect(model).toBeVisible()
  expect(screen.getByText('Sn.cif (cif)')).toBeVisible()
  fireEvent.click(toggle)
  fireEvent.click(toggle)
  expect(screen.getByTestId('detail-structure-model')).toBe(model)
  expect(view.container.querySelector('input[type="file"]')).toBeNull()
})
