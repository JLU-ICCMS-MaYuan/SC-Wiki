/** 仅展示现有材料事实；缺失不猜测，零压是有效值。 */
export function materialStateSummary(state: { material?: string | null; reported_space_group_symbol?: string | null; pressure_value_gpa?: number | null }): string {
  const pressure = state.pressure_value_gpa != null ? String(state.pressure_value_gpa) + ' GPa' : '压强未填写'
  const formula = state.material?.trim().replace(/\d/g, digit => '₀₁₂₃₄₅₆₇₈₉'[Number(digit)]) || '化学式未填写'
  return `${state.reported_space_group_symbol?.trim() || '空间群未填写'} · ${formula} · ${pressure}`
}
