import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import AlphaIntegralHelp from '../../frontend/src/components/spectrumEditor/AlphaIntegralHelp'

afterEach(cleanup)
it('相对像素和人工重算限制分别显示，核对步骤不承诺填依据即通过',()=>{
  render(<AlphaIntegralHelp unit="pixel" evidence="" manual />)
  expect(screen.getByText(/当前幅值仍是相对像素/)).toBeInTheDocument()
  expect(screen.getByTestId('manual-integral-boundary')).toHaveTextContent('尚未自动重算人工谱')
  fireEvent.click(screen.getByText('α²F 幅值怎么核对？查看操作步骤'))
  expect(screen.getByText(/若论文没有提供独立刻度/)).toBeVisible()
  expect(screen.getByText(/倍率可以抵消/)).toBeVisible()
})
it('已填写物理标定仍说明完整性边界，不误说缺少绝对尺度必然不能算ωlog',()=>{
  render(<AlphaIntegralHelp unit="dimensionless" evidence="图注给出α²F独立尺度" manual={false} />)
  expect(screen.getByText(/当前已填写幅值数值标定/)).toBeInTheDocument()
  expect(screen.queryByTestId('manual-integral-boundary')).toBeNull()
})
