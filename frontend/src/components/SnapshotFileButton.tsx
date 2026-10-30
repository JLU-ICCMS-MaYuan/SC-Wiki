import { useEffect,useState } from 'react'
import { Alert,Button,Dialog,DialogContent,DialogTitle } from '@mui/material'
import { api } from '../lib/api'
import { useLanguage } from '../context/LanguageContext'

export default function SnapshotFileButton({url,name}:{url:string;name:string}) {
  const {lang}=useLanguage()
  const [blob,setBlob]=useState<string>()
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>()=>{if(blob)URL.revokeObjectURL(blob)},[blob])
  const open=async()=>{
    setBusy(true);setError('')
    try {setBlob(URL.createObjectURL(await api.download(url)))}
    catch(e){setError((e as Error).message)}
    finally{setBusy(false)}
  }
  return <>
    <Button size="small" disabled={busy} onClick={()=>void open()}>{lang==='zh'?'查看冻结依据：':'View frozen source: '}{name}</Button>
    {error&&<Alert severity="error">{error}</Alert>}
    <Dialog open={Boolean(blob)} onClose={()=>setBlob(undefined)} fullWidth maxWidth="lg">
      <DialogTitle>{name}<Button onClick={()=>setBlob(undefined)}>{lang==='zh'?'关闭':'Close'}</Button></DialogTitle>
      <DialogContent><iframe title={name} src={blob} style={{width:'100%',height:'75vh',border:0}} /></DialogContent>
    </Dialog>
  </>
}
