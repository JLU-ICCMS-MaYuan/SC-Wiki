import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Box, Button, Typography } from '@mui/material'
import type { EvidenceRecord } from './EvidenceWorkflow'

interface Props {
  records: EvidenceRecord[]
  scope: string
  onOpen: (key: string, keys?: string[]) => void
  onChange: (field: string, pathKind?: 'current' | 'snapshot') => void
}
const normalize = (field: string) => field.replace(/^user_values\./, '')
const valueText = (value: unknown) => typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')

function recordOwner(record: EvidenceRecord, scope: string) {
  if (!record.state_key) return '论文'
  const state = Array.from(document.querySelectorAll<HTMLElement>(`[data-evidence-scope="${scope}"] [data-state-key]`)).find(node => node.dataset.stateKey === record.state_key)
  const index = state?.dataset.materialStateIndex ?? record.field.match(/^material_states\[(\d+)\]/)?.[1]
  const name = state?.dataset.stateLabel
  return [name, index == null ? `材料状态 ${record.state_key}` : `材料状态 ${Number(index) + 1}${state ? '' : '（已移除）'}`].filter(Boolean).join(' · ')
}

export const evidenceProblem = (record: EvidenceRecord) => Boolean(record.stale || (record.status !== 'supported' && !record.proposal_draft?.accepted && !record.human_confirmed && !record.resolution?.trim()))

/** 优先复用控件自己的标签，不把整个输入框变成按钮。 */
function fieldCaption(node: HTMLElement) {
  if (node.matches('.MuiInputBase-root')) {
    return node.closest('.MuiFormControl-root')?.querySelector<HTMLElement>('.MuiInputLabel-root') || null
  }
  return Array.from(node.querySelectorAll<HTMLElement>('label,.MuiTypography-root,h2,h3,h4,h5,h6'))
    .find(caption => !caption.closest('button,a,[role="button"]') &&
      (!caption.closest('[data-issue-field]') || caption.closest('[data-issue-field]') === node)) || null
}

