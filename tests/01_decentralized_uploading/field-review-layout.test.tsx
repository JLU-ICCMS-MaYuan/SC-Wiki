import '@testing-library/jest-dom/vitest'
import React, { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import PropertyModuleEditor from '../../frontend/src/components/PropertyModuleEditor'
import EvidenceFieldMarkers from '../../frontend/src/components/EvidenceFieldMarkers'
import EvidenceHistoryTimeline from '../../frontend/src/components/EvidenceHistoryTimeline'
import { useEvidenceWorkflow, type EvidenceRecord } from '../../frontend/src/components/EvidenceWorkflow'
import { currentEvidenceField } from '../../frontend/src/lib/evidenceFields'
import { clearFormDefinitionCache } from '../../frontend/src/lib/formDefinitions'
import { api } from '../../frontend/src/lib/api'
vi.mock('../../frontend/src/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() } }))
const row: any = { record_key:'r', module_code:'superconductive_properties',record_type:'predicted_tc',property_code:'tc',
 definition_key:'record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version:1,method_code:'isotropic_eliashberg',name_raw:'Tc',
 value_kind:'number',value_number:311,value_raw:'311',canonical_unit:'K',unit_raw:'K',payload:{parameters:{lambda_ep:3.94,omega_log:745,mu_star:.1},calculation_conditions:{calculation_code:'Quantum ESPRESSO'}} }
const definition: any = { definition_key:row.definition_key,version:1,target_kind:'property_record',module_code:'superconductive_properties',
 record_type:'predicted_tc',property_code:'tc',method_code:'isotropic_eliashberg',core_schema:{},json_schema:{type:'object'},ui_schema:{},status:'published',checksum:'test' }
const prefix='material_states[0].property_modules[0].records[0].'
const records: EvidenceRecord[] = [
 {key:'method',item_key:'method',record_key:'r',module_key:'m',state_key:'s',record_field:'method_code',field:prefix+'method_code',fields:[prefix+'method_code'],label:'预测方法',status:'supported',reason:'仅核对当前方法',current_value:'isotropic_eliashberg',evidences:[{file_id:'main',chunk_index:0,quote:'method'}],audit_events:[{id:'run-method',actor:{kind:'ai',model:'Method Model'},occurred_at:'2026-10-19T09:00:00Z',summary:'AI核对当前方法，未改值'}]},
 {key:'lambda',item_key:'lambda',record_key:'r',module_key:'m',state_key:'s',record_field:'payload.parameters.lambda_ep',field:prefix+'payload.parameters.lambda_ep',fields:[prefix+'payload.parameters.lambda_ep'],label:'λ独立核对',status:'unsupported',reason:'λ示例尚需核对',current_value:3.94,evidences:[]},
 {key:'software',item_key:'software',record_key:'r',module_key:'m',state_key:'s',record_field:'payload.calculation_conditions.calculation_code',field:prefix+'payload.calculation_conditions.calculation_code',fields:[prefix+'payload.calculation_conditions.calculation_code'],label:'计算软件',status:'supported',reason:'软件来源',current_value:'Quantum ESPRESSO',evidences:[{file_id:'main',chunk_index:0,page_start:5,quote:'Quantum ESPRESSO'}]},
]
beforeEach(()=>{vi.mocked(api.get).mockImplementation(async path=>(path.includes('/form-definitions')?(path.includes('?')?[definition]:definition):{ok:true,data:{changed:false,items:[],reason:'',history:[]}})as never)
 vi.mocked(api.post).mockImplementation(async path=>(path.endsWith('/preflight')?{version:'v',needs_check:true,records:structuredClone(records)}:{status:'located',image:'data:image/png;base64,eA==',region:[0,0,1,1]})as never)})
afterEach(()=>{cleanup();clearFormDefinitionCache();vi.clearAllMocks()})
function Harness({readOnly=false}:{readOnly?:boolean}){
 const[modules,setModules]=useState<any[]>([{module_key:'m',module_code:'superconductive_properties',definition_key:'module.superconductive_properties',definition_version:1,display_order:0,records:[structuredClone(row)]}])
 const flow=useEvidenceWorkflow({target:{target:'upload',target_id:'t'},readOnly,getCurrentValue:r=>currentEvidenceField(r,{},[{state_key:'s',material:'LaSc2H24',pressure_value_gpa:150,property_modules:modules}])})
 return <div data-evidence-scope="native"><div data-state-key="s"><PropertyModuleEditor modules={modules} readOnly={readOnly} basePath="material_states.0.property_modules" onChange={next=>{setModules(next);flow.invalidate('material_states[0].property_modules')}}/></div>
 <EvidenceFieldMarkers records={flow.records} scope="native" onOpen={flow.openIssue} onChange={flow.invalidate}/>{flow.dialog}</div>
}
const drawer=()=>document.querySelector('.evidence-review-drawer') as HTMLElement
async function show(){await act(async()=>render(<Harness/>));fireEvent.click(screen.getByText('超导性质'));await screen.findByRole('button',{name:/计算软件：查看来源核对/})}
it('方法只审自身，无Tc集合审核入口；三页签和四块分区不混入其他子项',async()=>{
 await show()
 expect(screen.queryByRole('button',{name:'超导转变温度 Tc'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'预测方法',exact:true}))
 expect(within(drawer()).getByText('仅核对当前方法')).toBeVisible()
 expect(within(drawer()).queryByText('λ示例尚需核对')).not.toBeInTheDocument()
 expect(within(drawer()).getAllByRole('tab')).toHaveLength(3)
 expect(within(drawer()).getByText('系统找到的原文').closest('details')).toHaveAttribute('open')
 expect(within(drawer()).getByText('人工修改记录').closest('details')).not.toHaveAttribute('open')
 expect(within(drawer()).getByText('AI 理由').closest('details')).not.toHaveAttribute('open')
 fireEvent.click(within(drawer()).getByRole('tab',{name:'历史记录'}))
 const history=within(drawer()).getByText('历史记录',{selector:'summary'});expect(history.closest('details')).not.toHaveAttribute('open')
 fireEvent.click(history)
 expect(within(drawer()).getByText('AI · Method Model')).toBeVisible()
 expect(within(drawer()).queryByText('λ示例尚需核对')).not.toBeInTheDocument()
})
it('设置页签复用现有编辑器，切换保留未应用输入，原PDF区域折叠重开不重复请求',async()=>{
 await show();fireEvent.click(screen.getByRole('button',{name:/计算软件：查看来源核对/}))
 fireEvent.click(within(drawer()).getByRole('tab',{name:'字段设置'}))
 expect(await within(drawer()).findByLabelText('字段名称（key）')).toBeVisible()
 expect(document.querySelectorAll('.MuiDrawer-paper')).toHaveLength(1)
 fireEvent.change(within(drawer()).getByLabelText('值'),{target:{value:'未应用内容'}})
 fireEvent.click(within(drawer()).getByRole('tab',{name:'来源核对'}))
 fireEvent.click(within(drawer()).getByRole('button',{name:'查看原 PDF 区域'}))
 expect(await within(drawer()).findByRole('img')).toBeVisible()
 fireEvent.click(within(drawer()).getByText('系统找到的原文'))
 expect(within(drawer()).getByRole('img',{hidden:true})).not.toBeVisible()
 fireEvent.click(within(drawer()).getByRole('tab',{name:'字段设置'}))
 expect(within(drawer()).getByLabelText('值')).toHaveValue('未应用内容')
 fireEvent.click(within(drawer()).getByRole('tab',{name:'来源核对'}))
 fireEvent.click(within(drawer()).getByText('系统找到的原文'))
 expect(within(drawer()).getByRole('img')).toBeVisible()
 expect(vi.mocked(api.post).mock.calls.filter(([path])=>path.endsWith('/region'))).toHaveLength(1)
})
it('其他问题仅在独立导航中可达；只读不显示重查和完成',async()=>{
 await act(async()=>render(<Harness readOnly/>));fireEvent.click(screen.getByText('超导性质'))
 fireEvent.click(await screen.findByRole('button',{name:'待处理项（1）'}))
 fireEvent.click(screen.getByRole('button',{name:'λ独立核对'}))
 await waitFor(()=>expect(within(drawer()).getAllByText('λ示例尚需核对')[0]).toBeVisible())
 expect(within(drawer()).queryByRole('button',{name:'完成',exact:true})).not.toBeInTheDocument()
 expect(within(drawer()).queryByRole('button',{name:'让系统重新查找'})).not.toBeInTheDocument()
 expect(within(drawer()).queryByRole('button',{name:'计算软件'})).not.toBeInTheDocument()
})
it('历史有真实actor/time才排序；无时间或时区明确降级且显示前后值详情',()=>{
 const record={...records[0],history:[{current_value:1,reason:'旧值'}]}
 render(<EvidenceHistoryTimeline record={record} manual={[{id:'human',changed:true,actor_user_id:5,actor_name:'历史姓名',created_at:'2026-10-19T10:00:00Z',before_value:3.9,after_value:3.94,reason:'原文修正',items:[],no_evidence_reason:''}]}/>)
 expect(screen.getByText('AI · Method Model')).toBeInTheDocument();expect(screen.getByText('历史姓名')).toBeInTheDocument()
 expect(screen.getByText('修改人未记录')).toBeInTheDocument();expect(screen.getByText('时间未记录')).toBeInTheDocument()
 const articles=screen.getAllByRole('article');expect(within(articles[0]).getByText('历史姓名')).toBeInTheDocument()
 fireEvent.click(within(articles[0]).getByText('查看详情'));expect(within(articles[0]).getByText('3.94')).toBeVisible()
})
