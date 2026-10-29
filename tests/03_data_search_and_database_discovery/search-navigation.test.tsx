import {describe,it,expect} from 'vitest'
import {safeReturn,searchURL,searchFilters,searchRequest,searchPageNumber,updateFilters} from '../../frontend/src/lib/searchNavigation'
describe('检索地址与合法来源恢复',()=>{
 it.each(['https://evil.invalid','//evil.invalid','/%2fevil.invalid','/\\evil.invalid','/%255cevil.invalid','/search%0a','javascript:alert(1)','/auth'])('rejects unsafe return %s',raw=>expect(safeReturn(raw)).toBe('/search'))
 it('keeps legitimate query, view and page through detail refresh',()=>{
  const path='/search?elements=H%2CLa%2CSc&view=states&state_page=2'
  expect(safeReturn(path)).toContain('view=states');expect(safeReturn(path)).toContain('state_page=2')
  const p=new URLSearchParams(path.split('?')[1]);expect(searchPageNumber(p,'state_page')).toBe(2)
 })
 it('preserves encoded keyword characters without turning them into query separators',()=>expect(safeReturn('/search?keyword=a%26b%20c&view=states')).toBe('/search?keyword=a%26b%20c&view=states'))
 it('new result links normalize elements and default to papers',()=>expect(searchURL(['La','H','Sc','H'],'elements_exact_search','')).toBe('/search?elements=H%2CLa%2CSc&mode=elements_exact_search&view=papers'))
 it('reset removes filters and pagination while preserving query and view',()=>{
  const p=new URLSearchParams('elements=Hg&view=states&state_page=3&keyword=abc')
  const next=updateFilters(p,{...searchFilters(new URLSearchParams())})
  expect(next.get('view')).toBe('states');expect(next.get('elements')).toBe('Hg');expect(next.has('state_page')).toBe(false);expect(searchRequest(next)).not.toHaveProperty('keyword')
 })
})
