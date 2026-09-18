import type { DraftMaterialState } from './paperProcessing'

export function materialIdentityMissing(state: Pick<DraftMaterialState, 'material' | 'material_name'>) {
  return !state.material_name?.trim() && !state.material?.trim()
}

export function materialLabel(state: Pick<DraftMaterialState, 'material' | 'material_name'>) {
  const name = state.material_name?.trim() || ''
  const formula = state.material?.trim() || ''
  return name && formula ? `${name}（${formula}）` : name || formula
}
