import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import StructureCandidateSource from '../../frontend/src/components/StructureCandidateSource'

afterEach(cleanup)

it('对称派生结构同时展示原始与派生坐标，保持未确认状态', () => {
  const candidate = { candidate_id: 'derived', status: 'valid', confirmation: 'unreviewed',
    sources: [{ filename: 'supp.pdf', page: 8, quote: 'Sc (2c) 0.333 0.667 0.000' }],
    derivation: { rounding_adjustments: [{ site: 'Sc(2c)', reported_coordinates: [.333, .667, 0], derived_coordinates: [1 / 3, 2 / 3, 0], rounding_half_width: [.0005, .0005, .0005] }] } }
  render(<StructureCandidateSource candidate={candidate} />)
  expect(screen.getByRole('alert')).toHaveTextContent('派生坐标')
  fireEvent.click(screen.getByText('查看坐标舍入处理'))
  expect(screen.getByText(/Sc\(2c\)：\(0.333, 0.667, 0\) → \(0.33333333, 0.66666667, 0\)/)).toBeVisible()
  fireEvent.click(screen.getByText('查看结构来源与已提取参数'))
  expect(screen.getByText('Sc (2c) 0.333 0.667 0.000')).toBeVisible()
  expect(candidate.confirmation).toBe('unreviewed')
})

it('没有对称恢复记录的结构不显示派生坐标提示', () => {
  render(<StructureCandidateSource candidate={{ candidate_id: 'original', status: 'valid', sources: [] }} />)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.queryByText('查看坐标舍入处理')).not.toBeInTheDocument()
})
