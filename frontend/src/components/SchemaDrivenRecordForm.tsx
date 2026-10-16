import React, { useMemo } from 'react'
import {
  Alert, Box, Button, Checkbox, FormControl, FormControlLabel, InputLabel, MenuItem, Select, TextField, Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import AutoGrowingTextField from './AutoGrowingTextField'
import ThermodynamicStabilityFields from './ThermodynamicStabilityFields'
import { isThermodynamicStability } from '../lib/thermodynamicStability'
import TcRecordFields from './TcRecordFields'
import PropertyRecordRow from './PropertyRecordRow'
import { DOS_SOURCE_KEY, hasDosConflict, isFermiDos } from '../lib/fermiDos'
import { muRangeIndex } from '../lib/tcParameters'
import type { FormDefinition, FormIssue, JsonSchema } from '../lib/formDefinitions'
import { getAtPath, setAtPath, validateRecordClient } from '../lib/formDefinitions'
import { newStableKey, normalizeCurrentTcValue, type PropertyRecordDraft, type PropertyValueKind } from '../lib/propertyModules'

interface Props {
  record: PropertyRecordDraft
  definition?: FormDefinition
  definitionError?: string
  issues?: FormIssue[]
  basePath?: string
  readOnly?: boolean
  onChange: (record: PropertyRecordDraft) => void
  onDelete?: () => void
}

const VALUE_KIND_LABELS: Record<PropertyValueKind, string> = {
  number: '数值', range: '范围', text: '文本', boolean: '布尔',
}

const FALLBACK_GROUP_SCHEMAS: Record<string, JsonSchema> = {
  calculation_conditions: {
    type: 'object',
    title: '计算条件',
    properties: {
      calculation_code: { type: 'string', title: '计算软件' },
      electronic_method: { type: 'string', title: '电子结构方法' },
      exchange_correlation_functional: { type: 'string', title: '交换关联泛函' },
      k_grid: { type: 'string', title: 'k 网格' },
      q_grid: { type: 'string', title: 'q 网格' },
      k_broadening: { type: 'number', title: 'k 展宽' },
      q_broadening: { type: 'number', title: 'q 展宽' },
      extensions: { type: 'array', title: '补充计算条件', items: { type: 'object' } },
    },
  },
  experimental_conditions: {
    type: 'object',
    title: '实验 Conditions',
  },
  parameters: {
    type: 'object',
    title: '参数',
    properties: {
      lambda_ep: { type: 'number', title: '电声耦合强度 λ', minimum: 0 },
      omega_log: { type: 'number', title: 'ωlog (K)', minimum: 0 },
      mu_star: { type: 'number', title: 'μ*', minimum: 0 },
      extensions: { type: 'array', title: '补充参数', items: { type: 'object' } },
    },
  },
}

// 仅在旧实验条件的显示边界转换；编辑 description 不删除原始字段或证据。
const experimentalConditionsText = (value: unknown): string => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return ''
  const conditions = value as Record<string, unknown>
  if (typeof conditions.description === 'string') return conditions.description
  const labels: Record<string, string> = {
    sample: '样品', preparation_method: '制备方式', measurement_method: '测量方法',
    apparatus: '测量装置', external_field_t: '外场 (T)', pressure_uncertainty_gpa: '压力不确定度 (GPa)',
    extensions: '其他实验信息',
  }
  return Object.entries(conditions)
    .filter(([, item]) => item != null && item !== '' && !(Array.isArray(item) && item.length === 0))
    .map(([key, item]) => `${labels[key] || key}：${typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)}`)
    .join('\n')
}

const titleFor = (definition: FormDefinition | undefined, path: string, schema: JsonSchema, fallback: string): string => {
  const fields = definition?.ui_schema?.fields
  const pointer = `/${path.replace(/\./g, '/')}`
  const configured = Array.isArray(fields)
    ? fields.find((item: any) => item?.pointer === pointer || item?.path === path)
    : fields?.[path] || fields?.[pointer]
  return configured?.label || configured?.title || schema.title || fallback
}

