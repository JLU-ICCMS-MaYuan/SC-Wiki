import {useEffect,useRef,useState} from 'react'
import {Autocomplete,Box,Button,MenuItem,Stack,TextField,Typography} from '@mui/material'
import contract from '../../../backend/data/scientific_form_contract.v1.json'
import {loadClassificationCatalogs,familyName} from '../lib/classifications'
import {useLanguage} from '../context/LanguageContext'
import {manualValueIdentity} from '../lib/manualEvidenceDrafts'

/** 未有专用设置的字段按契约类型接入；实际更新仍由宿主原回调持有。 */
export default function UnifiedFieldSettings({field,label,value,schema,readOnly,onApply,onClose,onPendingChange,choices}:{
 field:string;label:string;value:unknown;schema?:{type?:string;enum?:unknown[]};readOnly?:boolean;
 choices?:string[];onApply:(value:unknown)=>void;onClose:()=>void;onPendingChange?:(pending:boolean)=>void
}){
 const {t,dict,lang}=useLanguage(),initial=useRef(value),[error,setError]=useState('')
 const identity=manualValueIdentity(initial.current),changedOutside=manualValueIdentity(value)!==identity
 const key=field.split('.').at(-1)!
 const kind=(field.startsWith('paper.')?(contract.paper_fields as Record<string,string>)[key]:
  (contract.state_fields as Record<string,string>)[key] || (contract.state_scientific_fields as Record<string,string>)[key])
 const enumValues=schema?.enum || (contract.enums as Record<string,string[]>)[key]
 const list=kind?.endsWith('[]') || Array.isArray(value)
 const [current,setCurrent]=useState<unknown>(value),[catalog,setCatalog]=useState<string[]>(choices || []),[names,setNames]=useState<Record<string,string>>({})
 const family=['structure_families','material_families'].includes(key)
 const values=(Array.isArray(current)?current:[]).map(v=>typeof v==='object'&&v!==null?String((v as {name?:string}).name || ''):String(v))
 const numeric=kind?.startsWith('number') || kind==='integer' || ['number','integer'].includes(schema?.type || '') || typeof value==='number'
 useEffect(()=>{
  if(family)void loadClassificationCatalogs().then(c=>{const items=key==='structure_families'?c.structure_families:c.material_families;setCatalog(items.map(x=>x.name));setNames(Object.fromEntries(items.map(x=>[x.name,familyName(x,lang)])))}).catch(()=>{})
 },[family,key,lang])
 const edit=(next:unknown)=>{setCurrent(next);setError('');onPendingChange?.(manualValueIdentity(next)!==identity)}
 const close=()=>{onPendingChange?.(false);onClose()}
 const apply=()=>{
  if(readOnly)return
  if(changedOutside){setError(t('evidence.settingsConflict'));return}
  let next=current
  if(numeric && current!==null && current!==''){
   if(!Number.isFinite(Number(current)) || (kind==='integer'&&!Number.isInteger(Number(current)))){setError('请输入完整有效的数值');return}
   next=Number(current)
  }else if(numeric)next=null
  if(enumValues&&current==='')next=null
  if(manualValueIdentity(next)!==identity)onApply(next)
  close()
 }
 return <Stack component="form" spacing={2} onSubmit={e=>{e.preventDefault();apply()}}>
  <TextField label={t('evidence.settingsName')} value={label} slotProps={{input:{readOnly:true}}}/>
  {list?<Autocomplete multiple freeSolo={choices===undefined} options={catalog} value={values} getOptionLabel={v=>names[v] || v} disabled={readOnly}
    onChange={(_e,v)=>edit(v)} renderInput={params=><TextField {...params} label={t('evidence.settingsValue')}/>}/>
   : enumValues?<TextField select label={t('evidence.settingsValue')} value={String(current ?? '')} disabled={readOnly} onChange={e=>edit(e.target.value)}>
    <MenuItem value="">未填写</MenuItem>{enumValues.map(v=><MenuItem key={String(v)} value={String(v)}>{((dict.enums as any)[({paper_type:'paperType',theoretical_subtype:'theoreticalSubtype',superconductor_kind:'superconductorKind',state_kind:'stateKind',structure_optimization:'structureOptimization',material_dimensionality:'materialDimensionality',crystal_system:'crystalSystem'} as Record<string,string>)[key]] || {})[String(v)] || String(v)}</MenuItem>)}</TextField>
   : typeof current==='boolean'?<TextField select label={t('evidence.settingsValue')} value={String(current)} disabled={readOnly} onChange={e=>edit(e.target.value==='true')}>
    <MenuItem value="true">是</MenuItem><MenuItem value="false">否</MenuItem></TextField>
   : typeof current==='object'&&current!==null?<Typography>此内容由结构或派生工作区维护，请使用对应的专用入口。</Typography>
   : <TextField autoFocus label={t('evidence.settingsValue')} value={String(current ?? '')} disabled={readOnly}
     multiline={!numeric} minRows={numeric?undefined:3} onChange={e=>edit(e.target.value)}/>}
  {error&&<Typography color="error">{error}</Typography>}
  <Box sx={{display:'flex',justifyContent:'end',gap:1}}>
   <Button onClick={close}>{t(readOnly?'common.close':'common.cancel')}</Button>
   {!readOnly&&<Button type="submit" variant="contained" disabled={manualValueIdentity(current)===identity}>{t('evidence.settingsApply')}</Button>}
  </Box>
 </Stack>
}
