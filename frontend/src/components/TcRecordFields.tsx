import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import PropertyRecordRow from './PropertyRecordRow'
import {
  Box, Checkbox, FormControl, FormControlLabel, InputAdornment, InputLabel,
  MenuItem, Select, TextField,
} from '@mui/material'
import type { PropertyRecordDraft, PropertyValueKind } from '../lib/propertyModules'
import {
  muRangeIndex, readTcPairs, readTcParameter, setTcPairs, setTcParameter, tcKindParameters,
  type ParameterValue, type TcPair,
} from '../lib/tcParameters'

interface Props {
  record: PropertyRecordDraft
  readOnly: boolean
  issue: (field: string) => string | undefined
  fieldPath: (field: string) => string
  update: (patch: Partial<PropertyRecordDraft>) => void
  actions?: ReactNode
}

const numberPattern = /^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/

/** 保留小数/指数编辑文本；可选参数的非法文本也必须进入保存校验。 */
function TcNumber({ value, label, field, error, readOnly, onChange, unit, currentTc = false }: {
  value: ParameterValue; label: string; field: string; error?: string; readOnly: boolean
  onChange: (value: ParameterValue) => void; unit?: string; currentTc?: boolean
}) {
  const [text, setText] = useState(String(value ?? ''))
  const published = useRef(value)
  useEffect(() => {
    if (!Object.is(value, published.current)) setText(String(value ?? ''))
    published.current = value
  }, [value])
  const valid = numberPattern.test(text) && Number.isFinite(Number(text))
  const message = text !== '' && !valid ? '请输入完整的非负数值' : error
  return <TextField size="small" fullWidth label={label} value={text} disabled={readOnly}
    data-issue-field={field} data-tc-current-value={currentTc || undefined} error={Boolean(message)} helperText={message}
    slotProps={{ htmlInput: { inputMode: 'decimal' }, input: unit ? { endAdornment: <InputAdornment position="end">{unit}</InputAdornment> } : undefined }}
    onChange={event => {
      const next = event.target.value
      setText(next)
      const value = next === '' ? null : numberPattern.test(next) && Number.isFinite(Number(next)) ? Number(next) : next
      published.current = currentTc && typeof value === 'string' ? null : value
      onChange(value)
    }} />
}

const signature = (record: PropertyRecordDraft) => JSON.stringify([
  record.record_key, record.value_kind, record.value_number, record.value_min, record.value_max, record.payload.parameters,
])