const effectivePayloadSchema = (definition: FormDefinition | undefined, recordType: PropertyRecordDraft['record_type']): JsonSchema => {
  const schema = structuredClone(definition?.json_schema || { type: 'object', properties: {} }) as JsonSchema
  schema.type ||= 'object'
  const properties: Record<string, JsonSchema> = schema.properties || {}
  schema.properties = properties
  if (recordType === 'predicted_tc') {
    properties.calculation_conditions ||= FALLBACK_GROUP_SCHEMAS.calculation_conditions
    properties.parameters ||= FALLBACK_GROUP_SCHEMAS.parameters
  } else if (recordType === 'measured_tc') {
    properties.experimental_conditions ||= FALLBACK_GROUP_SCHEMAS.experimental_conditions
  }
  if (recordType === 'property' && definition?.property_code === 'custom' && schema.additionalProperties !== false) {
    properties.parameters ||= { type: 'object', properties: { extensions: FALLBACK_GROUP_SCHEMAS.parameters.properties!.extensions } }
    properties.calculation_conditions ||= { type: 'object', properties: { extensions: FALLBACK_GROUP_SCHEMAS.calculation_conditions.properties!.extensions } }
  }
  for (const [group, fallback] of Object.entries(FALLBACK_GROUP_SCHEMAS)) {
    const declared = properties[group]
    if (!declared) continue
    properties[group] = {
      ...fallback,
      ...declared,
      properties: { ...(recordType === 'predicted_tc' ? fallback.properties : {}), ...(declared.properties || {}) },
    }
  }
  return schema
}

const parseGridOrText = (raw: string, schema: JsonSchema): unknown => {
  if (schema.type !== 'array') return raw
  return raw.split(/[x,\s]+/).map(item => Number(item)).filter(Number.isFinite)
}

const extensionValuePatch = (item: Record<string, any>, kind: PropertyValueKind, raw: string): Record<string, any> => {
  const next: Record<string, any> = { ...item, value_kind: kind, value_raw: raw }
  delete next.value_number
  delete next.value_min
  delete next.value_max
  delete next.value_text
  delete next.value_boolean
  if (kind === 'number') next.value_number = raw === '' ? null : Number(raw)
  if (kind === 'text') next.value_text = raw
  if (kind === 'boolean') next.value_boolean = raw === 'true'
  return next
}