function FieldTrigger({ records, node, onOpen }: { records: EvidenceRecord[]; node: HTMLElement; onOpen: Props['onOpen'] }) {
  const [host] = useState(() => document.createElement('span'))
  const [caption, setCaption] = useState<HTMLElement | null>(null)
  const names = [...new Set(records.map(r => r.label))].join('、')
  const label = `${names}：查看来源核对（${records.length}）`
  useEffect(() => {
    const target = fieldCaption(node)
    setCaption(target)
    if (!target) {
      node.prepend(host)
      return () => host.remove()
    }
    // 问题解决或卸载后恢复原标签语义及默认聚焦行为。
    const attributes = {
      role: 'button', tabindex: '0', 'aria-description': label,
      title: label, 'aria-haspopup': 'dialog', 'data-evidence-key': records[0].key, 'data-evidence-caption': 'true',
    }
    const previous = Object.keys(attributes).map(name => [name, target.getAttribute(name)] as const)
    for (const [name, value] of Object.entries(attributes)) target.setAttribute(name, value)
    const activate = (event: Event) => {
      event.preventDefault()
      event.stopPropagation()
      target.focus()
      onOpen(records[0].key, records.map(r => r.key))
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
  }, [host, node, records, onOpen, label, names])
  return caption ? null : createPortal(<Button data-evidence-key={records[0].key} color="error" size="small" aria-label={label} title={label} aria-haspopup="dialog" onClick={event => { event.stopPropagation(); onOpen(records[0].key, records.map(r => r.key)) }}>{names}</Button>, host)
}

/** 在现有表单的字段锚点附加标记，避免复制动态表单和科学校验。 */
export default function EvidenceFieldMarkers({ records, scope, onOpen, onChange }: Props) {
  const [targets, setTargets] = useState<Array<{ record: EvidenceRecord; node: HTMLElement }>>([])
  const [owners, setOwners] = useState<Record<string, string>>({})
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(`[data-evidence-scope="${scope}"]`)
    if (!root) return
    let active = true
    let frame: ReturnType<typeof setTimeout> | undefined
    const find = () => {
      const nextOwners = Object.fromEntries(records.map(record => [record.key, recordOwner(record, scope)]))
      setOwners(old => JSON.stringify(old) === JSON.stringify(nextOwners) ? old : nextOwners)
      const nodes = Array.from(root.querySelectorAll<HTMLElement>('[data-issue-field]')).filter(node => !node.closest('[data-evidence-fallback]'))
      const next = records.filter(evidenceProblem).flatMap(record => {
        let area: HTMLElement = root
        if (record.state_key) {
          const state = Array.from(root.querySelectorAll<HTMLElement>('[data-state-key]')).find(n => n.dataset.stateKey === record.state_key)
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
        const fields = [...new Set(record.fields || [record.field])]
        return fields.filter(field => !fields.some(other => other !== field && other.startsWith(field + '.'))).flatMap(field => {
          const suffix = field.startsWith(record.field) ? field.slice(record.field.length) : ''
          const rowNodes = row ? Array.from(row.querySelectorAll<HTMLElement>('[data-issue-field]')) : scopedNodes
          const structures = Array.from(area.querySelectorAll<HTMLElement>('[data-scientific-structure]'))
          const structure = record.structure_hash ? structures.find(n => n.dataset.structureHash === record.structure_hash) : undefined
          // 未选中的结构问题留在清单，不能猜测属于当前预览。
          if (record.structure_hash && !structure) return []
          const stateField = record.state_key && !row ? Array.from(area.querySelectorAll<HTMLElement>('[data-issue-field]')).find(n => n.dataset.issueField?.replace(/^material_states\[\d+\]/, '') === field.replace(/^material_states\[\d+\]/, '')) : undefined
          // 已移除的 Tc raw 控件仍可出现在旧核对快照中，定位到当前值而非整个记录。
          const tcValue = ['.value_raw', '.unit_raw', '.canonical_unit'].includes(suffix)
            ? row?.querySelector<HTMLElement>('[data-tc-current-value]') : undefined
          const exact = structure || (row ? rowNodes.find(n => n.dataset.issueField?.endsWith(suffix) && suffix !== '') || tcValue || row : stateField || (!record.state_key ? scopedNodes.find(n => normalize(n.dataset.issueField || '') === normalize(field)) : undefined))
          const node = exact || (!record.state_key ? scopedNodes.filter(n => normalize(field).startsWith(normalize(n.dataset.issueField || '') + '.')).sort((a, b) => (b.dataset.issueField?.length || 0) - (a.dataset.issueField?.length || 0))[0] : undefined)
          const control = node?.matches('input,textarea,select') ? node.closest<HTMLElement>('.MuiInputBase-root') || node.parentElement : node?.matches('.MuiFormControl-root') ? node.querySelector<HTMLElement>('.MuiInputBase-root') || node : node
          return control ? [{ record, node: control }] : []
        })
      })
      setTargets(old => old.length === next.length && old.every((x, i) => x.node === next[i].node && x.record === next[i].record) ? old : next)
    }
    find()
    const observer = new MutationObserver(() => { clearTimeout(frame); frame = setTimeout(find, 0) })
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
      const record = records.find(r => r.state_key === stateKey && r.module_key === moduleKey && r.record_key === recordKey)
      const changedField = stateKey && record
        ? recordKey ? record.field : field.replace(/^material_states\[\d+\]/, record.field.match(/^material_states\[\d+\]/)?.[0] || '')
        : field
      // 浏览器会在原生监听器之间执行微任务；必须等整次事件传播结束，
      // 否则 React 的 onChange 尚未读取新值就被核对标记的更新恢复为旧值。
      setTimeout(() => { if (active) onChange(changedField, 'snapshot') }, 0)
    }
    root.addEventListener('input', changed)
    root.addEventListener('change', changed)
    return () => { active = false; observer.disconnect(); clearTimeout(frame); root.removeEventListener('input', changed); root.removeEventListener('change', changed) }
  }, [records, scope, onChange])
  useEffect(() => {
    for (const {node} of targets) node.dataset.evidenceAnnotated = 'true'
    const problematic = targets.filter(x => evidenceProblem(x.record))
    const marked = [...new Set(problematic.map(x => x.node))]
    for (const node of marked) { node.dataset.evidenceProblem = 'true' }
    return () => { for (const node of marked) delete node.dataset.evidenceProblem; for (const {node} of targets) delete node.dataset.evidenceAnnotated }
  }, [targets])
  const missing = records.filter(r => !targets.some(x => x.record.key === r.key) && evidenceProblem(r))
  const groups = new Map<HTMLElement, EvidenceRecord[]>()
  for (const { node, record } of targets) {
    const group = groups.get(node) || []
    if (!group.some(r => r.key === record.key)) group.push(record)
    groups.set(node, group)
  }
  return <>
    {/* outlined 控件复用原有标签缺口；额外 outline 会穿过浮动文字。 */}
    <style>{`
      [data-evidence-annotated="true"] {position: relative;}
      [data-evidence-problem="true"] {outline: 2px solid #d32f2f; outline-offset: 2px; position: relative; border-radius: 8px;}
      [data-evidence-problem="true"].MuiOutlinedInput-root {outline: none;}
      [data-evidence-problem="true"].MuiOutlinedInput-root > .MuiOutlinedInput-notchedOutline {border-color: #d32f2f; border-width: 2px;}
      [data-evidence-caption="true"] {color: #d32f2f !important; cursor: pointer; pointer-events: auto !important;}
      [data-evidence-caption="true"]:hover {text-decoration: underline;}
      [data-evidence-caption="true"]:focus-visible {outline: 2px solid #d32f2f; outline-offset: 2px; border-radius: 2px;}
    `}</style>
    {[...groups].map(([node, group], i) => <FieldTrigger key={`${group[0].key}-${i}`} records={group} node={node} onOpen={onOpen} />)}
    {missing.length > 0 && <Box data-evidence-fallback sx={{ my: 1, borderLeft: 2, borderColor: 'warning.main', pl: 1.5 }}>
      <Typography variant="caption" color="text.secondary">待定位的来源核对（{missing.length}）</Typography>
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
