import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Box, Button, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import type { EvidenceRecord } from './EvidenceWorkflow'
import type { PropertyRecordDraft } from '../lib/propertyModules'

interface Props {
  records: EvidenceRecord[]
  scope: string
  onOpen: (key: string, keys?: string[], fallback?: EvidenceRecord, tab?: 'source' | 'settings') => void
  onChange: (field: string, pathKind?: 'current' | 'snapshot') => void
}
const normalize = (field: string) => field.replace(/^user_values\./, '')
const valueText = (value: unknown) => typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')
/** 只读宿主保留来源、字段设置查看及模块展开入口。 */
export const readOnlyEvidenceFormSx = {
  pointerEvents: 'none', '& .MuiButton-root': { display: 'none' },
  '& [data-scientific-settings], & [data-evidence-key], & [data-property-module-toggle]': { pointerEvents: 'auto' },
  '& .MuiButton-root[data-scientific-settings], & .MuiButton-root[data-evidence-key]': { display: 'inline-flex' },
} as const
function matchesField(node: HTMLElement, record: EvidenceRecord, suffix: string) {
  suffix = suffix.replace('.omega_log_k', '.omega_log')
  if (record.record_field_key && record.record_field?.startsWith('payload.calculation_conditions.extensions.')) return node.dataset.scientificFieldKey === record.record_field_key && (!record.record_field?.split('.extensions.')[1]?.includes('.') || Boolean(node.dataset.issueField?.endsWith('.' + record.record_field.split('.').at(-1))))
  if (record.record_field?.startsWith('payload.parameters.extensions.')) return Boolean(node.dataset.issueField?.includes('.payload.parameters.extensions.') && node.dataset.issueField.endsWith('.' + record.record_field.split('.').at(-1)))
  return suffix !== '' && Boolean(node.dataset.issueField?.endsWith(suffix) || (suffix.includes('.payload.parameters.') && suffix.endsWith('.value_number') && node.dataset.issueField?.endsWith(suffix.slice(0, -13))))
}

function recordOwner(record: EvidenceRecord, state?: HTMLElement) {
  if (!record.state_key) return '论文'
  const index = state?.dataset.materialStateIndex ?? record.field.match(/^material_states\[(\d+)\]/)?.[1]
  const name = state?.dataset.stateLabel
  return [name, index == null ? `材料状态 ${record.state_key}` : `材料状态 ${Number(index) + 1}${state ? '' : '（已移除）'}`].filter(Boolean).join(' · ')
}

export const evidenceProblem = (record: EvidenceRecord) => !record.pending_review && !record.stale && (record.required !== false || record.human_modified || record.field_decision?.action === 'reject') && ['unsupported', 'uncertain', 'missing'].includes(record.status)

/** 优先复用控件自己的标签，不把整个输入框变成按钮。 */
function fieldCaption(node: HTMLElement) {
  if (node.hasAttribute('data-evidence-readonly')) return node
  if (node.matches('.MuiInputBase-root')) {
    return node.closest('.MuiFormControl-root')?.querySelector<HTMLElement>('.MuiInputLabel-root') || null
  }
  return Array.from(node.querySelectorAll<HTMLElement>('label,.MuiTypography-root,h2,h3,h4,h5,h6'))
    .find(caption => !caption.closest('button,a,[role="button"]') &&
      (!caption.closest('[data-issue-field]') || caption.closest('[data-issue-field]') === node)) || null
}

function currentPlaceholder(record: EvidenceRecord, node: HTMLElement): EvidenceRecord {
  if (!record.placeholder) return record
  const input = node.querySelector<HTMLInputElement | HTMLTextAreaElement>('input,textarea')
  return { ...record, current_value: input?.value ?? node.querySelector('[role="combobox"]')?.textContent ?? node.parentElement?.textContent ?? record.current_value }
}

