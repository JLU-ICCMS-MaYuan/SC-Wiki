import type { DraftMaterialState } from './paperProcessing'

/** 仅展示现有材料事实；缺失不猜测，零压是有效值。 */
export function materialStateSummary(state: Pick<DraftMaterialState, 'material' | 'reported_space_group_symbol' | 'pressure_value_gpa' | 'pressure_min_gpa' | 'pressure_max_gpa' | 'pressure_raw' | 'pressure_unit_raw'>): string {
  const pressure = state.pressure_value_gpa != null ? `${state.pressure_value_gpa} GPa`
    : state.pressure_min_gpa != null || state.pressure_max_gpa != null ? `${state.pressure_min_gpa ?? '?'}–${state.pressure_max_gpa ?? '?'} GPa`
      : state.pressure_raw?.trim() ? `${state.pressure_raw.trim()}${state.pressure_unit_raw?.trim() ? ` ${state.pressure_unit_raw.trim()}` : '（单位未填写）'}` : '压强未填写'
  const formula = state.material?.trim().replace(/\d/g, digit => '₀₁₂₃₄₅₆₇₈₉'[Number(digit)]) || '化学式未填写'
  return `${state.reported_space_group_symbol?.trim() || '空间群未填写'} · ${formula} · ${pressure}`
}
