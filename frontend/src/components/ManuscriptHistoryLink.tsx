import { Link } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'

/** 静态标题入口；输入和保存不触发交接列表请求。 */
export default function ManuscriptHistoryLink({target,targetId}:{target:'upload'|'paper'|'revision';targetId:string}) {
  const {lang}=useLanguage()
  return <Link target="_blank" rel="noopener noreferrer"
    href={`/manuscripts/${target}/${encodeURIComponent(targetId)}/handoffs`} sx={{fontSize:14}}>
    {lang==='zh'?'交接记录与快照':'Handoffs and snapshots'}
  </Link>
}
