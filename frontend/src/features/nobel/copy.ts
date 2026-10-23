import type { Lang } from '../../i18n'
import { laureates, type NobelLaureate } from './data'
import { englishBiographies } from './en'

export const copy = {
  zh: {
    title: '超导研究的诺奖群像', kicker: '诺贝尔奖里程碑 · 1913—2003',
    intro: '从超导与超流到量子隧穿，认识十二位诺奖得主。', brand: '科学史展厅',
    controls: '按住左右拖动，控制旋转方向 · 悬停暂停 · 点击阅读', pause: '暂停旋转', resume: '继续旋转', reduced: '减少动态已开启',
    gallery: '诺贝尔物理学奖得主肖像展', ring: '旋转的获奖者肖像', select: '选择获奖者', prize: '诺贝尔物理学奖',
    read: '科研经历与参考资料 ↗', back: '← 返回肖像展', photo: '原始照片', photoCaption: '历史原照 · 诺贝尔奖里程碑',
    identity: '获奖时国籍/身份：', achievement: '获奖成果', career: '科研经历', connection: '与超导研究的关系', sources: '参考资料', share: '本届奖项个人份额：',
    note: '资料核对日期：2026 年 10 月 23 日。生卒年份与授奖理由依据诺奖官网；国籍、任职机构与出生地分别注明。当前展示历史原始照片。',
    demoNote: '当前使用历史原照进行交互预览，漫画肖像后续制作。', notFound: '未找到这位获奖者',
    citation: (index: number) => `参考资料 ${index}`,
    visit: (name: string, year: number) => `查看 ${name}，${year} 年诺贝尔物理学奖得主`,
  },
  en: {
    title: 'Nobel portraits in superconductivity', kicker: 'NOBEL MILESTONES · 1913–2003',
    intro: 'Twelve laureates across superconductivity, superfluidity and quantum tunneling.', brand: 'History of science',
    controls: 'Drag to turn · Hover to pause · Click to read', pause: 'Pause rotation', resume: 'Resume rotation', reduced: 'Reduced motion enabled',
    gallery: 'Nobel physics laureate portraits', ring: 'Rotating laureate portraits', select: 'Select a laureate', prize: 'Nobel Prize in Physics',
    read: 'Research and references ↗', back: '← Back to the portraits', photo: 'original photograph', photoCaption: 'Original photograph · Nobel milestones',
    identity: 'Nationality / affiliation at the award: ', achievement: 'Award-winning contribution', career: 'Research career', connection: 'Connection to superconductivity', sources: 'References', share: 'Individual share of this prize: ',
    note: 'Sources checked on 23 October 2026. Dates and award motivations follow NobelPrize.org; citizenship, affiliation and birthplace are identified separately. Original historical photographs are shown.',
    demoNote: 'Interaction preview with original photographs; illustrated portraits will follow.', notFound: 'Laureate not found',
    citation: (index: number) => `Reference ${index}`,
    visit: (name: string, year: number) => `Read about ${name}, ${year} Nobel Prize in Physics laureate`,
  },
}

export function getLaureates(lang: Lang): NobelLaureate[] {
  if (lang === 'zh') return laureates
  return laureates.map(person => ({
    ...person, ...englishBiographies[person.id], name: person.englishName,
    identityNote: englishBiographies[person.id].identityNote,
    sources: person.sources.map((source, index) => ({ ...source,
      label: index === 0 ? `Nobel Prize: ${person.englishName} — Facts`
        : index === 1 ? `Nobel Prize: ${person.englishName} — Biography`
          : index === 2 ? `Nobel Prize in Physics ${person.awardYear}` : `Research paper · ${source.url.replace('https://doi.org/', '')}`,
      supports: ['Life dates and official laureate record', 'Education and research career', 'Award motivation and co-laureates', 'Published research supporting the contribution'][index] || 'Supporting source',
    })),
  }))
}

export function coAwardText(person: NobelLaureate, people: NobelLaureate[], lang: Lang) {
  const peers = people.filter(other => other.awardYear === person.awardYear && other.id !== person.id)
  if (!peers.length) return lang === 'zh'
    ? `独获 ${person.awardYear} 年诺贝尔物理学奖。`
    : `Sole recipient of the ${person.awardYear} Nobel Prize in Physics.`
  const names = peers.map(peer => lang === 'zh' ? peer.name : peer.englishName)
  return lang === 'zh'
    ? `与${names.join('、')}共同获颁 ${person.awardYear} 年诺贝尔物理学奖。`
    : `Shared the ${person.awardYear} Nobel Prize in Physics with ${names.join(' and ')}.`
}
