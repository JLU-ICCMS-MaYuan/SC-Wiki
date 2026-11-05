"""仅SELECT当前论文；Tc按模块共同资料展开，禁止据空直列判定丢失。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from sqlalchemy import select,event
from backend.database import SessionLocal
from backend import models as M
from backend.services.scientific_draft_rewrite import _record_snapshot
from backend.ingest.tc_contexts import expand_module
from backend.storage.paths import resolve_file
run=Path(__file__).resolve().parent
paper_id=int(sys.argv[1]);label=sys.argv[2];task=sys.argv[3]
with SessionLocal() as session:
 engine=session.get_bind()
 def select_only(conn,cursor,statement,parameters,context,executemany):
  if not statement.lstrip().upper().startswith(('SELECT','SHOW')):raise RuntimeError('核验脚本禁止写数据库')
 event.listen(engine,'before_cursor_execute',select_only)
 p=session.get(M.Paper,paper_id)
 assert p is not None and p.doi=='10.1073/pnas.1704505114' and p.upload_task_id==task,'论文身份不符'
 out={'paper':{k:getattr(p,k) for k in ('id','title','doi','review_status','content_revision','approved_revision','uploaded_by_user_id','reviewed_by_user_id','review_comment','reviewed_at','upload_task_id')},'states':[],'files':[]}
 for s in sorted(p.material_states,key=lambda s:s.id):
  row={k:getattr(s,k) for k in ('id','state_key','material_name','pressure_value_gpa','reported_space_group_symbol','reported_space_group_number','structure_optimization')}
  row['material']=s.superconductor.chemical_formula if s.superconductor else None
  row['property_modules']=[]
  for m in s.property_modules:
   module={'module_key':m.module_key,'module_code':m.module_code,'metadata':m.metadata_json,'records':[_record_snapshot(r,module_code=m.module_code) for r in m.records]}
   row['property_modules'].append(expand_module(module))
  out['states'].append(row)
 for f in session.scalars(select(M.PaperFile).where(M.PaperFile.paper_id==paper_id).order_by(M.PaperFile.sort_order)):
  item={k:getattr(f,k) for k in ('id','role','original_filename','stored_path','size','sha256','paper_revision')}
  if f.role in ('main','supplementary'):
   local=resolve_file(f.stored_path,size=f.size,sha256=f.sha256,media_type=f.media_type)
   item['readback_sha256']=hashlib.sha256(local.read_bytes()).hexdigest()
   assert item['readback_sha256']==f.sha256
  out['files'].append(item)
 out['history']=[{'event_id':e.id,'event_type':e.event_type,'status':e.review_status,'comment':e.review_comment,'actor_id':e.actor_user_id,'time':e.occurred_at,'handoff':(e.classification_snapshot or {}).get('handoff')} for eid in session.scalars(select(M.PaperHistoryEvent.id).where(M.PaperHistoryEvent.paper_id==paper_id).order_by(M.PaperHistoryEvent.id)) for e in [session.get(M.PaperHistoryEvent,eid)]]
 out['field_sources']=[{'field':s.field_path,'item_key':s.item_key,'content_hash':s.content_hash,'source_hash':s.source_hash,'result':s.result} for s in session.scalars(select(M.ScientificEvidenceSource).where(M.ScientificEvidenceSource.paper_id==paper_id,M.ScientificEvidenceSource.paper_revision==p.content_revision))]
 structure_columns=[c for c in M.StructureModel.__table__.columns if c.name not in {'created_at','updated_at'}]
 out['structures']=[dict(row) for row in session.execute(select(*structure_columns).where(M.StructureModel.paper_id==paper_id)).mappings()]
 users=session.execute(select(M.User.id,M.User.email,M.User.role).where(M.User.id.in_([p.uploaded_by_user_id,p.reviewed_by_user_id]))).mappings()
 out['actors']=[dict(x) for x in users]
 session.rollback()
(run/(label+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
print(json.dumps({'paper':out['paper'],'states':len(out['states']),'records':sum(len(m['records']) for s in out['states'] for m in s['property_modules']),'files':out['files'],'structures':len(out['structures']),'field_sources':len(out['field_sources']),'actors':out['actors'],'history':out['history']},ensure_ascii=False,indent=2,default=str))
