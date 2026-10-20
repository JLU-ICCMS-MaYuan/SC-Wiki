import type { StructureCandidate } from './paperProcessing'

export interface LatticeObservation {
  record_key: string; material: string; pressure_value_gpa?: number; space_group_symbol?: string
  retention?: 'pending' | 'retained' | 'excluded'; calculation_label?: string | null
  cell_parameters: Record<string, number>; sources: Array<Record<string, unknown>>; [key: string]: any
}

/** 新提取只替换待核对的自动结果，保留已有决定、人工来源及结构附件。 */
export function mergeStructuralPreview<T extends StructureCandidate | LatticeObservation>(previous: T[], incoming: T[]): T[] {
  const identity = (value: T) => 'candidate_id' in value ? value.candidate_id : value.record_key
  const protectedItems = previous.filter(value => value.retention === 'retained' || value.retention === 'excluded'
    || ('confirmation' in value && ['confirmed', 'excluded'].includes(value.confirmation || ''))
    || ('source_kind' in value && value.source_kind === 'attachment') || Boolean(value.user_note))
  const protectedKeys = new Set(protectedItems.map(identity))
  return [...protectedItems, ...incoming.filter(value => !protectedKeys.has(identity(value)))]
}
