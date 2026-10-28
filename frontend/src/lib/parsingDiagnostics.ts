export type TriageStatus = 'system_checked' | 'system_pending' | 'user_review'
export interface Triage {
  id: string
  version?: string
  category: string
  status: TriageStatus
  reason: string
  filename?: string
  file_role?: string
  checked_value?: unknown
  differences?: Array<{selected: string; alternative: string}>
  difference_count?: number
  evidence?: { url?: string; year?: number; doi?: string; title?: string; status?: string; native_text?: string; text_layer_match?: string; source_error?: string }
  impact?: { status: string; references: Array<{ state_key?: string; record_key?: string; label: string; kind: string }> }
}
export interface ParsingDifference {
  file_id: string; pdf_page: number; kind: string; selected?: string; anchor?: string
  engine?: string; selected_text?: string
  alternatives: Array<{ block_id?: string; engine?: string; text: string }>
  triage?: Triage
}
export interface BibliographyDifference {
  field: string; grobid_value: unknown; extracted_value: unknown; selected_value?: unknown; triage?: Triage
}
export interface ParsingSnapshot { regions: ParsingDifference[]; bibliography: BibliographyDifference[] }
export const EMPTY_PARSING_SNAPSHOT: ParsingSnapshot = { regions: [], bibliography: [] }

/** 只在外部草稿加载/刷新时调用；编辑输入不重算来源诊断。 */
export function retainParsingSnapshot(previous: ParsingSnapshot, draft: {
  parsing_conflicts?: ParsingDifference[]; bibliography_conflicts?: BibliographyDifference[]
}): ParsingSnapshot {
  const next = { regions: draft.parsing_conflicts || [], bibliography: draft.bibliography_conflicts || [] }
  return JSON.stringify(previous) === JSON.stringify(next) ? previous : next
}

export function groupParsingDifferences(regions: ParsingDifference[]) {
  const groups = new Map<string, ParsingDifference[]>()
  for (const region of regions) {
    const category = region.triage?.category || 'unclassified'
    const key = ['layout', 'notation', 'segmentation', 'table', 'identifier', 'symbol'].includes(category) ? category : 'unclassified'
    const items = groups.get(key)
    if (items) items.push(region)
    else groups.set(key, [region])
  }
  const order = ['identifier', 'symbol', 'table', 'unclassified', 'notation', 'segmentation', 'layout']
  return [...groups].sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
}
