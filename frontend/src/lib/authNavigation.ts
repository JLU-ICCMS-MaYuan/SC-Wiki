export function safeAuthReturnTo(value: string | null | undefined): string | null {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return null
  // 解码仅用于拒绝绕过，返回原路径以保留业务 query/hash 的编码。
  let decoded = value
  for (let i = 0; i < 4; i++) {
    if (!decoded.startsWith('/') || decoded.startsWith('//') || [...decoded].some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127 || char.charCodeAt(0) === 92)) return null
    const path = decoded.split(/[?#]/, 1)[0].toLowerCase()
    if (path === '/auth' || path.startsWith('/auth/') || path === '/auth-demo.html') return null
    try {
      const next = decodeURIComponent(decoded)
      if (next === decoded) break
      decoded = next
    } catch { return null }
  }
  if (/%(?:2f|5c|0[0-9a-f]|1[0-9a-f])/i.test(decoded)) return null
  try {
    const parsed = new URL(value, 'https://sc-wiki.invalid')
    const path = parsed.pathname.toLowerCase()
    if (parsed.origin !== 'https://sc-wiki.invalid' || path === '/auth' || path.startsWith('/auth/') || path === '/auth-demo.html') return null
    return parsed.pathname + parsed.search + parsed.hash
  } catch { return null }
}

export function authHref(location: { pathname: string; search?: string; hash?: string }): string {
  const returnTo = safeAuthReturnTo(location.pathname + (location.search || '') + (location.hash || ''))
  return returnTo ? `/auth?returnTo=${encodeURIComponent(returnTo)}` : '/auth'
}
