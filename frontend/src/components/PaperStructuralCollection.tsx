import { useEffect, useState } from 'react'
import { Alert, Box, Button, Card, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { StructuralItem } from './StructuralRecordView'

export function StructuralResults({ query }: { query: Record<string, unknown> | null }) {
  const [items, setItems] = useState<StructuralItem[]>([]), [total, setTotal] = useState(0)
  const [page, setPage] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const key = JSON.stringify(query)
  useEffect(() => { setPage(0) }, [key])
  useEffect(() => {
    let active = true
    if (!query) { setItems([]); setTotal(0); return }
    setBusy(true); setError('')
    void api.post<any>('/api/rag/structural-records/search', { ...query, limit: 20, offset: page * 20 })
      .then(value => { if (active) { setItems((value.items || []).filter((item: StructuralItem) => item.kind === 'model')); setTotal(value.total || 0) } })
      .catch(reason => { if (active) { setItems([]); setTotal(0); setError(reason.message) } })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [key, page, retry])
  if (!query) return null
  return <Box sx={{ mt: 3 }} data-testid="structural-search-results">
    <Typography variant="h6">相关结构资料 · {total} 项</Typography>
    <Typography variant="body2" color="text.secondary">按结构自身元素检索，无需 Tc。来源论文已批准；收录结构不代表该材料已证实超导。Tc 范围与图表筛选仅作用于 Tc 数据区。</Typography>
    {busy && <Typography role="status">正在读取结构资料…</Typography>}
    {error && <Alert severity="warning">结构资料暂不可读取：{error}<Button onClick={() => setRetry(v => v + 1)}>重试</Button></Alert>}
    {!busy && !error && !items.length && <Typography sx={{ my: 1 }}>暂无符合条件的已批准结构资料。</Typography>}
    <StructuralCards items={items} />
    <Box sx={{ display: 'flex', gap: 1, my: 1 }}><Button disabled={!page || busy} onClick={() => setPage(p => p - 1)}>上一页</Button><Typography sx={{ alignSelf: 'center' }}>第 {page + 1} 页</Typography><Button disabled={(page + 1) * 20 >= total || busy} onClick={() => setPage(p => p + 1)}>下一页</Button></Box>
  </Box>
}

export default function PaperStructuralCollection({ paperId }: { paperId: number }) {
  const [items, setItems] = useState<StructuralItem[]>([]), [error, setError] = useState('')
  useEffect(() => {
    let active = true; setItems([]); setError('')
    void api.get<any>(`/api/rag/structural-records/paper/${paperId}`).then(value => { if (active) setItems((value.items || []).filter((item: StructuralItem) => item.kind === 'model' && !item.state_key)) })
      .catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [paperId])
  if (!items.length && !error) return null
  return <Box sx={{ my: 3 }}><Typography variant="h6">本文提供的结构与几何资料</Typography>
    {error && <Alert severity="warning">{error}</Alert>}
    <StructuralCards items={items} />
  </Box>
}

function StructuralCards({ items }: { items: StructuralItem[] }) {
  return <>{items.map(item => <Card variant="outlined" key={item.id} sx={{ p: 2, my: 1, minWidth: 0 }}>
    <Typography fontWeight={700}>{item.material} · {item.pressure_gpa ?? '压力未报告'} {item.pressure_gpa != null ? 'GPa' : ''} · {item.space_group || '空间群未报告'}</Typography>
    <Typography variant="body2">{item.kind === 'model' ? '完整结构' : item.kind === 'issue' ? '提取问题 · 仅内部核对' : '几何参数 · 无原子位置'}{item.data.calculation_label ? ' · ' + item.data.calculation_label : ''}{item.retention !== 'retained' ? ' · 未公开' : ''}</Typography>
    <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>来源：{item.title} {item.doi ? ' · DOI: ' + item.doi : ''}</Typography>
    <Typography variant="caption" display="block">{item.data.sources?.map((source: any) => [source.filename, source.page ? `第 ${source.page} 页` : '', source.table].filter(Boolean).join(' · ')).join('；')}</Typography>
    <Button component={Link} to={`/structures/${encodeURIComponent(item.id)}`}>{item.kind === 'model' ? '查看结构与下载' : '查看参数与下载'}</Button>
    <Button component={Link} to={`/papers/${item.paper_id}`}>查看来源论文</Button>
  </Card>)}</>
}
