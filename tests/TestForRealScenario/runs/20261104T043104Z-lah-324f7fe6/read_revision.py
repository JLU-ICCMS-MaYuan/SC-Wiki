"""本篇返修／审核工作稿与有效来源的只读留证；不触发业务调用。"""
from pathlib import Path
import sys,json
from dotenv import load_dotenv
load_dotenv('.env')
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from sqlalchemy import select,event
from backend.database import SessionLocal
from backend import models as M
from backend.workdraft_models import ScientificWorkDraft,ScientificFieldSourceUse,ScientificSourceItem
run=Path(__file__).resolve().parent
label=sys.argv[1]
with SessionLocal() as s:
 def ro(c,cur,st,p,ctx,m):
  if not st.lstrip().upper().startswith(('SELECT','SHOW')):raise RuntimeError('只读限制')
 event.listen(s.get_bind(),'before_cursor_execute',ro)
 p=s.get(M.Paper,1429);assert p.doi=='10.1073/pnas.1704505114'
 r=s.get(M.PaperRevisionDraft,1429);a=s.get(M.ScientificReviewDraft,1429)
 draft=r.draft if r else a.draft if a else None
 targets=['1429']+([r.revision_id] if r else [])
 out={'revision':{c.name:getattr(r,c.name) for c in r.__table__.columns} if r else None,'admin':{c.name:getattr(a,c.name) for c in a.__table__.columns}if a else None,'workdrafts':[{c.name:getattr(x,c.name)for c in x.__table__.columns}for x in s.scalars(select(ScientificWorkDraft).where(ScientificWorkDraft.target_id.in_(targets)))],'checks':[{c.name:getattr(x,c.name)for c in x.__table__.columns}for x in s.scalars(select(M.ScientificEvidenceCheck).where(M.ScientificEvidenceCheck.target_id.in_(targets)))]}
 keys=[x['target']+':'+x['target_id'] for x in out['workdrafts']]
 out['uses']=[{c.name:getattr(x,c.name)for c in x.__table__.columns}for x in s.scalars(select(ScientificFieldSourceUse).where(ScientificFieldSourceUse.work_key.in_(keys)))]
 ids={x['source_id']for x in out['uses']}
 out['source_items']=[{'id':x.id,'namespace':x.namespace,'payload':x.payload}for x in s.scalars(select(ScientificSourceItem).where(ScientificSourceItem.id.in_(ids)))]
 s.rollback()
(run/(label+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
print(json.dumps({'revision_id':(out['revision']or{}).get('revision_id'),'version':(out['revision']or{}).get('draft_version'),'title':((draft or{}).get('paper')or{}).get('title'),'checks':len(out['checks']),'source_uses':len(out['uses']),'source_items':len(out['source_items']),'workdrafts':len(out['workdrafts'])},ensure_ascii=False))
