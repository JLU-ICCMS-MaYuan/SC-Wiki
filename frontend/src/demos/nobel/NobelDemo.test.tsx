import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import NobelDemo from './NobelDemo'
import { projectGallery } from './projection'

describe('弧形展陈的布局不变量', () => {
  it('两圈密集相位内，所有相邻容器始终有足够间隔', () => {
    for (const width of [288, 358, 568, 744, 1024, 1344]) {
      for (let angle = -360; angle <= 360; angle += 0.5) {
        const cards = projectGallery(angle, 12, width).sort((a, b) => a.x - b.x)
        for (let i = 1; i < cards.length; i++) {
          const previous = cards[i - 1], current = cards[i]
          const gap = current.x - current.width / 2 - (previous.x + previous.width / 2)
          if (gap < (width < 600 ? 24 : 36) - 1e-6) throw new Error(`相位 ${angle}、宽度 ${width} 发生遮挡`)
        }
      }
    }
  })

  it('切换主位和跨越循环边界时，可见人物位置连续，主位明显大于侧位', () => {
    for (let boundary = -360; boundary <= 360; boundary += 15) {
      const before = projectGallery(boundary - 0.001, 12, 1344)
      const after = projectGallery(boundary + 0.001, 12, 1344)
      before.forEach((card, index) => {
        if (card.opacity > 0 && after[index].opacity > 0) expect(Math.abs(card.x - after[index].x)).toBeLessThan(0.1)
      })
    }
    const cards = projectGallery(0, 12, 1344)
    expect(cards[0].scale / cards[2].scale).toBeGreaterThan(2)
    expect(Math.abs(cards[2].yaw)).toBeGreaterThan(35)
  })
})

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