const FieldTrigger = memo(function FieldTrigger({ records, node, onOpen }: { records: EvidenceRecord[]; node: HTMLElement; onOpen: Props['onOpen'] }) {
  const [host] = useState(() => document.createElement('span'))
  const [caption, setCaption] = useState<HTMLElement | null>(null)
  const names = [...new Set(records.map(r => r.label))].join('、')
  const label = `${names}：查看来源核对（${records.length}）`
  const hasProblem = records.some(evidenceProblem)
  useEffect(() => {
    if (node.hasAttribute('data-scientific-field')) {
      host.style.cssText = 'position:absolute;right:4px;top:4px;line-height:1'
    }
    const target = fieldCaption(node)
    setCaption(target)
    if (!target) {
      node.prepend(host)
      return () => host.remove()
    }
    // 重新绑定或卸载后恢复原标签语义及默认聚焦行为。
    const attributes = {
      role: 'button', tabindex: '0', 'aria-description': label,
      title: label, 'aria-haspopup': 'dialog', 'data-evidence-key': records[0].key, 'data-evidence-caption': 'true',
      'data-evidence-caption-problem': String(hasProblem),
    }
    const previous = Object.keys(attributes).map(name => [name, target.getAttribute(name)] as const)
    for (const [name, value] of Object.entries(attributes)) target.setAttribute(name, value)
    const activate = (event: Event) => {
      event.preventDefault()
      event.stopPropagation()
      target.focus()
      if (records[0].placeholder) onOpen(records[0].key, [records[0].key], currentPlaceholder(records[0], node))
      else onOpen(records[0].key, records.map(r => r.key))
    }
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') activate(event)
    }
    target.addEventListener('click', activate)
    target.addEventListener('keydown', keydown)
    return () => {
      target.removeEventListener('click', activate)
      target.removeEventListener('keydown', keydown)
      for (const [name, value] of previous) {
        if (value === null) target.removeAttribute(name)
        else target.setAttribute(name, value)
      }
    }
  }, [host, node, records, onOpen, label, names, hasProblem])
  return caption ? null : createPortal(<Button data-evidence-key={records[0].key} color={records.some(evidenceProblem) ? 'error' : 'primary'} size="small" sx={node.hasAttribute('data-scientific-field') ? { minWidth: 20, p: 0 } : undefined} aria-label={label} title={label} aria-haspopup="dialog" onClick={event => { event.stopPropagation(); if (records[0].placeholder) onOpen(records[0].key, [records[0].key], currentPlaceholder(records[0], node)); else onOpen(records[0].key, records.map(r => r.key)) }}>{node.hasAttribute('data-scientific-field') ? '•' : names}</Button>, host)
})