export default function TcRecordFields({ record, readOnly, issue, fieldPath, update, actions }: Props) {
  const kindLabel = useId(), predicted = record.record_type === 'predicted_tc', range = record.value_kind === 'range'
  const [pairs, setPairs] = useState(() => readTcPairs(record))
  const published = useRef(signature(record))
  useEffect(() => {
    const next = signature(record)
    if (next !== published.current) setPairs(readTcPairs(record))
    published.current = next
  }, [record])
  const emit = (patch: Partial<PropertyRecordDraft>) => {
    published.current = signature({ ...record, ...patch })
    update(patch)
  }
  const changePair = (index: 0 | 1, key: keyof TcPair, value: ParameterValue) => {
    const next: [TcPair, TcPair] = [{ ...pairs[0] }, { ...pairs[1] }]
    next[index] = { ...next[index], [key]: key === 'tc' && typeof value === 'string' ? null : value }
    setPairs(next)
    emit(setTcPairs(record, next))
  }
  const parameter = (key: 'lambda_ep' | 'omega_log' | 'mu_star', label: string, unit?: string) => {
    const path = `payload.parameters.${key}`
    return <Box sx={{ flex: key === 'lambda_ep' ? '1 0 130px' : '1 0 110px' }}>
      <TcNumber value={readTcParameter(record, key)} label={label} field={fieldPath(path)}
        error={issue(path) || issue(`${path}.value_number`)} readOnly={readOnly} unit={unit}
        onChange={value => emit({ payload: setTcParameter(record, key, value) })} />
    </Box>
  }
  const pair = (index: 0 | 1) => {
    // 规范端点变化时只更新锚点，不移动用户正在编辑的配对。
    const reversed = pairs[0].tc != null && pairs[1].tc != null && pairs[0].tc > pairs[1].tc
    const minimum = (index === 0) !== reversed
    const tcField = range ? minimum ? 'value_min' : 'value_max' : 'value_number'
    const extension = muRangeIndex(record)
    const muField = range && extension >= 0
      ? `payload.parameters.extensions.${extension}.${minimum ? 'value_max' : 'value_min'}` : 'payload.parameters.mu_star'
    return <Box key={index} role="group" aria-label={`${index === 0 ? '第一组' : '第二组'} Tc${predicted ? ' 与 μ*' : ''}`}
      data-testid={`tc-pair-${index}`} sx={{ display: 'flex', gap: 1, flex: predicted ? '2 0 236px' : '1 0 116px',
        alignItems: 'start', px: predicted ? 1 : 0, py: predicted ? 1.5 : 0, borderRadius: 1,
        bgcolor: predicted ? theme => theme.palette.mode === 'dark' ? '#302c43' : '#F4F3FF' : undefined,
        '& > *': { minWidth: 0, flex: 1 } }}>
      <TcNumber value={pairs[index].tc} label={range ? 'Tc' : 'Tc 值'} field={fieldPath(tcField)} currentTc unit="K"
        error={issue(tcField)} readOnly={readOnly} onChange={value => changePair(index, 'tc', value)} />
      {predicted && <TcNumber value={pairs[index].mu} label="μ*" field={fieldPath(muField)}
        error={issue(muField) || issue('payload.parameters.mu_star')} readOnly={readOnly} onChange={value => changePair(index, 'mu', value)} />}
    </Box>
  }
  const changeKind = (kind: PropertyValueKind) => {
    if (kind === record.value_kind) return
    const payload = tcKindParameters(record, kind, pairs[0].mu)
    const next = { ...record, payload, value_kind: kind, value_number: null, value_min: null, value_max: null,
      value_text: kind === 'text' ? '' : null, value_boolean: kind === 'boolean' ? false : null }
    setPairs(readTcPairs(next))
    emit(next)
  }
  return <PropertyRecordRow actions={actions}><Box data-testid="tc-core-row" sx={{ gridColumn: '1 / -1', minWidth: 0, overflowX: 'auto', py: 1 }}>
    <Box data-testid="tc-input-line" sx={{ display: 'flex', flexWrap: 'nowrap', alignItems: 'center', gap: 1, minWidth: predicted ? range ? 1100 : 860 : range ? 720 : 600 }}>
      {predicted && <>{parameter('lambda_ep', '电声耦合强度 λ')}{parameter('omega_log', 'ωlog', 'K')}</>}
      <TextField size="small" label="名称" value={record.name_raw} disabled={readOnly} sx={{ flex: '1.5 0 190px' }}
        data-issue-field={fieldPath('name_raw')} error={Boolean(issue('name_raw'))} helperText={issue('name_raw')}
        onChange={event => emit({ name_raw: event.target.value })} />
      <FormControl size="small" sx={{ flex: '0 0 90px' }} data-issue-field={fieldPath('value_kind')} error={Boolean(issue('value_kind'))}>
        <InputLabel id={kindLabel}>值类型</InputLabel>
        <Select labelId={kindLabel} label="值类型" value={record.value_kind} disabled={readOnly} onChange={event => changeKind(event.target.value as PropertyValueKind)}>
          <MenuItem value="number">数值</MenuItem><MenuItem value="range">范围</MenuItem>
          <MenuItem value="text">文本</MenuItem><MenuItem value="boolean">布尔</MenuItem>
        </Select>
      </FormControl>
      {(range || record.value_kind === 'number') && pair(0)}
      {range && pair(1)}
      {record.value_kind === 'text' && <TextField size="small" label="文本值" value={record.value_text ?? ''} disabled={readOnly} sx={{ flex: '1 0 180px' }}
        data-issue-field={fieldPath('value_text')} data-tc-current-value error={Boolean(issue('value_text'))} helperText={issue('value_text')}
        onChange={event => emit({ value_text: event.target.value })} />}
      {record.value_kind === 'boolean' && <FormControlLabel label="布尔值" data-issue-field={fieldPath('value_boolean')} data-tc-current-value
        control={<Checkbox checked={Boolean(record.value_boolean)} disabled={readOnly} onChange={event => emit({ value_boolean: event.target.checked })} />} />}
      {predicted && ['text', 'boolean'].includes(record.value_kind) && parameter('mu_star', 'μ*')}
      <FormControlLabel label="代表结果" data-issue-field={fieldPath('is_representative')} sx={{ m: 0, whiteSpace: 'nowrap', flexShrink: 0 }}
        control={<Checkbox checked={Boolean(record.is_representative)} disabled={readOnly} onChange={event => emit({ is_representative: event.target.checked })} />} />
    </Box>
  </Box></PropertyRecordRow>
}
