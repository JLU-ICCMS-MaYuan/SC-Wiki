import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import NobelDemo from './NobelDemo'

beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
})
afterEach(() => {
  vi.unstubAllGlobals()
  cleanup()
  window.history.replaceState({}, '', '/')
})

describe('诺奖肖像展 Demo', () => {
  it('展示 12 位人物并通过安全的新标签页链接打开详情', () => {
    render(<NobelDemo />)

    expect(screen.getByRole('heading', { name: '超导研究的诺奖群像' })).toBeTruthy()
    expect(document.querySelectorAll('.nobel-face')).toHaveLength(12)
    expect(document.querySelector('.nobel-caption')).toBeNull()
    expect(document.querySelectorAll('.nobel-face h2')).toHaveLength(12)
    expect(document.querySelector('.nobel-face img')?.getAttribute('src')).toContain('/original/')
    const personLink = screen.getByRole('listitem', { name: /查看 Heike Kamerlingh Onnes/ }) as HTMLAnchorElement
    expect(personLink.target).toBe('_blank')
    expect(personLink.rel).toContain('noopener')
    expect(personLink.href).toContain('person=onnes')
  })

  it('按人物查询参数呈现科研经历和支持性来源', () => {
    window.history.replaceState({}, '', '/nobel-demo.html?person=leggett')
    render(<NobelDemo />)

    expect(screen.getByRole('heading', { name: '安东尼·莱格特' })).toBeTruthy()
    expect(screen.getByText(/不是因超导研究获奖/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: '参考资料' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /诺贝尔奖：2003 年物理学奖/ })).toBeTruthy()
  })
})
