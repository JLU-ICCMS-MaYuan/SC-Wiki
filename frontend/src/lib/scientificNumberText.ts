/** 约数只修饰与原文匹配的当前数值，不能以旧原文覆盖改值或空值。 */
export function approximateNumberMatches(value: number, raw?: unknown, unit?: unknown): boolean {
  const match = typeof raw === 'string'
    ? raw.trim().match(/^(?:~|≈|∼|约|about\s+|approximately\s+)\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)(.*)$/i)
    : null
  if (!match || Number(match[1]) !== value) return false
  const suffix = match[2].trim().toLowerCase()
  if (!suffix || unit == null) return true
  const name = String(unit).toLowerCase()
  const aliases = name === 'k' ? ['k', 'kelvin'] : ['1', 'dimensionless'].includes(name) ? ['1', 'dimensionless'] : [name]
  return aliases.some(alias => suffix === alias || suffix.startsWith(alias + ' ') || suffix.startsWith(alias + '('))
}

export function scientificNumberText(value: number, raw?: unknown, unit?: unknown): string {
  return `${approximateNumberMatches(value, raw, unit) ? '≈' : ''}${value}`
}
