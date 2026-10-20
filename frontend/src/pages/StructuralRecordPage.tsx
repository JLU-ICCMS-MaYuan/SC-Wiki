import { useEffect, useState } from 'react'
import { Alert, Box, Button, MenuItem, TextField, Typography } from '@mui/material'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import StructuralRecordView, { type StructuralItem } from '../components/StructuralRecordView'

export default function StructuralRecordPage() {
  const { recordId } = useParams(), [item, setItem] = useState<StructuralItem | null>(null), [error, setError] = useState('')
  const [cell, setCell] = useState<'primitive' | 'conventional'>('conventional')
  useEffect(() => {
    let active = true; setItem(null); setError('')
    void api.get<StructuralItem>('/api/rag/structural-records/' + encodeURIComponent(recordId || ''))
      .then(value => { if (active) setItem(value) }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [recordId])
  const download = async (format: string) => {
    if (!item) return
    try {
      const blob = await api.download(`/api/rag/structural-records/${encodeURIComponent(item.id)}/download?format=${format}&cell=${cell}`)
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      link.href = url; link.download = `${item.material}-${item.pressure_gpa ?? 'unknown'}GPa.${format}`; link.click(); URL.revokeObjectURL(url)
    } catch (reason: any) { setError(reason.message) }
  }
  return <Box sx={{ minWidth: 0, pb: 4 }}>
    <Button component={Link} to="/search">返回元素搜索</Button>
    {error && <Alert severity="error">{error}</Alert>}
    {!item && !error && <Typography role="status">正在读取结构资料…</Typography>}
    {item && <><Typography variant="h5" sx={{ my: 2 }}>{item.material} · {item.pressure_gpa ?? '未知压力'} GPa · {item.space_group}</Typography>
      <Typography>来源：{item.title}{item.doi ? ' · DOI: ' + item.doi : ''} · 论文版本 {item.paper_revision}</Typography>
      <Button component={Link} to={`/papers/${item.paper_id}`}>查看来源论文</Button>
      <Button onClick={() => void download('json')}>下载带来源 JSON</Button>
      {item.kind === 'model' && <TextField select size="small" label="晶胞表示" value={cell} onChange={event => setCell(event.target.value as typeof cell)} sx={{ minWidth: 140, my: 1 }}><MenuItem value="conventional">惯用胞</MenuItem><MenuItem value="primitive">原胞</MenuItem></TextField>}
      {item.kind === 'model' ? <><Button onClick={() => void download('cif')}>下载 CIF</Button><Button onClick={() => void download('poscar')}>下载 POSCAR</Button></> : <Button onClick={() => void download('csv')}>下载 CSV</Button>}
      <StructuralRecordView item={item} cell={cell} />
    </>}
  </Box>
}
