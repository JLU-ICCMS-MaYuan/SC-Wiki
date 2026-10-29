import { useEffect, useState } from 'react'
import { Alert, Box, Button, Card, CircularProgress, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { detailURL, type SearchView } from '../lib/searchNavigation'
import { useLanguage } from '../context/LanguageContext'
interface Result { paper_id:number;title:string;year?:number;journal?:string;doi?:string;matched_states?:number;state_id?:number;state_key?:string;material?:string;material_name?:string;pressure_gpa?:number;space_group?:string;space_group_number?:number;structure_optimization?:string;structures?:Array<{id:string}> }
interface Response {items:Result[];total:number;papers_total:number;states_total:number}
export default function SearchResults({query,view,page,returnTo,onPageChange}:{query:Record<string,unknown>;view:SearchView;page:number;returnTo:string;onPageChange:(page:number)=>void}) {
  const {t}=useLanguage(),[data,setData]=useState<Response|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(true),[retry,setRetry]=useState(0)
  const [loadedKey,setLoadedKey]=useState('')
  const key=JSON.stringify({...query,view,limit:20,offset:(page-1)*20})
  useEffect(()=>{
    let active=true;setData(null);setBusy(true);setError('')
    const timer=setTimeout(()=>{void api.post<Response>('/api/papers/search/results',JSON.parse(key)).then(value=>{if(active){setData(value);setLoadedKey(key)}}).catch(reason=>{if(active)setError(reason.message)}).finally(()=>{if(active)setBusy(false)})},300)
    return()=>{active=false;clearTimeout(timer)}
  },[key,retry])
  const current=loadedKey===key?data:null
  const total=current?.total??0,last=Math.max(1,Math.ceil(total/20))
  useEffect(()=>{if(current && page>last)onPageChange(last)},[current,page,last,onPageChange])
  return <Box sx={{minWidth:0}} aria-busy={busy}>
    {busy && <CircularProgress size={24} aria-label={t('search.loadingResults')} />}
    {error && <Alert severity="error" action={<Button onClick={()=>setRetry(v=>v+1)}>{t('search.retry')}</Button>}>{error}</Alert>}
    {current && <>
      <Typography variant="h6" sx={{mb:2}}>{t('search.resultCounts',{papers:current.papers_total,states:current.states_total})}</Typography>
      {!current.items.length && <Typography>{t('search.noResults')}</Typography>}
      {current.items.map(item=><Card key={view==='states'?item.state_id:item.paper_id} data-testid={view==='states'?'search-state-card':'search-paper-card'} sx={{p:2,mb:2,minWidth:0,overflowWrap:'anywhere'}}>
        <Typography variant="h6">{view==='papers'?item.title:`${item.material_name||item.material||'—'} · ${item.pressure_gpa??'—'} GPa · ${item.space_group||'—'} (${item.space_group_number??'—'}) · ${t('search.optimization.'+(item.structure_optimization||'unknown'))}`}</Typography>
        {view==='states' && <Typography variant="body2">{item.title}</Typography>}
        <Typography variant="body2">{[item.year,item.journal,item.doi].filter(Boolean).join(' · ')}</Typography>
        {view==='papers' && <Typography variant="body2">{t('search.matchedStates',{count:item.matched_states??0})}</Typography>}
        <Button component={Link} to={detailURL(`/papers/${item.paper_id}`,returnTo)} target="_blank" rel="noopener noreferrer">{t('search.viewPaper')}</Button>
        {item.structures?.map(model=><Button key={model.id} component={Link} to={detailURL(`/structures/${encodeURIComponent(model.id)}`,returnTo)} target="_blank" rel="noopener noreferrer">{t('search.viewStructure')}</Button>)}
      </Card>)}
      {total>20 && <Box sx={{display:'flex',alignItems:'center',gap:2}}><Button disabled={page<=1} onClick={()=>onPageChange(page-1)}>{t('search.previousPage')}</Button><Typography>{page} / {last}</Typography><Button disabled={page>=last} onClick={()=>onPageChange(page+1)}>{t('search.nextPage')}</Button></Box>}
    </>}
  </Box>
}
