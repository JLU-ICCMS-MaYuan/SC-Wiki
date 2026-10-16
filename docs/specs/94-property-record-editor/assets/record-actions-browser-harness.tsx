import React,{useState} from 'react'
import {createRoot} from 'react-dom/client'
import {BrowserRouter} from 'react-router-dom'
import {ThemeProvider,CssBaseline,Box,Button,FormControlLabel,Checkbox,Typography} from '@mui/material'
import theme from './src/theme'
import PropertyModuleEditor from './src/components/PropertyModuleEditor'
import {api} from './src/lib/api'
import {emptyPropertyModule,emptyPropertyRecord} from './src/lib/propertyModules'
import {newStabilityRecord} from './src/lib/thermodynamicStability'
import matrix from './record-actions-fixtures.json'
const definitions=matrix.definitions
const custom=definitions.find(d=>d.property_code==='custom')!
const codes=['electronic_properties','dynamical_properties','thermodynamical_properties','superconductive_properties'] as const
const defs=codes.map(module_code=>({...custom,definition_key:'record.'+module_code+'.custom',module_code})).concat(definitions.filter(d=>d.property_code!=='custom') as any)
const dosDefinition={...defs[0],definition_key:'record.electronic_properties.dos_fermi',property_code:'dos_fermi',json_schema:{type:'object',properties:{}}};defs.push(dosDefinition as any)
api.get=(async(path:string)=>path.startsWith('/api/form-definitions?')?defs:defs.find(d=>path.includes(encodeURIComponent(d.definition_key)))) as typeof api.get
const defaults=()=>codes.map(code=>{
 const module=emptyPropertyModule(code)
 const r={...emptyPropertyRecord(code),record_key:code+'-one',name_raw:'示例性质',value_raw:'1.5',value_number:1.5,evidences:[{filename:'example.pdf',page:2,quote:'Isolated validation fixture'}]}
 if(code==='electronic_properties')module.records=[{...r,property_code:'dos_fermi',definition_key:dosDefinition.definition_key,name_raw:'N(Ef)',value_kind:'text',value_raw:'18.76',value_text:'18.76',value_number:null,unit_raw:'states/spin/Ry/f.u.'}]
 if(code==='dynamical_properties')module.records=[{...r,name_raw:'最小声子频率',unit_raw:'THz'}]
 if(code==='thermodynamical_properties')module.records=[newStabilityRecord({...r,value_number:null}),{...r,record_key:code+'-two',name_raw:'形成焓',unit_raw:'eV/atom'}]
 if(code==='superconductive_properties')module.records=[{...r,record_type:'predicted_tc',property_code:'tc',method_code:'allen_dynes',definition_key:definitions[0].definition_key,name_raw:'critical temperature',value_raw:'206',value_number:206,unit_raw:'K',payload:{parameters:{lambda_ep:2.1,omega_log:960,mu_star:0.10},calculation_conditions:{calculation_code:'QE'}}},{...r,record_key:code+'-two',record_type:'measured_tc',property_code:'tc',method_code:'resistivity',definition_key:definitions.find(d=>d.record_type==='measured_tc')!.definition_key,name_raw:'Measured Tc',value_raw:'185',value_number:185,unit_raw:'K',payload:{experimental_conditions:{description:'Four-probe validation fixture'}}}]
 return module
})
function App(){const[modules,setModules]=useState(defaults),[readOnly,setReadOnly]=useState(false),[width,setWidth]=useState('100%'),[last,setLast]=useState('尚未修改预览')
return <ThemeProvider theme={theme}><CssBaseline/><Box sx={{p:2,bgcolor:'background.default'}}><Typography variant="h6">物性记录操作 · 正式共享组件</Typography><Typography variant="body2">隔离样例；没有连接业务草稿和保存接口。</Typography><Box sx={{display:'flex',gap:2,my:2}}><Button onClick={()=>setWidth(width==='360px'?'100%':'360px')}>切换 360px</Button><FormControlLabel label="只读" control={<Checkbox checked={readOnly} onChange={e=>setReadOnly(e.target.checked)}/>}/><Button onClick={()=>{setModules(defaults());setLast('已恢复隔离样例')}}>恢复样例</Button></Box><Box id="validation-stage" sx={{width,maxWidth:'100%',mx:'auto',p:1,border:'1px solid',borderColor:'divider'}}><PropertyModuleEditor modules={modules} readOnly={readOnly} onChange={(next,deletion)=>{setModules(next);setLast(deletion?.deletedRecordKey?'删除键：'+deletion.deletedRecordKey:'已修改隔离输入')}}/></Box><Typography role="status">{last}</Typography></Box></ThemeProvider>}
createRoot(document.getElementById('root')!).render(<BrowserRouter><App/></BrowserRouter>)
