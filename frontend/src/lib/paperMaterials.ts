export interface MaterialRelation {
  material?: string
  relation?: string
  [sourceField: string]: unknown
}

export interface MaterialSummaryState {
  state_key?: string
  material_name?: string | null
  material?: string | null
}

/** 仅解析已知契约；无法解析的历史内容保留原值，禁止编辑时静默清空。 */
export function parseMaterialRelations(value: unknown): MaterialRelation[] | null {
  if (value == null || value === '') return []
  let parsed = value
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed) } catch { return null }
  }
  if (!Array.isArray(parsed) || !parsed.every(item => item && typeof item === 'object' && !Array.isArray(item)
    && (item.material == null || typeof item.material === 'string')
    && (item.relation == null || typeof item.relation === 'string'))) return null
  return parsed as MaterialRelation[]
}

export function researchMaterials(states: MaterialSummaryState[]): string[] {
  return [...new Set(states.map(state => state.material_name?.trim() || state.material?.trim() || '').filter(Boolean))]
}

export function locateMaterialState(trigger: HTMLElement, index: number) {
  const root = trigger.closest('[data-evidence-scope], [data-paper-detail]')
  const state = root?.querySelector<HTMLElement>(`[data-material-state-index="${index}"]`)
  if (!state) return
  for (let parent = state.parentElement; parent && parent !== root; parent = parent.parentElement) {
    if (parent instanceof HTMLDetailsElement) parent.open = true
  }
  const header = state.querySelector<HTMLElement>('[data-state-toggle]')
  if (header?.getAttribute('aria-expanded') === 'false') header.click()
  state.scrollIntoView({ block: 'start', behavior: 'smooth' })
  ;(header || state).focus({ preventScroll: true })
}
