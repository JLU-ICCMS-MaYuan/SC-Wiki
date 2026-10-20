import { Alert, Box, Typography } from '@mui/material'
import CrystalStructureView from './CrystalStructureView'
import StructureCandidateSource from './StructureCandidateSource'
import { useEffect, useRef, useState } from 'react'

export interface StructuralItem {
  id: string; kind: 'model' | 'lattice' | 'issue'; material: string; pressure_gpa?: number | null; space_group?: string
  data: any; title?: string; doi?: string; paper_id?: number; paper_revision?: number; retention?: string; state_key?: string | null
}

export default function StructuralRecordView({ item, cell = 'conventional' }: { item: StructuralItem; cell?: 'primitive' | 'conventional' }) {
  const value = item.data
  if (item.kind === 'issue') return <Box><Alert severity="warning">{value.reason || value.validation?.message || '结构提取待核对'}</Alert><StructureCandidateSource candidate={{ candidate_id: item.id, ...value }} showModelStatus={false} /></Box>
  if (item.kind === 'model') {
    const text = value.representations?.[cell]?.cif?.text
    return <Box sx={{ minWidth: 0 }}>
      {text && <Box component="details" sx={{ mt: 1 }}>
        <Typography component="summary" sx={{ cursor: 'pointer' }}>查看三维结构</Typography>
        <LazyModel text={text} />
      </Box>}
      <StructureCandidateSource candidate={value} />
    </Box>
  }
  return <Box sx={{ minWidth: 0 }}>
    <Typography variant="body2">{value.calculation_label || '近似分组待核对'} · 原文未报告原子位置</Typography>
    <Typography variant="body2" sx={{ mt: 1 }}>原文晶格参数（长度 Å，角度 °，体积 Å³）：{Object.entries(value.cell_parameters || {}).map(([key, v]) => `${key} = ${v}`).join('，')}</Typography>
    {!!Object.keys(value.derived_cell_parameters || {}).length && <Typography variant="caption" display="block">对称性派生（长度 Å，角度 °）：{Object.entries(value.derived_cell_parameters).map(([key, v]) => `${key} = ${v}`).join('，')}</Typography>}
    {(value.bond_lengths || []).map((bond: any, index: number) => <Typography key={index} variant="body2">{bond.pair}：{bond.min}–{bond.max} Å</Typography>)}
    <StructureCandidateSource candidate={{ candidate_id: value.record_key, sources: value.sources }} showModelStatus={false} />
  </Box>
}

function LazyModel({ text }: { text: string }) {
  // 展开时才挂载 WebGL，避免一个资料集合同时创建许多画布。
  const host = useRef<HTMLDivElement>(null), [visible, setVisible] = useState(false)
  useEffect(() => {
    const details = host.current?.closest('details')
    const update = () => { if (details?.open) setVisible(true) }
    details?.addEventListener('toggle', update); update()
    return () => details?.removeEventListener('toggle', update)
  }, [])
  return <Box ref={host}>{visible && <CrystalStructureView data={text} format="cif" />}</Box>
}
