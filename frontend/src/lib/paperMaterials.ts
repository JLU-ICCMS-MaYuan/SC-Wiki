export interface MaterialSummaryState {
  state_key?: string
  material_name?: string | null
  material?: string | null
  reported_space_group_symbol?: string | null
  pressure_value_gpa?: number | null
  superconductor?: { chemical_formula?: string | null } | null
}

export function researchMaterials(states: MaterialSummaryState[]): string[] {
  return [...new Set(states.map(state => state.material_name?.trim() || state.material?.trim() || '').filter(Boolean))]
}

export function locateMaterialState(trigger: HTMLElement, index: number, stateKey?: string) {
  const root = trigger.closest('[data-evidence-scope], [data-paper-detail]')
  const state = stateKey
    ? Array.from(root?.querySelectorAll<HTMLElement>('[data-material-state-index]') || []).find(node => node.dataset.stateKey === stateKey)
    : root?.querySelector<HTMLElement>(`[data-material-state-index="${index}"]`)
  if (!state) return
  for (let parent = state.parentElement; parent && parent !== root; parent = parent.parentElement) {
    if (parent instanceof HTMLDetailsElement) parent.open = true
  }
  const header = state.querySelector<HTMLElement>('[data-state-toggle]')
  if (header?.getAttribute('aria-expanded') === 'false') header.click()
  state.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
  ;(header || state).focus({ preventScroll: true })
}
