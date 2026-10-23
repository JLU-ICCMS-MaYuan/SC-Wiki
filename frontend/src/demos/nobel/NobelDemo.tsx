import { useState, type CSSProperties } from 'react'
import { laureates, type NobelLaureate } from './data'
import './nobel-demo.css'

const getPerson = () => new URLSearchParams(window.location.search).get('person')

function SourceList({ sources }: { sources: NobelLaureate['sources'] }) {
  return (
    <ol className="nobel-sources">
      {sources.map((source) => (
        <li key={source.url} id={`source-${sources.indexOf(source) + 1}`}>
          <a href={source.url} target="_blank" rel="noopener noreferrer">{source.label}</a>
          <span>{source.supports}</span>
        </li>
      ))}
    </ol>
  )
}

function Citations({ indices }: { indices: number[] }) {
  return <sup className="nobel-citations">{indices.map(index => <a key={index} href={`#source-${index}`} aria-label={`参考资料 ${index}`}>[{index}]</a>)}</sup>
}

function LaureateDetail({ person }: { person: NobelLaureate }) {
  return (
    <main className="nobel-detail">
      <a className="nobel-back" href="/nobel-demo.html">← 返回肖像展</a>
      <div className="nobel-detail-grid">
        <figure className="nobel-detail-portrait">
          <img src={person.image} alt={`${person.englishName} 的漫画肖像`} />
          <figcaption>漫画肖像 · 超导诺奖得主展</figcaption>
        </figure>
        <article className="nobel-biography">
          <p className="nobel-kicker">NOBEL PHYSICS · {person.awardYear}</p>
          <h1>{person.name}</h1>
          <p className="nobel-english-name">{person.englishName} <span>({person.years})</span><Citations indices={[1]} /></p>
          <p className="nobel-identity">获奖时国籍/身份：{person.identity}<Citations indices={[1, 2, 3]} /></p>
          {person.identityNote && <p className="nobel-note">{person.identityNote}</p>}
          <section>
            <h2>获奖成果</h2>
            <p>{person.awardReason}<Citations indices={[1, 3]} /></p>
          </section>
          <section>
            <h2>科研经历</h2>
            <p>{person.career}<Citations indices={[2]} /></p>
          </section>
          <section>
            <h2>与超导研究的关系</h2>
            <p>{person.superconductivityLink}<Citations indices={[1, 3, ...(person.sources.length > 3 ? [4] : [])]} /></p>
          </section>
          <section>
            <h2>参考资料</h2>
            <SourceList sources={person.sources} />
          </section>
          <p className="nobel-editorial-note">资料核对日期：2026 年 10 月 23 日。生卒年份与授奖理由依据诺奖官网；国籍、任职机构与出生地分别注明。肖像仍为待评审的线稿处理图，尚未达到参考漫画的最终质量。</p>
        </article>
      </div>
    </main>
  )
}

function Exhibition() {
  const initial = laureates[0]
  const [selected, setSelected] = useState(initial)
  const [still, setStill] = useState(false)
  const people = laureates
  const position = people.indexOf(selected) * -30
  const radius = 410

  return (
    <main className="nobel-exhibition">
      <header className="nobel-header">
        <a className="nobel-brand" href="/">SC-WIKI <span>科学史展厅</span></a>
        <p className="nobel-kicker">SUPERCONDUCTIVITY · NOBEL LAUREATES</p>
        <h1>超导研究的诺奖群像</h1>
        <p className="nobel-intro">沿着一圈肖像，回看超导与量子物态研究中的重要发现。</p>
      </header>

      <section className="nobel-gallery" aria-label="诺贝尔物理学奖得主肖像展">
        <div className="nobel-gallery-topline">
          <span>获奖者肖像 · 1913—2003</span>
          <span>将指针移到肖像上暂停展陈</span>
        </div>
        <div className="nobel-stage">
          <div className="nobel-axis" aria-hidden="true" />
          <div className="nobel-cylinder" role="list" aria-label="缓慢旋转的获奖者肖像">
            <div className="nobel-ring" data-still={still} style={{'--focus-angle': `${position}deg`} as CSSProperties}>
              {people.map((person, index) => {
                const angle = (360 / people.length) * index
                const active = selected.id === person.id
                return (
                  <a
                    key={person.id}
                    className={`nobel-face${active ? ' is-selected' : ''}`}
                    style={{ transform: `rotateY(${angle}deg) translateZ(${radius}px)` }}
                    href={`/nobel-demo.html?person=${person.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`查看 ${person.englishName}，${person.awardYear} 年诺贝尔物理学奖得主`}
                    role="listitem"
                    onMouseEnter={() => setSelected(person)}
                    onFocus={() => { setSelected(person); setStill(true) }}
                  >
                    <img src={person.image} alt="" loading={index < 4 ? 'eager' : 'lazy'} />
                    <span className="nobel-face-plaque">{person.awardYear}</span>
                  </a>
                )
              })}
            </div>
          </div>
          <div className="nobel-stage-floor" aria-hidden="true" />
        </div>

        <nav className="nobel-person-index" aria-label="选择获奖者">
          <button type="button" onClick={() => setStill(!still)} aria-pressed={still}>{still ? '继续旋转' : '暂停旋转'}</button>
          {people.map(person => <button key={person.id} type="button" aria-pressed={selected.id === person.id} onClick={() => { setSelected(person); setStill(true) }}>{person.englishName.split(' ').slice(-1)[0]}</button>)}
        </nav>

        <article className="nobel-caption" aria-live="polite">
          <div className="nobel-caption-year">{selected.awardYear}</div>
          <div className="nobel-caption-copy">
            <h2>{selected.name} <span>· {selected.englishName}</span></h2>
            <p className="nobel-caption-meta">{selected.years} <i /> {selected.identity}</p>
            {selected.identityNote && <p className="nobel-note">{selected.identityNote}</p>}
            <p>{selected.achievement}</p>
          </div>
          <a className="nobel-read-more" href={`/nobel-demo.html?person=${selected.id}`} target="_blank" rel="noopener noreferrer">
            阅读科研经历 ↗
          </a>
        </article>
      </section>

      <footer className="nobel-footer">
        <p>交互预览 · 肖像线稿仍待重绘与评审，尚未满足最终漫画素材验收。</p>
        <p>本 Demo 独立运行，尚未替换快讯页现有的诺奖里程碑区块。</p>
      </footer>
    </main>
  )
}

export default function NobelDemo() {
  const personId = getPerson()
  const person = laureates.find((entry) => entry.id === personId)

  return (
    <div className="nobel-demo-shell">
      {person ? <LaureateDetail person={person} /> : <Exhibition />}
    </div>
  )
}
