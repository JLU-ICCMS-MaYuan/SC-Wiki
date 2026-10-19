import { useState } from 'react'
import { Box, Button, Typography } from '@mui/material'
import type { JsonSchema } from '../lib/formDefinitions'
import { newStableKey, type PropertyRecordDraft, type PropertyValueKind } from '../lib/propertyModules'
import ScientificFieldBox, { type FieldSettingsPresentation } from './ScientificFieldBox'
import ScientificFieldSettingsDrawer from './ScientificFieldSettingsDrawer'

const stages: Record<string, string> = { electron_phonon: '声子／电声耦合', structural_relaxation: '结构优化', electronic_structure: '电子结构', sscha: 'SSCHA', aimd: '分子动力学', superconductivity: '超导计算' }
const settings: Record<string, string> = { calculation_code: '计算软件', electronic_method: '电子结构方法', exchange_correlation_functional: '交换关联泛函',
  energy_cutoff: '截断能', charge_density_cutoff: '电荷密度截断能', k_grid: 'k 网格', q_grid: 'q 网格', q_grid_interpolated: '插值 q 网格',
  supercell: '超胞', atoms: '原子数', temperature_k: '温度', convergence_energy: '能量收敛阈值', convergence_force: '力收敛阈值', matsubara_frequency_cutoff: 'Matsubara 频率截断' }
