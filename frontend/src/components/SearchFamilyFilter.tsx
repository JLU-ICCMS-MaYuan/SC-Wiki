import {useEffect,useState} from 'react'
import {Alert,Box,Button,MenuItem,Select} from '@mui/material'
import {familyName,loadClassificationCatalogs,refreshClassificationCatalogs,type ClassificationTerm} from '../lib/classifications'
import {useLanguage} from '../context/LanguageContext'

// 搜索与上传／审核读取同一目录；旧地址的别名只用于恢复已选项。
export default function SearchFamilyFilter({value,onChange}:{value:string;onChange:(value:string)=>void}) {
 const {lang,t}=useLanguage()
 const [families,setFamilies]=useState<ClassificationTerm[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(false),[retry,setRetry]=useState(0)
 useEffect(()=>{
  let active=true;setLoading(true);setError(false)
  void (async()=>{
   try {const catalog=await (retry?refreshClassificationCatalogs():loadClassificationCatalogs());if(active)setFamilies(catalog.material_families||[])}
   catch {if(active)setError(true)}
   finally {if(active)setLoading(false)}
  })()
  return()=>{active=false}
 },[retry])
 const normalize=(name:string)=>name.normalize('NFKC').toLowerCase().replace(/[_-]+/g,' ').trim().replace(/\s+/g,' ')
 const selected=families.find(f=>String(f.id)===value || [f.name,f.name_zh,f.name_en,...f.aliases].some(name=>!!name&&normalize(name)===normalize(value)))
 const displayValue=selected?String(selected.id):value
 return <Box sx={{width:'100%',minWidth:0}}>
  <Select fullWidth variant="standard" disableUnderline value={displayValue} disabled={loading||error}
   inputProps={{'aria-label':t('search.superconductorType')}}
   onChange={e=>onChange(e.target.value)} sx={{fontSize:14,fontWeight:650,'& .MuiSelect-select':{py:1.1,px:1.5}}}>
   <MenuItem value="All">{t('search.allTypes')}</MenuItem>
   {value!=='All'&&!selected&&<MenuItem value={value} disabled>{loading?t('search.catalogLoading'):t('search.unknownType')}</MenuItem>}
   {families.map(f=><MenuItem key={f.id} value={String(f.id)}>{familyName(f,lang)}</MenuItem>)}
  </Select>
  {error&&<Alert severity="warning">{t('search.catalogUnavailable')}<Button onClick={()=>setRetry(n=>n+1)}>{t('search.retry')}</Button></Alert>}
 </Box>
}
