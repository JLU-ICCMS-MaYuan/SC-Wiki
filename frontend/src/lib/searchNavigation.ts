export type SearchView = 'papers' | 'states'
export const SEARCH_FILTER_DEFAULTS = { formula:'',tcMin:0,tcMax:9999,pMin:0,pMax:9999,yMin:1900,yMax:2030,type:'All',review:'All',chartOnly:false }
export type SearchFilters = typeof SEARCH_FILTER_DEFAULTS
const keys: Record<keyof SearchFilters,string> = { formula:'keyword',tcMin:'tc_min',tcMax:'tc_max',pMin:'pressure_min',pMax:'pressure_max',yMin:'year_min',yMax:'year_max',type:'superconductor_type',review:'review_status',chartOnly:'chart_only' }
export function searchFilters(params: URLSearchParams): SearchFilters {
  const value = {...SEARCH_FILTER_DEFAULTS}
  for (const field of Object.keys(keys) as Array<keyof SearchFilters>) {
    const raw=params.get(keys[field]); if(raw==null)continue
    if(typeof value[field]==='number') { if(raw.trim() && Number.isFinite(Number(raw))) (value as any)[field]=Number(raw) }
    else if(field==='chartOnly') value[field]=raw==='true'
    else (value as any)[field]=raw
  }
  return value
}
export function updateFilters(params: URLSearchParams, filters: SearchFilters) {
  const next=new URLSearchParams(params)
  for(const field of Object.keys(keys) as Array<keyof SearchFilters>) {
    if(filters[field]===SEARCH_FILTER_DEFAULTS[field])next.delete(keys[field]);else next.set(keys[field],String(filters[field]))
  }
  for(const key of ['paper_page','state_page','structure_page'])next.delete(key)
  return next
}
export function searchRequest(params: URLSearchParams) {
  const f=searchFilters(params)
  const body: Record<string,unknown>={elements:(params.get('elements')||'').split(',').filter(Boolean),mode:params.get('mode')||'elements_combination_search'}
  if(params.has('formula')) {body.formula=params.get('formula');body.mode='formula_search';body.elements=[]}
  for(const field of Object.keys(keys) as Array<keyof SearchFilters>) if(f[field]!==SEARCH_FILTER_DEFAULTS[field])body[keys[field]]=field==='review'?String(f[field]).toLowerCase():f[field]
  return body
}
export function searchURL(selected: Iterable<string>,mode:string,formula:string) {
  const elements=[...new Set(selected)].sort()
  const params=new URLSearchParams(elements.length?{elements:elements.join(','),mode}:{formula:formula.trim(),mode:'formula_search'})
  params.set('view','papers');return '/search?'+params
}
export const searchPageNumber=(params:URLSearchParams,key:string)=>{const n=Number(params.get(key)||1);return Number.isInteger(n)&&n>0&&n<=5001?n:1}
// 仅允许真实业务来路；解码后再验证，拒绝协议相对、反斜线和控制字符绕过。
export function safeReturn(raw: string | null, fallback='/search') {
  if(!raw || !raw.startsWith('/') || raw.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(raw))return fallback
  try {
    const u=new URL(raw,'https://scwiki.invalid')
    let pathname=u.pathname
    for(let i=0;i<3 && /%[0-9a-f]{2}/i.test(pathname);i++)pathname=decodeURIComponent(pathname)
    if(u.origin!=='https://scwiki.invalid'||pathname.startsWith('//')||/[\\\u0000-\u0020\u007f]/.test(pathname)||!/^\/(search|papers|structures|upload|account|admin|superadmin|share|users|news)(\/|$)/.test(pathname))return fallback
    // 查询值保持原编码，避免把关键词中的%26／%20改成新的参数或空白。
    return u.pathname+u.search+u.hash
  } catch {return fallback}
}
export function detailURL(path:string,from:string){return path+'?'+new URLSearchParams({return:safeReturn(from)})}