/** 在现有表单的字段锚点附加标记，避免复制动态表单和科学校验。 */
export default function EvidenceFieldMarkers({ records, scope, onOpen: openCallback, onChange: changeCallback }: Props) {
  const theme = useTheme()
  const callbacks = useRef({ openCallback, changeCallback })
  callbacks.current = { openCallback, changeCallback }
  const onOpen = useCallback<Props['onOpen']>((...args) => callbacks.current.openCallback(...args), [])
  const onChange = useCallback<Props['onChange']>((...args) => callbacks.current.changeCallback(...args), [])
  const currentRecords = useRef(records)
  currentRecords.current = records
  // 核对颜色/理由改变不改变节点拓扑；只在身份或实际 DOM 结构变化时重新定位。
  const topology = JSON.stringify(records.map(r => [r.key, r.field, r.fields, r.state_key, r.module_key, r.record_key,
    r.record_field, r.record_field_key, r.structure_hash, r.structure_field]))
  const [bindings, setTargets] = useState<Array<{ record: EvidenceRecord; node: HTMLElement }>>([])
  const targets = useMemo(() => {
    const latest = new Map(records.map(record => [record.key, record]))
    return bindings.flatMap(binding => {
      const record = latest.get(binding.record.key) || (binding.record.placeholder ? binding.record : undefined)
      return record ? [{ node: binding.node, record }] : []
    })
  }, [bindings, records])
  const [owners, setOwners] = useState<Record<string, string>>({})
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(`[data-evidence-scope="${scope}"]`)
    if (!root) return
    const openSettings = (event: Event) => {
      const request = (event as CustomEvent<{ field: string; name: string; value: string; handled: boolean }>).detail
      if (request.handled) return
      const node = (event.target as HTMLElement).closest<HTMLElement>('[data-scientific-field]')
      if (!node) return
      request.handled = true
      const found = targets.find(target => target.node === node)?.record
      if (found) onOpen(found.key, [found.key], found.placeholder ? currentPlaceholder(found, node) : undefined, 'settings')
      else {
        // 新增或尚未载入核对结果的字段仍使用同一侧栏，不伪造来源资格。
        const field = request.field.replace(/\.(\d+)(?=\.|$)/g, '[$1]')
        const key = `view:${scope}:${field}`
        onOpen(key, [key], { key, field, label: request.name, current_value: request.value, state_key: node.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey,
          module_key: node.closest<HTMLElement>('[data-module-key]')?.dataset.moduleKey, record_key: node.closest<HTMLElement>('[data-record-key]')?.dataset.recordKey,
          record_field_key: node.closest<HTMLElement>('[data-scientific-field-key]')?.dataset.scientificFieldKey,
          status: 'unchecked', reason: '', evidences: [], required: false, placeholder: true }, 'settings')
      }
    }
    root.addEventListener('scwiki:open-field-settings', openSettings)
    return () => root.removeEventListener('scwiki:open-field-settings', openSettings)
  }, [scope, targets, onOpen])
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(`[data-evidence-scope="${scope}"]`)
    if (!root) return
    const openRecord = (event: Event) => {
      const { record, field } = (event as CustomEvent<{ record: PropertyRecordDraft; field: string }>).detail
      const node = (event.target as HTMLElement).closest<HTMLElement>('[data-record-key]')
      const stateKey = node?.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey
      const moduleKey = node?.closest<HTMLElement>('[data-module-key]')?.dataset.moduleKey
      const found = records.find(item => item.record_key === record.record_key && item.state_key === stateKey && item.module_key === moduleKey)
      if (found) onOpen(found.key, [found.key])
      else {
        const key = 'view:dos:' + stateKey + ':' + moduleKey + ':' + record.record_key
        onOpen(key, [key], { key, field, label: record.name_raw || '费米能级 DOS', placeholder: true, required: false,
          module_code: record.module_code, state_key: stateKey, module_key: moduleKey, record_key: record.record_key,
          current_value: { record }, status: 'uncertain', reason: 'DOS 来源数值存在差异，待人工核对', evidences: [] })
      }
    }
    root.addEventListener('scwiki:open-record-evidence', openRecord)
    return () => root.removeEventListener('scwiki:open-record-evidence', openRecord)
  }, [records, scope, onOpen])
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(`[data-evidence-scope="${scope}"]`)
    if (!root) return
    let active = true
    let frame: ReturnType<typeof setTimeout> | undefined
    const find = () => {
      const records = currentRecords.current
      const stateNodes = new Map(Array.from(root.querySelectorAll<HTMLElement>('[data-state-key]')).map(node => [node.dataset.stateKey, node]))
      const nextOwners = Object.fromEntries(records.map(record => [record.key, recordOwner(record, stateNodes.get(record.state_key))]))
      setOwners(old => JSON.stringify(old) === JSON.stringify(nextOwners) ? old : nextOwners)
      const nodes = Array.from(root.querySelectorAll<HTMLElement>('[data-issue-field]')).filter(node => !node.closest('[data-evidence-fallback]'))
      const next = records.flatMap(record => {
        let area: HTMLElement = root
        if (record.state_key) {
          const state = stateNodes.get(record.state_key)
          if (!state) return []
          area = state
        }
        if (record.module_key) {
          const module = Array.from(area.querySelectorAll<HTMLElement>('[data-module-key]')).find(n => n.dataset.moduleKey === record.module_key)
          if (!module) return []
          area = module
        }
        const row = record.record_key ? Array.from(area.querySelectorAll<HTMLElement>('[data-record-key]')).find(n => n.dataset.recordKey === record.record_key) : undefined
        if (record.record_key && !row) return []
        const scopedNodes = nodes.filter(node => area.contains(node))
        const fields = !record.record_field && row?.querySelector('[data-dos-current-value]')
          ? ['name_raw', 'value_raw', 'unit_raw'].map(name => record.field + '.' + name)
          : [...new Set(record.fields || [record.field])]
        return fields.filter(field => !fields.some(other => other !== field && other.startsWith(field + '.'))).flatMap(field => {
          const recordPath = record.record_field ? record.field.slice(0, record.field.length - record.record_field.length - 1) : record.field
          const suffix = field.startsWith(recordPath) ? field.slice(recordPath.length) : ''
          const rowNodes = row ? Array.from(row.querySelectorAll<HTMLElement>('[data-issue-field]')) : scopedNodes
          const structures = Array.from(area.querySelectorAll<HTMLElement>('[data-scientific-structure]'))
          const structure = record.structure_hash ? structures.find(n => n.dataset.structureHash === record.structure_hash) : undefined
          // 未选中的结构问题留在清单，不能猜测属于当前预览。
          if (record.structure_hash && !structure) return []
          const stateField = record.state_key && !row ? Array.from(area.querySelectorAll<HTMLElement>('[data-issue-field]')).find(n => n.dataset.issueField?.replace(/^material_states\[\d+\]/, '') === field.replace(/^material_states\[\d+\]/, '')) : undefined
          // 已移除的 Tc raw 控件仍可出现在旧核对快照中，定位到当前值而非整个记录。
          const tcValue = ['.value_raw', '.unit_raw', '.canonical_unit'].includes(suffix)
            ? row?.querySelector<HTMLElement>('[data-tc-current-value]') : undefined
          const dosValue = suffix === '' ? row?.querySelector<HTMLElement>('[data-dos-current-value]') : undefined
          const structureField = record.structure_field ? structure?.querySelector<HTMLElement>(`[data-structure-field="${record.structure_field}"]`) : structure
          const exact = structureField || (row ? rowNodes.find(n => matchesField(n, record, suffix)) || (!record.record_field ? tcValue || dosValue || row : undefined) : stateField || (!record.state_key ? scopedNodes.find(n => normalize(n.dataset.issueField || '') === normalize(field)) : undefined))
          const node = exact || (!record.state_key ? scopedNodes.filter(n => normalize(field).startsWith(normalize(n.dataset.issueField || '') + '.')).sort((a, b) => (b.dataset.issueField?.length || 0) - (a.dataset.issueField?.length || 0))[0] : undefined)
          // 组合控件与内部输入必须归一为同一个锚点，否则两次标注同一标签，
          // 下次更新会把已标注标签误判为外部按钮并额外插入一行标题。
          const control = node?.hasAttribute('data-scientific-field') ? node : node?.querySelector<HTMLElement>('[data-scientific-field]') || (node?.matches('input,textarea,select') ? node.closest<HTMLElement>('.MuiInputBase-root') || node.parentElement : node?.matches('.MuiFormControl-root,.MuiAutocomplete-root') ? node.querySelector<HTMLElement>('.MuiInputBase-root') || node : node)
          return control ? [{ record, node: control }] : []
        })
      })
      // 每个实际控件都保留查看入口；无后端记录时只读展示当前值，不创造核对资格。
      for (const node of root.querySelectorAll<HTMLElement>('.MuiInputBase-root')) {
        if (node.closest('[data-evidence-ignore],.evidence-review-drawer') || next.some(x => x.node === node)) continue
        const caption = fieldCaption(node)
        if (!caption) continue
        const input = node.querySelector<HTMLInputElement | HTMLTextAreaElement>('input,textarea')
        const anchor = node.closest<HTMLElement>('[data-issue-field]')
        const owner = node.closest<HTMLElement>('[data-record-key],[data-scientific-structure]')
        const associated = next.filter(x => x.node.contains(node) && (!owner || owner.contains(x.node) || x.node === owner))
        if (associated.length) {
          for (const x of associated) next.push({record:x.record,node})
          continue
        }
        const field = anchor?.dataset.issueField || `view:${caption.id || input?.id || caption.textContent}`
        const record: EvidenceRecord = {key:`view:${scope}:${field}:${caption.id}`, field, label:caption.textContent || '',
          current_value:input?.value ?? node.querySelector('[role="combobox"]')?.textContent ?? '', status:'unchecked',
          state_key: node.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey,
          module_key: node.closest<HTMLElement>('[data-module-key]')?.dataset.moduleKey, record_key: node.closest<HTMLElement>('[data-record-key]')?.dataset.recordKey,
          record_field_key: node.closest<HTMLElement>('[data-scientific-field-key]')?.dataset.scientificFieldKey,
          reason:'', evidences:[], required:false, placeholder:true}
        next.push({record,node})
      }
      for (const node of root.querySelectorAll<HTMLElement>('[data-evidence-readonly]')) {
        if (next.some(x => x.node === node) || node.closest('[data-evidence-ignore]')) continue
        const owner = node.closest<HTMLElement>('[data-scientific-structure]')
        const associated = owner && next.filter(x => x.node === owner)
        if (associated && associated.length) {
          for (const x of associated) next.push({record:x.record,node})
        } else {
          const record: EvidenceRecord = {key:`view:${scope}:readonly:${node.textContent}`, field:'view:readonly',
            label:node.textContent || '', current_value:node.parentElement?.textContent || '', status:'unchecked',
            structure_field: node.dataset.structureField, structure_hash: owner?.dataset.structureHash,
            state_key: node.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey,
            reason:'', evidences:[], required:false, placeholder:true}
          next.push({record,node})
        }
      }
      setTargets(old => old.length === next.length && old.every((x, i) => x.node === next[i].node && (x.record === next[i].record || (x.record.placeholder && JSON.stringify(x.record) === JSON.stringify(next[i].record)))) ? old : next)
    }
    find()
    const anchors = '[data-issue-field],[data-state-key],[data-module-key],[data-record-key],[data-scientific-structure],[data-evidence-readonly],.MuiInputBase-root,label,[data-scientific-settings]'
    const observer = new MutationObserver(changes => {
      const renamed = new Map(changes.filter(change => change.type === 'attributes' && change.attributeName === 'data-state-label')
        .map(change => { const node = change.target as HTMLElement; return [node.dataset.stateKey, node] }))
      if (renamed.size) setOwners(old => {
        const next = { ...old }
        for (const record of currentRecords.current) if (renamed.has(record.state_key)) next[record.key] = recordOwner(record, renamed.get(record.state_key))
        return next
      })
      // 文本/标记自身的变动不代表新字段；新增、删除和身份改变才需要重建定位。
      if (!changes.some(change => (change.type === 'attributes' && change.attributeName !== 'data-state-label') || [...change.addedNodes, ...change.removedNodes]
        .some(node => node instanceof Element && (node.matches(anchors) || node.querySelector(anchors))))) return
      clearTimeout(frame); frame = setTimeout(find, 0)
    })
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-issue-field', 'data-state-key', 'data-state-label', 'data-module-key', 'data-record-key', 'data-structure-hash'] })
    const changed = (event: Event) => {
      // 文本在 input 时已通知；失焦后的 change 不能再次使刚保存的版本失效。
      if (event.type === 'change' && (event.target as HTMLElement).matches('textarea,input:not([type="checkbox"]):not([type="radio"])')) return
      const node = (event.target as HTMLElement).closest<HTMLElement>('[data-issue-field]')
      if (!node?.dataset.issueField) return
      const field = normalize(node.dataset.issueField)
      const stateKey = node.closest<HTMLElement>('[data-state-key]')?.dataset.stateKey
      const moduleKey = node.closest<HTMLElement>('[data-module-key]')?.dataset.moduleKey
      const recordKey = node.closest<HTMLElement>('[data-record-key]')?.dataset.recordKey
      const record = currentRecords.current.find(r => r.state_key === stateKey && r.module_key === moduleKey && r.record_key === recordKey)
      const currentBase = field.match(/^material_states\[\d+\]\.property_modules\[\d+\]\.records\[\d+\]/)?.[0]
      const snapshotBase = record?.record_field ? record.field.slice(0, -record.record_field.length - 1) : record?.field
      const changedField = stateKey && record
        ? currentBase && snapshotBase ? snapshotBase + field.slice(currentBase.length)
          : field.replace(/^material_states\[\d+\]/, record.field.match(/^material_states\[\d+\]/)?.[0] || '')
        : field
      // 浏览器会在原生监听器之间执行微任务；必须等整次事件传播结束，
      // 否则 React 的 onChange 尚未读取新值就被核对标记的更新恢复为旧值。
      setTimeout(() => { if (active) onChange(changedField, 'snapshot') }, 0)
    }
    root.addEventListener('input', changed)
    root.addEventListener('change', changed)
    return () => { active = false; observer.disconnect(); clearTimeout(frame); root.removeEventListener('input', changed); root.removeEventListener('change', changed) }
  }, [topology, scope, onChange])
  const annotated = useRef(new Map<HTMLElement, boolean>())
  useEffect(() => {
    const next = new Map<HTMLElement, boolean>()
    for (const { node, record } of targets) next.set(node, Boolean(next.get(node) || evidenceProblem(record)))
    for (const node of annotated.current.keys()) if (!next.has(node)) { delete node.dataset.evidenceProblem; delete node.dataset.evidenceAnnotated }
    for (const [node, problem] of next) {
      if (!annotated.current.has(node)) node.dataset.evidenceAnnotated = 'true'
      if (annotated.current.get(node) !== problem) {
        if (problem) node.dataset.evidenceProblem = 'true'
        else delete node.dataset.evidenceProblem
      }
    }
    annotated.current = next
  }, [targets])
  useEffect(() => () => {
    for (const node of annotated.current.keys()) { delete node.dataset.evidenceProblem; delete node.dataset.evidenceAnnotated }
  }, [])
  const missing = records.filter(r => !targets.some(x => x.record.key === r.key) && evidenceProblem(r))
  const previousGroups = useRef(new Map<HTMLElement, EvidenceRecord[]>())
  const groups = useMemo(() => {
    const next = new Map<HTMLElement, EvidenceRecord[]>()
    for (const { node, record } of targets) {
      const group = next.get(node) || []
      if (!group.some(r => r.key === record.key)) group.push(record)
      next.set(node, group)
    }
    for (const [node, group] of next) {
      const old = previousGroups.current.get(node)
      if (old?.length === group.length && old.every((record, index) => record === group[index])) next.set(node, old)
    }
    previousGroups.current = next
    return next
  }, [targets])
  return <>
    {/* outlined 控件复用原有标签缺口；额外 outline 会穿过浮动文字。 */}
    <style>{`
      [data-evidence-annotated="true"] {position: relative;}
      [data-evidence-problem="true"] {outline: 2px solid #d32f2f; outline-offset: 2px; position: relative; border-radius: 8px;}
      [data-scientific-field][data-evidence-problem="true"] {outline: none; border-color: #d32f2f;}
      [data-evidence-problem="true"].MuiOutlinedInput-root {outline: none;}
      [data-evidence-problem="true"].MuiOutlinedInput-root > .MuiOutlinedInput-notchedOutline {border-color: #d32f2f; border-width: 2px;}
      [data-evidence-caption="true"] {color: ${theme.palette.primary.main} !important; cursor: pointer; pointer-events: auto !important;}
      [data-evidence-caption-problem="true"] {color: #d32f2f !important;}
      [data-evidence-caption="true"]:hover {text-decoration: underline;}
      [data-evidence-caption="true"]:focus-visible {outline: 2px solid ${theme.palette.primary.main}; outline-offset: 2px; border-radius: 2px;}
      [data-evidence-caption-problem="true"]:focus-visible {outline-color: #d32f2f;}
    `}</style>
    {[...groups].map(([node, group], i) => <FieldTrigger key={`${group[0].key}-${i}`} records={group} node={node} onOpen={onOpen} />)}
    {missing.length > 0 && <Box component="details" data-evidence-fallback sx={{ my: 1, borderLeft: 2, borderColor: 'warning.main', pl: 1.5 }}>
      <Typography component="summary" variant="caption" color="text.secondary">待定位的来源核对（{missing.length}）</Typography>
      {missing.map(record => <Box key={record.key}>
        <Button size="small" color="error" data-evidence-key={record.key} aria-haspopup="dialog" onClick={() => onOpen(record.key)} sx={{ textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere' }}>
          {owners[record.key] || '论文'} · {record.provenance?.filename ? `${record.provenance.filename} · ` : record.structure_hash ? `结构 #${Number(record.field.match(/(?:structures|structure_candidates)\[(\d+)\]/)?.[1] || 0) + 1} · ` : ''}{record.label}：查看来源核对
        </Button>
      </Box>)}
    </Box>}
  </>
}

export function EvidenceRecordList({ records, onOpen }: { records: EvidenceRecord[]; onOpen: (key: string, keys?: string[]) => void }) {
  return <Box sx={{ display: 'grid', gap: 1 }}>{records.map(r => <Box key={r.key} sx={{ position: 'relative', border: '2px solid', borderColor: !evidenceProblem(r) ? 'divider' : 'error.main', borderRadius: 2, p: 1.5 }}>
    <Button data-evidence-key={r.key} color={evidenceProblem(r) ? 'error' : 'primary'} aria-haspopup="dialog" title={`${r.label}：查看来源核对`} onClick={() => onOpen(r.key)} sx={{ fontWeight: 600, justifyContent: 'flex-start', textAlign: 'left', textTransform: 'none' }}>{r.label}</Button>
    <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{valueText(r.current_value)}</Typography>
  </Box>)}</Box>
}
