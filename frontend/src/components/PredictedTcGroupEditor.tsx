import { useId } from 'react'
import { Alert, Box, Button, Checkbox, FormControl, IconButton, InputLabel, MenuItem, Select, TextField, Tooltip, Typography } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import type { FormDefinition, FormIssue } from '../lib/formDefinitions'
import { newStableKey, type PropertyRecordDraft } from '../lib/propertyModules'
import { muRangeIndex, readTcParameter, setTcParameter } from '../lib/tcParameters'
import { completeTcNumber, completeTcMu, expandTcPoints, newTcPoint, selectTcPoint, setTcMethodValue, tcGroupMeta, tcMethodKey, tcPointKey, tcPointViews, updateTcCommon, updateTcPoint } from '../lib/predictedTcGroups'
import TcScientificField from './TcScientificField'
import SchemaDrivenRecordForm from './SchemaDrivenRecordForm'
import PropertyRecordRow from './PropertyRecordRow'
import { scientificNumberText } from '../lib/scientificNumberText'

interface Props {
  records: PropertyRecordDraft[]
  definitions: FormDefinition[]
  definition?: FormDefinition
  errors?: string[]
  issues: FormIssue[]
  basePath: string
  recordIndices: Map<string, number>
  readOnly: boolean
  onChange: (records: PropertyRecordDraft[], selected?: boolean) => void
}
const names: Record<string, string> = { isotropic_eliashberg: '各向同性 Eliashberg', anisotropic_eliashberg: '各向异性 Eliashberg',
  allen_dynes: 'Allen–Dynes 修正 McMillan', mcmillan: 'McMillan', scdft: '超导密度泛函理论 SCDFT', other: '其他方法', unknown: '未说明方法' }

