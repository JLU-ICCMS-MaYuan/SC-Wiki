import React from 'react'
import { Box } from '@mui/material'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

/** 用户正文不经过 RAG 标记替换，也不允许原始 HTML 和远程图片。 */
export default function CommunityMarkdown({ content }: { content: string }) {
  return <Box sx={{ overflowWrap: 'anywhere', '& pre': { overflowX: 'auto', p: 1.5, bgcolor: 'action.hover' }, '& table': { display: 'block', overflowX: 'auto' }, '& .katex-display': { overflowX: 'auto', overflowY: 'hidden' } }}>
    <ReactMarkdown skipHtml remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, { strict: false, trust: false, maxExpand: 1000 }]]}
      components={{ img: () => null, a: ({ href, children }) => <a href={href && /^(https?:\/\/|mailto:|\/[^/]|#)/i.test(href) ? href : undefined} target="_blank" rel="noopener noreferrer nofollow">{children}</a> }}>
      {content}
    </ReactMarkdown>
  </Box>
}
