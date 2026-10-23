import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { LanguageProvider } from '../../frontend/src/context/LanguageContext'
import NobelLaureatePage from '../../frontend/src/pages/NobelLaureatePage'
import { NobelGallery, NobelSurface } from '../../frontend/src/features/nobel/NobelExperience'
import { getLaureates, coAwardText } from '../../frontend/src/features/nobel/copy'

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear() })

describe('诺奖正式接入与授奖事实', () => {
  it('1973年三人共同获奖但贡献不同，份额分别为1/4、1/4、1/2', () => {
    const people = getLaureates('zh')
    const three = people.filter(person => person.awardYear === 1973)
    expect(three.map(person => person.prizeShare)).toEqual(['1/4', '1/4', '1/2'])
    expect(three[0].achievement).toContain('并非超导研究')
    expect(three[1].achievement).toContain('超导体中的电子隧穿')
    expect(three[2].achievement).toContain('库珀对隧穿')
    expect(coAwardText(three[0], people, 'zh')).toBe('与伊瓦尔·贾埃弗、布赖恩·约瑟夫森共同获颁 1973 年诺贝尔物理学奖。')
    expect(coAwardText(people[0], people, 'zh')).toBe('独获 1913 年诺贝尔物理学奖。')
    for (const year of [1913, 1972, 1973, 1987, 2003]) {
      const sum = people.filter(person => person.awardYear === year).reduce((total, person) => {
        const [a, b] = person.prizeShare.split('/').map(Number)
        return total + a / b
      }, 0)
      expect(sum).toBeCloseTo(1)
    }
  })

  it('共享正式组件中每个人的成果后显示共同获奖关系，入口不指向Demo', () => {
    render(<NobelSurface><NobelGallery embedded lang="zh" /></NobelSurface>)
    const links = [...document.querySelectorAll<HTMLAnchorElement>('.nobel-face')]
    expect(links).toHaveLength(12)
    for (const link of links) {
      expect(link.pathname).toMatch(/^\/nobel\//)
      expect(link.target).toBe('_blank')
      expect(link.querySelector('.nobel-person-achievement')?.nextElementSibling?.className).toBe('nobel-person-coaward')
    }
    expect(document.querySelector('h1')).toBeNull()
  })

  it('正式人物路由支持英文内容与明确的奖项份额', () => {
    localStorage.setItem('sc-wiki.language', 'en')
    const { container } = render(<MemoryRouter initialEntries={['/nobel/esaki']}><LanguageProvider>
      <Routes><Route path="/nobel/:personId" element={<NobelLaureatePage />} /></Routes>
    </LanguageProvider></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Leo Esaki', level: 1 })).toBeTruthy()
    expect(screen.getByText('1/4')).toBeTruthy()
    expect(container.textContent).toContain('Shared the 1973 Nobel Prize in Physics with Ivar Giaever and Brian Josephson.')
    expect(container.textContent).not.toMatch(/[\u3400-\u9fff]/)
    expect(screen.getByRole('link', { name: '← Back to the portraits' }).getAttribute('href')).toBe('/news#nobel-milestones')
  })

  it('未知人物不会显示为另一个人的资料', () => {
    render(<MemoryRouter initialEntries={['/nobel/missing']}><LanguageProvider>
      <Routes><Route path="/nobel/:personId" element={<NobelLaureatePage />} /></Routes>
    </LanguageProvider></MemoryRouter>)
    expect(screen.getByRole('heading', { name: '未找到这位获奖者' })).toBeTruthy()
  })

  it('12人英文资料均完整，保留原始身份与来源路径且无中文泄漏', () => {
    const people = getLaureates('en')
    expect(people).toHaveLength(12)
    for (const person of people) {
      expect(person.career.length).toBeGreaterThan(30)
      expect(person.awardReason.length).toBeGreaterThan(30)
      expect(person.superconductivityLink.length).toBeGreaterThan(30)
      expect(JSON.stringify(person)).not.toMatch(/[\u3400-\u9fff]/)
      expect(person.sources[0].url).toMatch(/nobelprize.org.*\/facts\/$/)
    }
  })
})
