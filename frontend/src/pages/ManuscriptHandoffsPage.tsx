import { useEffect,useRef,useState } from 'react'
import { Link,useParams } from 'react-router-dom'
import { Alert,Box,Button,Chip,CircularProgress,Paper,Typography } from '@mui/material'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'

export interface Handoff {
  event_id:number;occurred_at:string;actor_user_id:number;actor_name:string;
  snapshot_id:string;snapshot_number:number;reused:boolean;action:string;
  receiver:string;holder:'author'|'review'|'published';published_snapshot_id?:string;comment?:string
}
interface Listing {paper_id:number|null;events:Handoff[];state:Handoff|null;has_more?:boolean;can_return?:boolean;legacy_public?:boolean}

export default function ManuscriptHandoffsPage() {
  const {target,targetId}=useParams()
  const {user}=useAuth(),{lang}=useLanguage()
  const [data,setData]=useState<Listing>(),[error,setError]=useState(''),[loading,setLoading]=useState(true)
  const [retry,setRetry]=useState(0),[returning,setReturning]=useState(false)
  const [offset,setOffset]=useState(0)
  const operation=useRef<string | undefined>(undefined)
  useEffect(()=>{
    const abort=new AbortController();setLoading(true);setError('')
    if(!target||!['upload','paper','revision'].includes(target)||!targetId){setError('无效的稿件入口');setLoading(false);return}
    const params=new URLSearchParams({target,target_id:targetId,limit:'20',offset:String(offset)})
    void api.get<Listing>(`/api/rag/handoffs?${params}`,{signal:abort.signal})
      .then(setData).catch(e=>{if(!abort.signal.aborted)setError((e as Error).message)})
      .finally(()=>{if(!abort.signal.aborted)setLoading(false)})
    return()=>abort.abort()
  },[target,targetId,retry,offset])
  const returnRevision=async()=>{
    if(!data?.paper_id||returning)return
    operation.current??=crypto.randomUUID()
    setReturning(true);setError('')
    try{
      await api.post(`/api/rag/handoffs/${data.paper_id}/return`,{
        operation_id:operation.current,expected_snapshot_id:data.state?.snapshot_id})
      operation.current=undefined;setRetry(n=>n+1)
    }catch(e){setError((e as Error).message)}finally{setReturning(false)}
  }
  const state=data?.state
  return <Box sx={{maxWidth:1100,mx:'auto',py:3}}>
    <Typography variant="h4">{lang==='zh'?'交接记录与快照':'Handoffs and snapshots'}</Typography>
    {loading&&<CircularProgress aria-label="加载交接记录"/>}
    {error&&<Alert severity="error" action={<Button onClick={()=>setRetry(n=>n+1)}>重试</Button>}>{error}</Alert>}
    {!loading&&data&&<>
      <Box sx={{display:'flex',gap:1,my:2,flexWrap:'wrap'}}>
        <Chip label={`当前工作稿：${state?.holder==='author'?'原上传者':state?.holder==='review'?'审核人员':state?.holder==='published'?'已交出':data.legacy_public?'存量批准稿':'尚未交出'}`} />
        {state&&<Chip label={`最新交出快照：S${state.snapshot_number}`}/>}
        <Chip label={`公开批准版：${state?.published_snapshot_id?'见下方标记':data.legacy_public?'存量批准版，尚无新快照':'无'}`}/>
      </Box>
      {user&&['admin','superadmin'].includes(user.role)&&data.paper_id&&data.can_return&&
        <Button variant="outlined" disabled={returning} onClick={()=>void returnRevision()}>正式交还原上传者修订</Button>}
      <Box><Button disabled={!offset} onClick={()=>setOffset(n=>Math.max(0,n-20))}>上一页</Button>
        <Button disabled={!data.has_more} onClick={()=>setOffset(n=>n+20)}>下一页</Button></Box>
      {!data.events.length&&<Typography sx={{my:2}}>当前尚无新合同的正式交接快照；已有旧历史没有删除。</Typography>}
      {data.events.map(event=><Paper key={event.event_id} variant="outlined" sx={{p:2,my:2}}>
        <Typography fontWeight={700}>{event.actor_name||`#${event.actor_user_id}`} → {event.receiver}</Typography>
        <Typography>{new Date(event.occurred_at).toLocaleString()} · {event.action} · S{event.snapshot_number} · {event.reused?'沿用':'新建'}</Typography>
        {state?.published_snapshot_id===event.snapshot_id&&<Chip size="small" color="success" label="当前公开批准版"/>}
        {event.comment&&<Typography sx={{whiteSpace:'pre-wrap'}}>{event.comment}</Typography>}
        <Button component={Link} target="_blank" rel="noopener noreferrer"
          to={`/papers/${data.paper_id}/snapshots/${event.snapshot_id}?handoff=${event.event_id}`}>查看整稿</Button>
      </Paper>)}
    </>}
  </Box>
}
