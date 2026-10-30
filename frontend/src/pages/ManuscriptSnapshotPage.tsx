import type { PropertySpectrumListing } from '../lib/propertySpectra'
import { useEffect,useMemo,useState } from 'react'
import { useParams,useSearchParams } from 'react-router-dom'
import { Alert,Box,Button,CircularProgress,Typography } from '@mui/material'
import UploadTaskEditor from '../components/UploadTaskEditor'
import type { EvidenceRecord,EvidenceSource,FrozenManualEvidence } from '../components/EvidenceWorkflow'
import type { UploadDraft } from '../lib/paperProcessing'
import { api } from '../lib/api'
import SnapshotFileButton from '../components/SnapshotFileButton'
import type { Handoff } from './ManuscriptHandoffsPage'

interface File {file_id:string;original_filename:string}
interface Frozen {
  snapshot_id:string;snapshot_number:number;handoff:Handoff;
  content:{spectra?:PropertySpectrumListing;draft:UploadDraft;records:EvidenceRecord[];files:File[];
    manual:Array<{item_key:string;reason:string;no_evidence_reason:string;items:Array<{file_id?:string;filename?:string;text?:string;content?:string}>}>}
}

const emptySpectra:PropertySpectrumListing={items:[],jobs:[],version:'frozen',can_edit:false,can_review:false}

export default function ManuscriptSnapshotPage() {
  const {id,snapshotId}=useParams(),[params]=useSearchParams()
  const eventId=params.get('handoff')
  const [data,setData]=useState<Frozen>(),[error,setError]=useState(''),[retry,setRetry]=useState(0)
  const base=`/api/rag/handoffs/${id}/snapshots/${snapshotId}`
  useEffect(()=>{
    const abort=new AbortController();setData(undefined);setError('')
    void api.get<Frozen>(base+(eventId?`?event_id=${encodeURIComponent(eventId)}`:''),{signal:abort.signal})
      .then(setData).catch(e=>{if(!abort.signal.aborted)setError((e as Error).message)})
    return()=>abort.abort()
  },[base,eventId,retry])
  const frozen=useMemo(()=>{
    const source=(entry:EvidenceSource):EvidenceSource=>({...entry,
      snapshot_file_url:data?.content.files.some(f=>f.file_id===entry.file_id)
        ?`${base}/files/${encodeURIComponent(entry.file_id)}`:undefined})
    return {
      records:data?.content.records.map(r=>({...r,evidences:(r.evidences||[]).map(source)})),
      manual:data?.content.manual.map(m=>({...m,evidences:m.items.map(item=>source({
        file_id:item.file_id||'',chunk_index:0,source_name:item.filename||'人工提供资料',
        quote:item.text||item.content||m.reason||m.no_evidence_reason}))})) as FrozenManualEvidence[]|undefined,
    }
  },[data,base])
  if(error)return <Alert severity="error" action={<Button onClick={()=>setRetry(n=>n+1)}>重试</Button>}>{error}</Alert>
  if(!data)return <CircularProgress aria-label="加载冻结快照"/>
  return <Box sx={{py:2}}>
    <Typography variant="h4">只读整稿快照 S{data.snapshot_number}</Typography>
    {data.handoff&&<Typography>{data.handoff.actor_name} → {data.handoff.receiver} · {data.handoff.action} · {new Date(data.handoff.occurred_at).toLocaleString()}</Typography>}
    <Alert severity="info">这是正式交出时的完整内容。当前工作稿的修改不会改变本页。</Alert>
    {!data.content.spectra&&<Alert severity="info">该旧快照未保存独立谱数据，不加载当前谱替代。</Alert>}
    <UploadTaskEditor taskId={`snapshot-${data.snapshot_id}`} draftOverride={data.content.draft} readOnly
      frozenEvidenceRecords={frozen.records} frozenManualEvidence={frozen.manual}
      frozenSpectra={data.content.spectra || emptySpectra} onSubmitted={()=>undefined}/>
    {data.content.files.map(f=><SnapshotFileButton key={f.file_id} name={f.original_filename}
      url={`${base}/files/${encodeURIComponent(f.file_id)}`}/>)}
  </Box>
}
