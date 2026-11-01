import React from 'react'
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { EvidenceRegion } from '../../frontend/src/components/EvidenceRegion'
import { normalizeUploadDraft } from '../../frontend/src/lib/paperProcessing'
afterEach(()=>{cleanup();vi.restoreAllMocks()})

it('外部正式题录以真实外链和卷期页显示，不冒充PDF区域或原文页码',()=>{
 const fetch=vi.spyOn(globalThis,'fetch')
 render(<EvidenceRegion target={{target:'upload',target_id:'isolated'}} source={{
  file_id:'crossref:10.1073/pnas.1118168109',origin_kind:'external_bibliography',
  source_url:'https://api.crossref.org/works/10.1073%2Fpnas.1118168109',
  quote:JSON.stringify({DOI:'10.1073/pnas.1118168109',title:['Current paper'],volume:'109',issue:'17',page:'6463-6466'})}} />)
 expect(screen.getByRole('link',{name:'Crossref 正式题录（外部来源）'})).toHaveAttribute('href','https://api.crossref.org/works/10.1073%2Fpnas.1118168109')
 expect(screen.getByText(/109 卷 · 17 期 · 6463-6466/)).toBeVisible()
 expect(screen.queryByRole('button')).not.toBeInTheDocument()
 expect(fetch).not.toHaveBeenCalled()
})

it('旧详情从活跃草稿归一化移除，保留结果；泛量子标签不冒充SSCHA',()=>{
 const draft=normalizeUploadDraft({paper:{title:'Keep'},material_states:[{state_kind:'theoretical',
  material:'CaH6',pressure_value_gpa:200,structure_optimization:'anharmonic_quantum',
  structure_optimization_details:{method:'old',volume:'fixed'}}]})
 expect(draft.material_states[0]).not.toHaveProperty('structure_optimization_details')
 expect(draft.material_states[0].structure_optimization).toBe('unknown')
 expect(draft.material_states[0].pressure_value_gpa).toBe(200)
})
