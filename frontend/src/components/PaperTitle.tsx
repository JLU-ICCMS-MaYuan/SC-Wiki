import { useLayoutEffect, useRef, useState } from 'react'
import { Tooltip, Typography } from '@mui/material'

/** 只测量当前标题；完整题目始终来自原始值。 */
export default function PaperTitle({ title }: { title: string }) {
  const ref = useRef<HTMLElement>(null)
  const [truncated, setTruncated] = useState(false)
  useLayoutEffect(() => {
    const node = ref.current
    if (!node) return
    const measure = () => setTruncated(node.scrollWidth > node.clientWidth)
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(node)
    return () => observer?.disconnect()
  }, [title])
  return <Tooltip title={truncated ? title : ''} describeChild>
    <Typography ref={ref} variant="body2" fontWeight={600} noWrap tabIndex={truncated ? 0 : undefined}
      sx={{ width: '100%' }}>{title}</Typography>
  </Tooltip>
}
