import { Box, MenuItem, TextField, Typography } from '@mui/material'
import AutoGrowingTextField from './AutoGrowingTextField'
import { HULL_BASES, STABILITY, ZPE, emptyHullCase, withStability, validateStability, type ThermodynamicStability, type HullBasis } from '../lib/thermodynamicStability'
import type { PropertyRecordDraft } from '../lib/propertyModules'

export default function ThermodynamicStabilityFields({ record, onChange, readOnly, basePath }: { record: PropertyRecordDraft; onChange: (record: PropertyRecordDraft) => void; readOnly?: boolean; basePath: string }) {
  const data = record.payload.thermodynamic_stability as ThermodynamicStability
  const basis = Object.hasOwn(HULL_BASES, data.basis) ? data.basis : 'unspecified'
  const current = data.cases?.[basis] || emptyHullCase(basis)
  const field = (key: string) => `${basePath ? `${basePath}.` : ''}payload.thermodynamic_stability.cases.${basis}.${key}`
  const update = (patch: Partial<typeof current>) => onChange(withStability(record, { ...data, cases: { ...data.cases, [basis]: { ...current, ...patch } } }))
  const aboveLabel = basis === 'formation_energy' ? 'Energy above hull' : basis === 'formation_enthalpy' ? 'Enthalpy above hull' : basis === 'formation_gibbs' ? 'Gibbs free energy above hull' : 'Above hull（依据未说明）'
  return <Box sx={{ minWidth: 0 }}>
    <Box sx={{ display: 'flex', gap: 1, overflowX: 'auto', py: 1, '& > *': { flex: '0 0 auto', minWidth: 110 } }}>
      <TextField select size="small" label="凸包依据" sx={{ minWidth: 210 }} value={basis} disabled={readOnly} onChange={event => {
        const next = event.target.value as HullBasis
        onChange(withStability(record, { ...data, basis: next, cases: { ...data.cases, [next]: data.cases?.[next] || emptyHullCase(next) } }))
      }}>{Object.entries(HULL_BASES).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField>
      <TextField select size="small" label="相对分解路径的稳定性" sx={{ minWidth: 200 }} value={current.stability} disabled={readOnly} data-issue-field={field('stability')}
        onChange={event => update({ stability: event.target.value as typeof current.stability, ...(event.target.value !== 'unstable' ? { above_hull: null } : {}) })}>
        {Object.entries(STABILITY).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
      </TextField>
      {current.stability === 'unstable' && <>
        <AutoGrowingTextField minFieldWidth={230} label={aboveLabel} type="number" value={current.above_hull ?? ''} disabled={readOnly} data-issue-field={field('above_hull')} slotProps={{ htmlInput: { min: 0, step: 'any' } }} onChange={event => update({ above_hull: event.target.value === '' ? null : Number(event.target.value) })} />
        <TextField size="small" select label="单位" value={current.unit} disabled={readOnly} onChange={event => update({ unit: event.target.value as typeof current.unit })}><MenuItem value="eV/atom">eV/atom</MenuItem><MenuItem value="meV/atom">meV/atom</MenuItem></TextField>
      </>}
      <AutoGrowingTextField label="温度 (K)" type="number" value={current.temperature_k ?? ''} disabled={readOnly || basis === 'formation_energy' || basis === 'formation_enthalpy'} data-issue-field={field('temperature_k')} slotProps={{ htmlInput: { min: 0, step: 'any' } }} onChange={event => update({ temperature_k: event.target.value === '' ? null : Number(event.target.value) })} />
      <TextField select size="small" label="零点振动能 ZPE" sx={{ minWidth: 180 }} value={current.zpe} disabled={readOnly} data-issue-field={field('zpe')} onChange={event => update({ zpe: event.target.value as typeof current.zpe })}>{Object.entries(ZPE).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField>
    </Box>
    <Typography variant="caption" color="text.secondary">压强使用当前材料状态；未报告的数值留空，按论文核对温度和 ZPE。</Typography>
    <Box sx={{ display: 'grid', gap: 1, mt: 1 }}>
      <TextField size="small" label="分解路径" multiline value={current.decomposition_path} disabled={readOnly} data-issue-field={field('decomposition_path')} onChange={event => update({ decomposition_path: event.target.value })} />
      <TextField size="small" label="判据与结论的来源说明" multiline value={current.source_description} disabled={readOnly} data-issue-field={field('source_description')} onChange={event => update({ source_description: event.target.value })} />
    </Box>
    {validateStability(record).map(issue => <Typography key={issue.field} variant="caption" color="error">{issue.message}</Typography>)}
  </Box>
}