const SchemaDrivenRecordForm: React.FC<Props> = ({
  record,
  definition,
  definitionError = '',
  issues: externalIssues = [],
  basePath = '',
  readOnly = false,
  onChange,
  onDelete,
}) => {
  const issues = useMemo(() => [...validateRecordClient(record, definition), ...externalIssues], [record, definition, externalIssues])
  const payloadSchema = useMemo(() => effectivePayloadSchema(definition, record.record_type), [definition, record.record_type])
  const isTc = record.record_type === 'predicted_tc' || record.record_type === 'measured_tc'
  const isDosFermi = isFermiDos(record)
  const mirroredTextValue = record.value_kind === 'text' && record.value_text === record.value_raw
  const currentValueField = { number: 'value_number', range: 'value_min', text: 'value_text', boolean: 'value_boolean' }[record.value_kind]
  const issue = (field: string) => issues.find(item => item.field === field || item.field.endsWith(`.${field}`)
    || (isTc && field === currentValueField && /(?:^|\.)(value_raw|unit_raw|canonical_unit)$/.test(item.field)))?.message
  const fieldPath = (field: string) => basePath ? `${basePath}.${field}` : field
  const update = (patch: Partial<PropertyRecordDraft>) => onChange(normalizeCurrentTcValue({ ...record, ...patch }))
  const updatePath = (path: string, value: unknown) => onChange(normalizeCurrentTcValue(setAtPath(record, path, value)))
  const tcProps = { record, readOnly, issue, fieldPath, update }
  const recordActions = !readOnly && onDelete
    ? <Button color="error" startIcon={<DeleteIcon />} onClick={onDelete} sx={{ whiteSpace: 'nowrap' }}>删除记录</Button>
    : undefined
  const quotedSources = useMemo(() => {
    const values = [...(record.evidence ? [record.evidence] : []), ...(record.evidences || [])]
    return [...new Map(values.filter((value): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value))
      .filter(value => typeof value.quote === 'string' && value.quote.trim())
      .map(value => [`${value.filename || value.source_name || ''}:${value.page || value.page_start || value.pdf_page || ''}:${value.quote}`, value])).values()]
  }, [record.evidence, record.evidences])

  const renderExtensions = (path: string, schema: JsonSchema) => {
    const items = getAtPath(record, path)
    const values = Array.isArray(items) ? items as Array<Record<string, any>> : []
    return (
      <Box key={path} data-issue-field={fieldPath(path)} sx={{ gridColumn: '1 / -1', minWidth: 0 }}>
        {values.map((item, index) => {
          if (record.record_type === 'predicted_tc' && path === 'payload.parameters.extensions' && index === muRangeIndex(record)) return null
          if (path === 'payload.parameters.extensions') {
            const parameters = record.payload.parameters as Record<string, any> | undefined
            const canonical = String(item.key || '').replace(/_reported$/, '')
            if (item.reported && ['lambda_ep', 'omega_log', 'mu_star'].includes(canonical) && parameters && canonical in parameters) return null
            const paired = values[muRangeIndex(record)]
            if (item.key === 'mu_star_reported_range' && paired && paired.value_min === item.value_min && paired.value_max === item.value_max) return null
          }
          const itemPath = `${path}.${index}`
          const kind = (item.value_kind || 'number') as PropertyValueKind
          return (
            <Box key={item.field_key || index} data-extension-row sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mt: 1, overflowX: 'auto', py: 1 }}>
              <AutoGrowingTextField data-issue-field={fieldPath(`${itemPath}.name_raw`)} label="字段名称" value={item.name_raw ?? item.name ?? item.key ?? ''} disabled={readOnly}
                error={Boolean(issue(`${itemPath}.name_raw`))} helperText={issue(`${itemPath}.name_raw`)}
                onChange={event => updatePath(`${itemPath}.name_raw`, event.target.value)} />
              <FormControl size="small" sx={{ minWidth: 110, flex: '0 0 auto' }}>
                <InputLabel>值类型</InputLabel>
                <Select label="值类型" value={kind} disabled={readOnly}
                  onChange={event => updatePath(itemPath, extensionValuePatch(item, event.target.value as PropertyValueKind, item.value_raw || ''))}>
                  {Object.entries(VALUE_KIND_LABELS).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
                </Select>
              </FormControl>
              {kind === 'boolean' ? (
                <FormControl size="small" sx={{ minWidth: 110, flex: '0 0 auto' }}>
                  <InputLabel>值</InputLabel>
                  <Select label="值" value={String(Boolean(item.value_boolean))} disabled={readOnly}
                    onChange={event => updatePath(itemPath, extensionValuePatch(item, kind, event.target.value))}>
                    <MenuItem value="true">是</MenuItem><MenuItem value="false">否</MenuItem>
                  </Select>
                </FormControl>
              ) : (
                <AutoGrowingTextField data-issue-field={fieldPath(`${itemPath}.value_raw`)} label={kind === 'range' ? '值（下界..上界）' : '值'} value={item.value_raw || ''} disabled={readOnly}
                  error={Boolean(issue(`${itemPath}.value_raw`))} helperText={issue(`${itemPath}.value_raw`)}
                  onChange={event => {
                    const next = extensionValuePatch(item, kind, event.target.value)
                    if (kind === 'range') {
                      const [min, max] = event.target.value.split('..').map(part => part.trim() ? Number(part) : NaN)
                      next.value_min = Number.isFinite(min) ? min : null
                      next.value_max = Number.isFinite(max) ? max : null
                    }
                    updatePath(itemPath, next)
                  }} />
              )}
              <AutoGrowingTextField data-issue-field={fieldPath(`${itemPath}.unit_raw`)} label="单位" value={item.unit_raw || ''} disabled={readOnly}
                onChange={event => updatePath(`${itemPath}.unit_raw`, event.target.value)} />
              {!readOnly && <Button color="error" aria-label="删除扩展字段" onClick={() => updatePath(path, values.filter((_, itemIndex) => itemIndex !== index))}><DeleteIcon /></Button>}
            </Box>
          )
        })}
        {!readOnly && <Button size="small" startIcon={<AddIcon />} onClick={() => updatePath(path, [...values, {
          field_key: newStableKey('field'), name_raw: '', value_kind: 'number', value_raw: '', value_number: null, unit_raw: '', evidences: [],
        }])}>新增字段</Button>}
      </Box>
    )
  }

  const renderSchema = (schema: JsonSchema, path: string, fallbackLabel: string): React.ReactNode => {
    const label = titleFor(definition, path, schema, fallbackLabel)
    if (path === 'payload.experimental_conditions' && record.record_type === 'measured_tc') {
      const descriptionPath = `${path}.description`
      const error = issue(descriptionPath) || issue(path)
      return (
        <TextField key={path} label={label} multiline minRows={3} fullWidth disabled={readOnly}
          sx={{ gridColumn: '1 / -1' }} value={experimentalConditionsText(getAtPath(record, path))}
          data-issue-field={fieldPath(descriptionPath)} error={Boolean(error)} helperText={error}
          onChange={event => updatePath(descriptionPath, event.target.value)} />
      )
    }
    if (schema.type === 'array' && path.endsWith('.extensions')) return renderExtensions(path, schema)
    if (schema.type === 'object' || schema.properties) {
      const fixed = Object.entries(schema.properties || {}).filter(([key, child]) => key !== 'extensions' && !(record.record_type === 'predicted_tc'
        && path === 'payload.parameters' && ['lambda_ep', 'omega_log', 'omega_log_k', 'mu_star'].includes(key)) && child.type !== 'object')
      return (
        <Box key={path} data-issue-field={fieldPath(path)} sx={{ gridColumn: '1 / -1', minWidth: 0 }}>
          {path === 'payload.calculation_conditions' && <Typography variant="body2" color="text.secondary">计算条件</Typography>}
          {fixed.length > 0 && <Box data-condition-row sx={{ display: 'flex', gap: 1, overflowX: 'auto', py: 1, '& > *': { flex: '0 0 auto', minWidth: 110 } }}>
            {fixed.map(([key, child]) => renderSchema(child, `${path}.${key}`, key))}
          </Box>}
          {Object.entries(schema.properties || {}).filter(([key, child]) => key === 'extensions' || child.type === 'object')
            .map(([key, child]) => renderSchema(child, `${path}.${key}`, key))}
          {issue(path) && <Typography color="error" variant="caption">{issue(path)}</Typography>}
        </Box>
      )
    }
    const value = getAtPath(record, path)
    if (schema.enum) {
      return (
        <FormControl key={path} size="small" error={Boolean(issue(path))} data-issue-field={fieldPath(path)}>
          <InputLabel>{label}</InputLabel>
          <Select label={label} value={value ?? ''} disabled={readOnly} onChange={event => updatePath(path, event.target.value)}>
            {schema.enum.map(option => <MenuItem key={String(option)} value={String(option)}>{String(option)}</MenuItem>)}
          </Select>
        </FormControl>
      )
    }
    if (schema.type === 'boolean') {
      return <FormControlLabel key={path} data-issue-field={fieldPath(path)} control={<Checkbox checked={Boolean(value)} disabled={readOnly} onChange={event => updatePath(path, event.target.checked)} />} label={label} />
    }
    const numeric = schema.type === 'number' || schema.type === 'integer'
    return (
      <AutoGrowingTextField key={path} label={label} type={numeric ? 'number' : 'text'} value={Array.isArray(value) ? value.join(' x ') : value ?? ''} disabled={readOnly}
        data-issue-field={fieldPath(path)} error={Boolean(issue(path))} helperText={issue(path) || schema.description}
        slotProps={numeric ? { htmlInput: { min: schema.minimum, max: schema.maximum, step: schema.type === 'integer' ? 1 : 'any' } } : undefined}
        onChange={event => updatePath(path, numeric ? (event.target.value === '' ? null : Number(event.target.value)) : parseGridOrText(event.target.value, schema))} />
    )
  }

  return (
    <Box data-issue-field={basePath} data-record-key={record.record_key} data-testid={`property-record-${record.record_key}`} sx={{ display: 'grid', gap: 1, minWidth: 0, containerType: isTc ? 'inline-size' : undefined, containerName: isTc ? 'tc-record' : undefined, gridTemplateColumns: 'minmax(0, 1fr)', py: 1, mb: 1 }}>
      {definitionError && <Alert severity="error" sx={{ gridColumn: '1 / -1' }}>{definitionError}</Alert>}
      {isThermodynamicStability(record) ? <ThermodynamicStabilityFields record={record} readOnly={readOnly} onChange={onChange} basePath={basePath} actions={recordActions} /> : isTc ? <TcRecordFields {...tcProps} actions={recordActions} /> : <PropertyRecordRow actions={recordActions}><Box data-property-core-row sx={{ display: 'flex', gap: 1, overflowX: 'auto', py: 1, '& > *': { flex: '0 0 auto', minWidth: 110 }, '& .MuiInputBase-root': { fontSize: '0.875rem' } }}>
      <AutoGrowingTextField label="名称" value={record.name_raw} disabled={readOnly} data-issue-field={fieldPath('name_raw')} error={Boolean(issue('name_raw'))} helperText={issue('name_raw')} onChange={event => update({ name_raw: event.target.value })} />
      <FormControl size="small">
        <InputLabel>值类型</InputLabel>
        <Select label="值类型" value={record.value_kind} disabled={readOnly} onChange={event => update({ value_kind: event.target.value as PropertyValueKind })}>
          {Object.entries(VALUE_KIND_LABELS).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
        </Select>
      </FormControl>
      <AutoGrowingTextField label="原始值" value={record.value_raw} disabled={readOnly} data-dos-current-value={isDosFermi ? true : undefined} data-issue-field={fieldPath('value_raw')} error={Boolean(issue('value_raw'))} helperText={issue('value_raw')}
        onChange={event => update(mirroredTextValue ? { value_raw: event.target.value, value_text: event.target.value } : { value_raw: event.target.value })} />
      <AutoGrowingTextField label="单位" value={record.unit_raw || ''} disabled={readOnly} data-issue-field={isDosFermi ? fieldPath('unit_raw') : undefined} onChange={event => update({ unit_raw: event.target.value || null })} />
      {record.value_kind === 'number' && <AutoGrowingTextField label="数值" type="number" value={record.value_number ?? ''} disabled={readOnly} onChange={event => update({ value_number: event.target.value === '' ? null : Number(event.target.value) })} />}
      {record.value_kind === 'range' && <><AutoGrowingTextField label="下界" type="number" value={record.value_min ?? ''} disabled={readOnly} data-issue-field={fieldPath('value_min')} error={Boolean(issue('value_min'))} helperText={issue('value_min')} onChange={event => update({ value_min: event.target.value === '' ? null : Number(event.target.value) })} /><AutoGrowingTextField label="上界" type="number" value={record.value_max ?? ''} disabled={readOnly} onChange={event => update({ value_max: event.target.value === '' ? null : Number(event.target.value) })} /></>}
      {record.value_kind === 'text' && !mirroredTextValue && <AutoGrowingTextField label="文本值" value={record.value_text || ''} disabled={readOnly} onChange={event => update({ value_text: event.target.value })} />}
      {record.value_kind === 'boolean' && <FormControlLabel control={<Checkbox checked={Boolean(record.value_boolean)} disabled={readOnly} onChange={event => update({ value_boolean: event.target.checked })} />} label="布尔值" />}
      </Box></PropertyRecordRow>}
      {hasDosConflict(record) && <Button size="small" color="warning" sx={{ justifySelf: 'start' }} aria-haspopup="dialog" onClick={event => {
        event.currentTarget.dispatchEvent(new CustomEvent('scwiki:open-record-evidence', { bubbles: true, detail: { record, field: basePath } }))
      }}>数值有矛盾 · 查看来源对照</Button>}
      {Object.entries(payloadSchema.properties || {}).sort(([a], [b]) => a === 'parameters' ? -1 : b === 'parameters' ? 1 : 0).filter(([key]) => !['thermodynamic_stability', 'source_associations', 'table_row_ref', DOS_SOURCE_KEY].includes(key)).map(([key, schema]) => renderSchema(schema, `payload.${key}`, key))}
      {!isDosFermi && <Box sx={{ gridColumn: '1 / -1', minWidth: 0 }}>
        {quotedSources.length ? <Box component="details" data-evidence-summary sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
          <Box component="summary" sx={{ cursor: 'pointer' }}>原文证据（{quotedSources.length}）</Box>
          {quotedSources.map((source, index) => <Typography key={index} variant="caption" display="block" sx={{ mt: 0.5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {[source.filename || source.source_name || '当前论文附件', source.page || source.page_start || source.pdf_page ? `第 ${source.page || source.page_start || source.pdf_page} 页` : ''].filter(Boolean).join(' · ')}：{String(source.quote)}
          </Typography>)}
        </Box> : record.value_raw && <Typography variant="caption" color="text.secondary">
          {record.basis_kind === 'paper_inference' ? '论文推断；无逐字原文引句' : record.basis_kind === 'general_knowledge' ? '通用知识建议；无论文原文引句' : '暂无可定位原文证据；可查看来源核对'}
        </Typography>}
      </Box>}
    </Box>
  )
}

export default SchemaDrivenRecordForm