export default function PredictedTcGroupEditor({ records, definitions, definition, errors = [], issues, basePath, recordIndices, readOnly, onChange }: Props) {
  const helpId = useId(), root = records[0]
  const path = (record: PropertyRecordDraft) => `${basePath}.records.${recordIndices.get(record.record_key)}`
  const rootPath = path(root)
  const selected = records.flatMap(tcPointViews).find(point => point.selected)
  const methods = [...new Set(records.map(tcMethodKey))]
  const choices = definitions.filter(d => d.record_type === 'predicted_tc')
  const error = (field: string) => issues.find(i => i.field === field)?.message
  const replaceMethod = (method: string, value: string) => {
    const d = choices.find(item => item.method_code === value)
    if (!d) return
    onChange(records.flatMap(record => {
      if (tcMethodKey(record) !== method) return [record]
      return expandTcPoints([record]).map(point => ({
        ...setTcMethodValue(point, 'method_code', value), definition_key: d.definition_key, definition_version: d.version,
      }))
    }))
  }
  const parameter = (key: 'lambda_ep' | 'omega_log', label: string, unit?: string) => <Box sx={{ width: 170, flex: '0 0 auto' }}>
    <TcScientificField label={label} value={readTcParameter(root, key)} readOnly={readOnly} field={`${rootPath}.payload.parameters.${key}`} unit={unit}
      settings={(root.payload.parameters as any)?.field_settings?.[key]}
      error={error(`${rootPath}.payload.parameters.${key}`)} onChange={value => onChange(updateTcCommon(records, { ...root, payload: setTcParameter(root, key, value) }))}
      onApply={(value, settings) => {
        const payload = setTcParameter(root, key, value), parameters = payload.parameters as Record<string, any>
        parameters.field_settings = { ...(parameters.field_settings || {}), [key]: settings }
        onChange(updateTcCommon(records, { ...root, payload }))
      }} />
  </Box>
  const core = <Box data-testid="predicted-tc-core" sx={{ minWidth: 0 }}>
    {records.filter(r => !['number', 'range'].includes(r.value_kind)).map(r => <Alert key={r.record_key} severity="warning" sx={{ mb: 1 }}>
      原提取内容不是可填写的 Tc 数值：{r.value_text || r.value_raw}。请通过来源核对查找数值，或在下方填写；原内容保留。
    </Alert>)}
    <Box data-testid="tc-parameter-line" sx={{ display: 'flex', gap: 1, overflowX: 'auto', py: 1 }}>
      {parameter('lambda_ep', '电声耦合强度 λ')}{parameter('omega_log', 'ωlog', 'K')}
    </Box>
    <Typography id={helpId} variant="caption" color="text.secondary" component="p" sx={{ my: 1 }}>
      勾选 Tc 前的方框，将该预测方法、该 μ* 对应的 Tc 作为代表结果。同一材料状态只选一组，改选会取消原选择，再次点击可取消。请先填写 Tc 和 μ*；μ* 可明确填写“不适用”“未报告”或“未知”。
    </Typography>
    {records.some(r => r.value_kind === 'range' && r.is_representative) && <Alert severity="info" sx={{ mb: 1 }}
      action={readOnly ? undefined : <Button size="small" onClick={() => onChange(records.map(r => r.value_kind === 'range' ? { ...r, is_representative: false } : r))}>取消旧标记</Button>}>
      旧范围尚未明确代表端点，请选择具体 Tc／μ* 组合。</Alert>}
    <Typography variant="caption" component="p" color="primary" aria-live="polite" sx={{ my: 1 }}>
      {selected ? `代表结果：${names[selected.record.method_code || ''] || selected.record.method_code} · μ* = ${selected.mu ?? '待填写'} · Tc = ${selected.tc == null ? '待填写' : scientificNumberText(selected.tc, selected.record.value_raw, 'K')} K` : '本组尚未选择代表结果'}
    </Typography>
    {methods.map((method, methodIndex) => {
      const members = records.filter(r => tcMethodKey(r) === method), first = members[0]
      const points = members.flatMap(tcPointViews)
      const metadata = tcGroupMeta(first)
      return <Box key={method} role="group" data-record-key={first.record_key} aria-label={`第${methodIndex + 1}种预测方法`}>
        <PropertyRecordRow actions={readOnly ? undefined : <Tooltip title="删除本方法及其全部组合"><IconButton color="error" size="small" aria-label={`删除第${methodIndex + 1}种方法`}
          onClick={() => onChange(records.filter(r => tcMethodKey(r) !== method))}><DeleteIcon /></IconButton></Tooltip>}>
          <Box data-testid="tc-method-line" sx={{ display: 'flex', alignItems: 'center', gap: 1, overflowX: 'auto', py: 1, '& > *': { flex: '0 0 auto' } }}>
            <FormControl size="small" sx={{ width: 220 }} data-issue-field={`${path(first)}.method_code`}>
              <InputLabel id={`${helpId}-${methodIndex}`}>预测方法</InputLabel>
              <Select labelId={`${helpId}-${methodIndex}`} label="预测方法" value={first.method_code || 'unknown'} disabled={readOnly}
                onChange={event => replaceMethod(method, event.target.value)}>
                {Object.entries(names).map(([code, label]) => <MenuItem key={code} value={code}>{label}</MenuItem>)}
              </Select>
            </FormControl>
            {first.method_code === 'other' && <TextField size="small" label="具体方法名称" value={metadata?.method_name ?? first.method_raw ?? ''}
              disabled={readOnly} sx={{ width: 220 }} data-issue-field={`${path(first)}.method_raw`}
              onChange={event => onChange(records.map(record => tcMethodKey(record) === method
                ? setTcMethodValue(record, 'method_raw', event.target.value) : record))} />}
            {!readOnly && <Button size="small" aria-label="添加 Tc／μ* 组合" startIcon={<AddIcon />} onClick={() => {
              const expanded = expandTcPoints(records), template = expanded.find(r => tcMethodKey(r) === method)!
              onChange([...expanded, newTcPoint(template, method)])
            }}>组合</Button>}
            {points.map((point, index) => {
              const lower = point.key === `${point.record.record_key}:0`
              const tcField = point.record.value_kind === 'range' ? lower ? 'value_min' : 'value_max' : 'value_number'
              const extension = muRangeIndex(point.record)
              const muField = point.record.value_kind === 'range' && extension >= 0
                ? `payload.parameters.extensions.${extension}.${lower ? 'value_max' : 'value_min'}` : 'payload.parameters.mu_star'
              return <Box key={point.key} role="group" aria-label={`第${index + 1}组 Tc 与 μ*`} data-record-key={point.record.record_key}
                sx={{ display: 'flex', alignItems: 'center', gap: 1, p: '12px 8px', borderRadius: 1, bgcolor: theme => theme.palette.mode === 'dark' ? '#302c43' : '#F4F3FF' }}>
                <Checkbox size="small" sx={{ p: 0, alignSelf: 'center', flex: '0 0 auto' }} checked={point.selected}
                  disabled={readOnly || !completeTcNumber(point.tc) || !completeTcMu(point.record, point.mu)}
                  slotProps={{ input: { 'aria-label': `选择第${methodIndex + 1}种方法第${index + 1}组为代表结果`, 'aria-describedby': helpId } }}
                  data-issue-field={`${path(point.record)}.is_representative`}
                  onChange={(_, checked) => onChange(selectTcPoint(records, point.key, checked), checked)} />
                <Box sx={{ width: 150 }}><TcScientificField value={point.tc} label="Tc" unit="K" readOnly={readOnly} currentTc
                  field={`${path(point.record)}.${tcField}`} error={error(`${path(point.record)}.${tcField}`)}
                  settings={(point.record.payload.field_settings as any)?.tc}
                  onApply={(value, settings) => onChange(updateTcPoint(records, point.key, 'tc', value).map(r => tcPointKey(r) === point.key
                    ? { ...r, payload: { ...r.payload, field_settings: { ...(r.payload.field_settings as any || {}), tc: settings } } } : r))}
                  onChange={value => onChange(updateTcPoint(records, point.key, 'tc', value))} /></Box>
                <Box sx={{ width: 150 }}><TcScientificField value={point.mu} label="μ*" readOnly={readOnly}
                  emptyLabel={({not_applicable:'不适用',not_reported:'未报告',unknown:'未知'} as Record<string,string>)[String((point.record.payload.parameters as any)?.mu_star_status)] || ''}
                  field={`${path(point.record)}.${muField}`} error={error(`${path(point.record)}.${muField}`)}
                  settings={(point.record.payload.field_settings as any)?.mu_star}
                  onApply={(value, settings) => onChange(updateTcPoint(records, point.key, 'mu', value).map(r => tcPointKey(r) === point.key
                    ? { ...r, payload: { ...r.payload, field_settings: { ...(r.payload.field_settings as any || {}), mu_star: settings } } } : r))}
                  onChange={value => onChange(updateTcPoint(records, point.key, 'mu', value))} /></Box>
                {!readOnly && <IconButton size="small" color="error" disabled={points.length === 1} aria-label={`删除第${index + 1}组组合`}
                  onClick={() => onChange(expandTcPoints(records).filter(r => tcPointKey(r) !== point.key))}><DeleteIcon fontSize="small" /></IconButton>}
              </Box>
            })}
          </Box>
        </PropertyRecordRow>
      </Box>
    })}
    {!readOnly && <Button size="small" startIcon={<AddIcon />} onClick={() => {
      const expanded = expandTcPoints(records), unknown = choices.find(d => d.method_code === 'unknown')
      onChange([...expanded, newTcPoint(expanded[0], newStableKey('tc-method'), unknown)])
    }}>新增字段</Button>}
    {[...new Set([...errors, ...issues.filter(i => records.some(r => i.field.startsWith(path(r)+'.'))).map(i => i.message)].filter(Boolean))]
      .map((message, index) => <Alert severity="error" key={index}>{message}</Alert>)}
  </Box>
  return <SchemaDrivenRecordForm record={root} definition={definition} issues={issues} basePath={rootPath} readOnly={readOnly}
    tcCore={core} onChange={next => onChange(updateTcCommon(records, next))} />
}