export function conditionName(item: Record<string, any>): string {
  if (item.name_raw != null) return item.name_raw
  const [stage, key] = String(item.key || '').split('.')
  return (!item.name || item.name === `${stage} · ${key}` || item.name === item.key) && stages[stage] && settings[key]
    ? `${stages[stage]} · ${settings[key]}` : item.name || item.key || '补充字段'
}
export function conditionValue(item: Record<string, any>): string {
  if (item.value_kind === 'boolean') return item.value_boolean == null ? '' : item.value_boolean ? '是' : '否'
  if (item.value_kind === 'range') return item.value_min == null && item.value_max == null ? '' : `${item.value_min ?? ''}..${item.value_max ?? ''}`
  return String(item.value_kind === 'number' ? item.value_number ?? item.value_raw ?? '' : item.value_text ?? item.value_raw ?? '')
}
const signature = (value: unknown) => JSON.stringify(value)
interface Editing { key?: string; index?: number; recordKey?: string; snapshot: string; name: string; kind: PropertyValueKind; raw: string; unit: string; fixed: boolean }
export default function CalculationConditionFields({ record, schema, readOnly, basePath, onChange }: {
  record: PropertyRecordDraft; schema: JsonSchema; readOnly: boolean; basePath: string; onChange: (record: PropertyRecordDraft) => void
}) {
  const conditions = record.payload.calculation_conditions as Record<string, any> || {}
  const extensions: Record<string, any>[] = conditions.extensions || []
  const [editing, setEditing] = useState<Editing | null>(null), [error, setError] = useState('')
  const [presentation, setPresentation] = useState<FieldSettingsPresentation>()
  const write = (next: Record<string, any>) => onChange({ ...record, payload: { ...record.payload, calculation_conditions: next } })
  const open = (next: Editing, host?: FieldSettingsPresentation) => { setPresentation(host); setError(''); setEditing({ ...next, recordKey: record.record_key }) }
  const rawValue = (key: string) => Array.isArray(conditions[key]) ? conditions[key].join(' × ') : String(conditions[key] ?? '')
  const fixed = Object.entries(schema.properties || {}).filter(([key, child]) => key !== 'extensions' && child.type !== 'object')
  const save = () => {
    if (!editing || readOnly) return
    if (editing.recordKey !== record.record_key) { setError('当前记录已变化，请关闭后重新打开'); return }
    if (!editing.name.trim()) { setError('请填写字段名称'); return }
    if (editing.fixed) {
      const key = editing.key!, child = schema.properties?.[key] || {}
      if (signature([conditions[key], conditions.field_settings?.[key]]) !== editing.snapshot) { setError('字段已发生变化，请关闭后重新打开'); return }
      let value: unknown = editing.raw
      if (['number', 'integer'].includes(child.type || '')) {
        value = editing.raw.trim() === '' ? null : Number(editing.raw)
        if (value != null && (!Number.isFinite(value) || child.type === 'integer' && !Number.isInteger(value)
          || child.minimum != null && Number(value) < child.minimum || child.maximum != null && Number(value) > child.maximum)) { setError('请输入符合字段要求的数值'); return }
      } else if (child.type === 'array') {
        value = editing.raw.trim() ? editing.raw.trim().split(/[x×,\s]+/).map(Number) : null
        if (Array.isArray(value) && (value.some(v => !Number.isFinite(v)) || child.minItems != null && value.length < Number(child.minItems)
          || child.maxItems != null && value.length > Number(child.maxItems))) { setError('请输入完整有效的网格'); return }
      }
      if (child.enum && !child.enum.includes(value as string)) { setError('值不在该字段允许的选项中'); return }
      write({ ...conditions, [key]: value, field_settings: { ...(conditions.field_settings || {}), [key]: { name_raw: editing.name.trim(), unit_raw: editing.unit.trim() } } })
      setEditing(null); return
    }
    const previous = editing.index == null ? undefined : extensions[editing.index]
    if (editing.index != null && signature(previous) !== editing.snapshot) { setError('字段已发生变化，请关闭后重新打开'); return }
    const raw = editing.raw.trim(), next: Record<string, any> = { ...previous, field_key: previous?.field_key || newStableKey('field'), name_raw: editing.name.trim(), value_kind: editing.kind, value_raw: editing.raw, unit_raw: editing.unit.trim() }
    for (const key of ['value_number', 'value_min', 'value_max', 'value_text', 'value_boolean']) delete next[key]
    if (editing.kind === 'number') {
      if (raw && !Number.isFinite(Number(raw))) { setError('请输入完整数值'); return }
      next.value_number = raw ? Number(raw) : null
    } else if (editing.kind === 'range') {
      const pair = raw.split('..').map(v => v.trim())
      if (raw && (pair.length !== 2 || pair.some(v => !v || !Number.isFinite(Number(v))) || Number(pair[0]) > Number(pair[1]))) { setError('范围格式为下界..上界，且下界不大于上界'); return }
      next.value_min = raw ? Number(pair[0]) : null; next.value_max = raw ? Number(pair[1]) : null
    } else if (editing.kind === 'boolean') next.value_boolean = raw === '' ? null : raw === 'true'
    else next.value_text = editing.raw
    const updated = [...extensions]
    if (editing.index == null) updated.push(next); else updated[editing.index] = next
    write({ ...conditions, extensions: updated }); setEditing(null)
  }
  return <Box sx={{ minWidth: 0 }}>
    <Typography variant="body2" color="text.secondary">计算条件</Typography>
    <Box data-condition-row sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, py: 1 }}>
      {fixed.map(([key, child]) => {
        const display = conditions.field_settings?.[key], name = display?.name_raw || child.title || settings[key] || key
        return <ScientificFieldBox key={key} name={name} value={rawValue(key)} readOnly={readOnly} numeric={['number', 'integer'].includes(child.type || '')} field={`${basePath}.${key}`}
          onChange={value => write({ ...conditions, [key]: ['number', 'integer'].includes(child.type || '') ? value === '' ? null : Number(value) : child.type === 'array' ? value.split(/[x×,\s]+/).filter(Boolean).map(Number) : value })}
          onSettings={host => open({ fixed: true, key, snapshot: signature([conditions[key], display]), name, kind: ['number', 'integer'].includes(child.type || '') ? 'number' : 'text', raw: rawValue(key), unit: display?.unit_raw || '', }, host)} />
      })}
      {extensions.filter(item => !String(item.key || '').startsWith('structural_relaxation.')).map(item => {
        const index = extensions.indexOf(item)
        return <ScientificFieldBox key={item.field_key || item.key || index} name={conditionName(item)} value={conditionValue(item)} readOnly={readOnly} field={`${basePath}.extensions.${index}.value_raw`} fieldKey={item.field_key || item.key}
          error={item.value_kind === 'number' && item.value_raw && (item.value_number == null || !Number.isFinite(item.value_number)) ? '请输入完整有效的数值' : undefined}
          onChange={['text', 'number'].includes(item.value_kind || 'text') ? raw => {
            const updated = { ...item, value_raw: raw, ...(item.value_kind === 'number' ? { value_number: raw.trim() ? Number(raw) : null } : { value_text: raw }) }
            write({ ...conditions, extensions: extensions.map((entry, i) => i === index ? updated : entry) })
          } : undefined}
          onSettings={host => open({ index, fixed: false, snapshot: signature(item), name: conditionName(item), kind: item.value_kind || 'text',
            raw: item.value_kind === 'boolean' ? item.value_boolean == null ? '' : String(item.value_boolean) : conditionValue(item), unit: item.unit_raw || '' }, host)} />
      })}
    </Box>
    {!readOnly && <Button size="small" onClick={() => open({ fixed: false, snapshot: '', name: '', raw: '', unit: '', kind: 'number' })}>＋ 新增字段</Button>}
    {extensions.some(item => String(item.key || '').startsWith('structural_relaxation.')) && <Typography variant="caption" component="p" color="text.secondary">结构优化阶段的设置保留在原记录和导出中，不作为当前超导计算条件展示。</Typography>}
    <ScientificFieldSettingsDrawer presentation={presentation} value={editing} readOnly={readOnly} typeLocked={editing?.fixed}
      adding={editing?.index == null && !editing?.fixed} error={error}
      onChange={value => setEditing(current => current && { ...current, ...value })} onApply={save} onClose={() => setEditing(null)}
      onDelete={editing?.index == null ? undefined : () => {
        if (editing.recordKey !== record.record_key || signature(extensions[editing.index!]) !== editing.snapshot) { setError('字段已发生变化，请关闭后重新打开'); return }
        write({ ...conditions, extensions: extensions.filter((_, i) => i !== editing.index) }); setEditing(null)
      }} />
  </Box>
}
