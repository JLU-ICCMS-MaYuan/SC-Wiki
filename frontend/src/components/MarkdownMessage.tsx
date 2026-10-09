import React, { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'
import { api } from '../lib/api'
import type { SourceTarget } from './RagSourceDrawer'

interface PaperInfo {
  title?: string
  doi?: string
  journal?: string
  year?: number
}

interface MarkdownMessageProps {
  content: string
  papers: Record<string, PaperInfo>
  paperSeqMap?: Record<string, number>
  onSourceOpen?: (target: SourceTarget, trigger: HTMLElement) => void
}

/** 清理文本中的内部标记，保留 [PID_xxx] 给组件处理 */
function cleanText(text: string): string {
  let t = text
  for (const tag of ['<!--IS:', '<!--BS:']) {
    const i = t.lastIndexOf(tag)
    if (i !== -1) t = t.substring(0, i)
  }
  t = t.replace(/\[PID_(\d+)[,\s]*来源\d+\]/g, '[PID_$1]')
  t = t.replace(/\[来源\d+\]（paper_id=\d+）/g, '')
  t = t.replace(/\[来源\d+\]/g, '')
  // 包裹裸 LaTeX
  t = t.replace(/(\\mathrm\{(?:[^{}]|\{[^{}]*\})*\}(?:_\{[^}]*\})?)/g, '$$1$')
  return t
}

const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ content, papers, paperSeqMap, onSourceOpen }) => {
  const text = cleanText(content)
  const [links, setLinks] = useState<SourceTarget[]>([])

  useEffect(() => {
    let current = true
    const timer = window.setTimeout(() => {
      const excerpt = text.slice(0, 12_000)
      const citationIds = Array.from(excerpt.matchAll(/\[PID_(\d+)\]/g), m => Number(m[1]))
      void api.post<{ ok: boolean; data: SourceTarget[] }>('/api/rag/source-links', {
        text: excerpt, citation_ids: citationIds,
      }).then(result => { if (current) setLinks(result.data) })
        .catch(() => { if (current) setLinks([]) })
    }, 250)
    return () => { current = false; window.clearTimeout(timer) }
  }, [text])

  const linkByTerm = useMemo(() => new Map(links.map(item => [item.term, item])), [links])
  const terms = useMemo(() => links.filter(item => !item.term.startsWith('[PID_'))
    .map(item => item.term).sort((a, b) => b.length - a.length), [links])

  // 闭包捕获 papers, paperSeqMap
  const processText = (str: string): React.ReactNode => {
    const escaped = terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    const pattern = new RegExp(`(\\[PID_\\d+\\]${escaped.length ? `|${escaped.join('|')}` : ''})`, 'g')
    const parts = str.split(pattern)
    if (parts.length === 1) return str
    return parts.map((part, i) => {
      const m = part.match(/^\[PID_(\d+)\]$/)
      const target = linkByTerm.get(part)
      if (!m && !target) return part
      if (m) {
        const pid = m[1]
        const seq = paperSeqMap?.[pid]
        const p = papers?.[pid]
        const title = p?.journal && p?.year ? `${p.journal} (${p.year})` : p?.journal || `Paper #${pid}`
        return <sup key={i} title={title}>
          {target && onSourceOpen ? <button type="button" className="rag-source-link"
            onClick={event => onSourceOpen(target, event.currentTarget)}>[{seq || pid}]</button>
            : <span className="cite-muted">[{seq || pid}]</span>}
        </sup>
      }
      return target && onSourceOpen ? <button key={i} type="button" className="rag-source-link"
        onClick={event => onSourceOpen(target, event.currentTarget)}>{part}</button> : part
    })
  }

  const processChildren = (children: React.ReactNode): React.ReactNode => {
    return React.Children.map(children, child => {
      if (typeof child === 'string') return processText(child)
      if (React.isValidElement(child) && (child.props as any)?.children) {
        if (typeof child.type === 'string' && ['a', 'code', 'pre'].includes(child.type)) return child
        return React.cloneElement(child, {
          ...(child.props as any),
          children: processChildren((child.props as any).children),
        } as any)
      }
      return child
    })
  }

  return (
    <div className="markdown-body" style={{ fontSize: 14, lineHeight: 1.8, color: '#333' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: false }]]}
        components={{
          p: ({ children, ...props }) => React.createElement('p', props, processChildren(children)),
          li: ({ children, ...props }) => React.createElement('li', props, processChildren(children)),
          td: ({ children, ...props }) => React.createElement('td', props, processChildren(children)),
          th: ({ children, ...props }) => React.createElement('th', props, processChildren(children)),
          span: ({ children, ...props }) => React.createElement('span', props, processChildren(children)),
        }}
      >
        {text}
      </ReactMarkdown>
      <style>{`
        .rag-source-link { border: 0; padding: 0; margin: 0 1px; background: none; color: #4d6bfe; cursor: pointer; font: inherit; text-decoration: underline; text-underline-offset: 2px; }
        .rag-source-link:hover { color: #303fbb; }
        .cite-muted { color: #999; }
      `}</style>
    </div>
  )
}

export default MarkdownMessage
