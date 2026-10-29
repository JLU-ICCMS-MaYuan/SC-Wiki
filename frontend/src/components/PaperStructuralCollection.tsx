import { useEffect, useState } from 'react'
import { Alert, Box, Button, Card, Typography } from '@mui/material'
import { useLocation } from 'react-router-dom'
import { detailURL } from '../lib/searchNavigation'
import { useLanguage } from '../context/LanguageContext'
import { api } from '../lib/api'
import type { StructuralItem } from './StructuralRecordView'

export function StructuralResults({ query, page: controlledPage, onPageChange }: { query: Record<string, unknown> | null; page?: number; onPageChange?: (page: number) => void }) {
  const {t} = useLanguage()
  const [items, setItems] = useState<StructuralItem[]>([]), [total, setTotal] = useState(0)
  const [localPage, setLocalPage] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const location = useLocation()
  const page = controlledPage ?? localPage
  const setPage = (value: number) => onPageChange ? onPageChange(value) : setLocalPage(value)
  const key = JSON.stringify(query)
  useEffect(() => { if (controlledPage === undefined) setLocalPage(0) }, [key, controlledPage])
  useEffect(() => {
    let active = true
    if (!query) { setItems([]); setTotal(0); return }
    setBusy(true); setError('')
    void api.post<any>('/api/rag/structural-records/search', { ...query, independent_only: true, limit: 20, offset: page * 20 })
      .then(value => { if (active) { setItems((value.items || []).filter((item: StructuralItem) => item.kind === 'model')); setTotal(value.total || 0); const last = Math.max(0, Math.ceil((value.total || 0) / 20) - 1); if (page > last) setPage(last) } })
      .catch(reason => { if (active) { setItems([]); setTotal(0); setError(reason.message) } })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [key, page, retry])
  if (!query) return null
  return <Box sx={{ mt: 3 }} data-testid="structural-search-results">
    <Typography variant="h6">{t('search.independentStructures',{count:total})}</Typography>
    <Typography variant="body2" color="text.secondary">{t('search.independentHint')}</Typography>
    {busy && <Typography role="status">{t('search.structuresLoading')}</Typography>}
    {error && <Alert severity="warning">{t('search.structuresUnavailable')}{error}<Button onClick={() => setRetry(v => v + 1)}>{t('search.retry')}</Button></Alert>}
    {!busy && !error && !items.length && <Typography sx={{ my: 1 }}>{t('search.structuresEmpty')}</Typography>}
    <StructuralCards items={items} from={location.pathname + location.search} />
    <Box sx={{ display: 'flex', gap: 1, my: 1 }}><Button disabled={!page || busy} onClick={() => setPage(page - 1)}>{t('search.previousPage')}</Button><Typography sx={{ alignSelf: 'center' }}>{t('search.pageNumber',{page:page+1})}</Typography><Button disabled={(page + 1) * 20 >= total || busy} onClick={() => setPage(page + 1)}>{t('search.nextPage')}</Button></Box>
  </Box>
}

export default function PaperStructuralCollection({ paperId }: { paperId: number }) {
  const {t} = useLanguage()
  const [items, setItems] = useState<StructuralItem[]>([]), [error, setError] = useState('')
  useEffect(() => {
    let active = true; setItems([]); setError('')
    void api.get<any>(`/api/rag/structural-records/paper/${paperId}`).then(value => { if (active) setItems((value.items || []).filter((item: StructuralItem) => item.kind === 'model' && !item.state_key)) })
      .catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [paperId])
  if (!items.length && !error) return null
  return <Box sx={{ my: 3 }}><Typography variant="h6">{t('search.paperStructures')}</Typography>
    {error && <Alert severity="warning">{error}</Alert>}
    <StructuralCards items={items} />
  </Box>
}

function StructuralCards({ items, from = window.location.pathname + window.location.search }: { items: StructuralItem[]; from?: string }) {
  const {t} = useLanguage()
  return <>{items.map(item => <Card variant="outlined" key={item.id} sx={{ p: 2, my: 1, minWidth: 0 }}>
    <Typography fontWeight={700}>{item.material} · {item.pressure_gpa ?? '压力未报告'} {item.pressure_gpa != null ? 'GPa' : ''} · {item.space_group || '空间群未报告'}</Typography>
    <Typography variant="body2">{item.kind === 'model' ? '完整结构' : item.kind === 'issue' ? '提取问题 · 仅内部核对' : '几何参数 · 无原子位置'}{item.data.calculation_label ? ' · ' + item.data.calculation_label : ''}{item.retention !== 'retained' ? ' · 未公开' : ''}</Typography>
    <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>来源：{item.title} {item.doi ? ' · DOI: ' + item.doi : ''}</Typography>
    <Typography variant="caption" display="block">{item.data.sources?.map((source: any) => [source.filename, source.page ? `第 ${source.page} 页` : '', source.table].filter(Boolean).join(' · ')).join('；')}</Typography>
    <Button component="a" href={detailURL(`/structures/${encodeURIComponent(item.id)}`, from)} target="_blank" rel="noopener noreferrer">{item.kind === 'model' ? '查看结构与下载' : '查看参数与下载'}</Button>
    <Button component="a" href={detailURL(`/papers/${item.paper_id}`, from)} target="_blank" rel="noopener noreferrer">{t('search.viewPaper')}</Button>
  </Card>)}</>
}
