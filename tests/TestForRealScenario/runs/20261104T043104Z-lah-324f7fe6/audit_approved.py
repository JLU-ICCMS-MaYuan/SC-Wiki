"""只读正式图、冻结交接与原文件，按真实数据所有权核验。"""
from pathlib import Path
from collections import Counter
import sys,json,copy
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv('.env')
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from sqlalchemy import select,event
from backend.database import SessionLocal
from backend import models as M
from backend.workdraft_models import ScientificSourceItem
from backend.ingest.tc_contexts import expand_module
from backend.ingest.field_sources import expand
r=Path(__file__).resolve().parent
formal=json.loads((r/'phase4-after-502.json').read_text())
draft=json.loads((r/'phase4-before-approval.json').read_text())['admin']['draft']
expected=json.loads((r/'source-review/expected-table-s1.json').read_text())
want=[];got=[];original={};observed={}
for row in expected['rows']:
 for i,c in enumerate(expected['columns']):want.append([row['material'],row['pressure_gpa'],c['method_raw'],c['mu_star'],row['tc_values'][i],row['lambda_ep'],row['omega_log_k']])
for s in draft['material_states']:
 for m in s.get('property_modules',[]):
  for p in expand_module(m).get('records',[]):original[p['record_key']]={'state_key':s['state_key'],'record':p}
for s in formal['states']:
 for m in s['property_modules']:
  for p in m['records']:
   observed[p['record_key']]={'state_key':s['state_key'],'record':p}
   if p.get('record_type')!='predicted_tc' or (s['material'],float(s['pressure_value_gpa'] or -1))not in{(x[0],x[1])for x in want}:continue
   z=p['payload']['parameters'];g=p['payload'].get('tc_group')or{};raw=(p.get('method_raw')or'')+' '+(g.get('method_name')or'');name='McMillan'if p['method_code']=='mcmillan'else'Eliashberg'if'eliashberg'in raw.lower()else raw
   got.append([s['material'],float(s['pressure_value_gpa']),name,z.get('mu_star'),float(p.get('value_number')),z.get('lambda_ep'),z.get('omega_log')])
keys=['record_type','property_code','method_code','method_raw','value_kind','unit_raw','value_raw','value_text','value_boolean']
record_problems=[]
for key,old in original.items():
 now=observed.get(key)
 if now is None or now['state_key']!=old['state_key']:record_problems.append([key,'归属或身份']);continue
 a=old['record'];b=now['record']
 for field in keys:
  if a.get(field)!=b.get(field):record_problems.append([key,field,a.get(field),b.get(field)])
 for field in ['value_number','value_min','value_max']:
  av,bv=a.get(field),b.get(field)
  if (av is None)!=(bv is None)or av is not None and Decimal(str(av))!=Decimal(str(bv)):record_problems.append([key,field,av,bv])
 for field in ['parameters','calculation_conditions','tc_group']:
  if a.get('payload',{}).get(field)!=b.get('payload',{}).get(field):record_problems.append([key,'payload.'+field,a.get('payload',{}).get(field),b.get('payload',{}).get(field)])
required_problems=[x['field']for x in formal['field_sources']if x['result'].get('required')and(x['result'].get('stale')or x['result'].get('status')in['unchecked','uncertain','unsupported'])]
with SessionLocal()as s:
 def ro(c,cur,st,p,ctx,m):
  if not st.lstrip().upper().startswith(('SELECT','SHOW')):raise RuntimeError('禁止写')
 event.listen(s.get_bind(),'before_cursor_execute',ro)
 events=[s.get(M.PaperHistoryEvent,i)for i in s.scalars(select(M.PaperHistoryEvent.id).where(M.PaperHistoryEvent.paper_id==1429).order_by(M.PaperHistoryEvent.id))]
 snapshots=[{'event_id':e.id,'operation_id':e.operation_id,'actor_id':e.actor_user_id,'classification_snapshot':e.classification_snapshot}for e in events]
 latest=snapshots[-1]['classification_snapshot']['manuscript_snapshot']
 frozen=expand(s,latest)
 sources=[expand(s,x['result'])for x in formal['field_sources']]
 pre=expand(s,next(x['classification_snapshot']['manuscript_snapshot'] for x in snapshots if x['event_id']==431))
 previous={x['item_key']:x for x in pre['records']}
 citation_comparisons=[];citation_changes=[]
 for row in sources:
  old=previous.get(row.get('materialized_from'))
  if old is None:continue
  citation_comparisons.append(row['field'])
  if old.get('evidences',[])!=row.get('evidences',[]):citation_changes.append({'field':row['field'],'before':old.get('evidences',[]),'after':row.get('evidences',[])})
 (r/'final-citation-transfer-audit.json').write_text(json.dumps({'compared':len(citation_comparisons),'changes':citation_changes},ensure_ascii=False,indent=2))
 s.rollback()
(r/'final-frozen-snapshots.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2,default=str))
(r/'final-expanded-sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2,default=str))
structures={x['structure_hash']:x['structure_text']for x in formal['structures']}
expected_structures={s['structure']['structure_hash']:s['structure']['structure_text']for s in draft['material_states']if s.get('structure')}
manual_title=[x for x in frozen.get('manual',[])if'high-Tc'in x.get('reason','')]
checks={'approved':formal['paper']['review_status']=='approved'and formal['paper']['approved_revision']==formal['paper']['content_revision'],'title_correct':formal['paper']['title']==draft['paper']['title'],'table_s1_28_matches':Counter(map(tuple,want))==Counter(map(tuple,got)),'all_32_records_retained':set(original)==set(observed)and not record_problems,'three_structures_exact':structures==expected_structures,'required_current_checks_valid':not required_problems,'manual_title_reason_retained':bool(manual_title),'pdf_roles_hashes_correct':len(formal['files'])==2 and all(x['sha256']==x['readback_sha256']for x in formal['files']),'four_handoffs':[x['handoff']['action']for x in formal['history']if x.get('handoff')]==['submit','return','submit','approve'],'sources_resolved':len(sources)==len(formal['field_sources']),'selected_citations_preserved':bool(citation_comparisons)and not citation_changes}
out={'paper':formal['paper'],'checks':checks,'record_problems':record_problems,'required_problems':required_problems,'table_rows':got,'manual_title':manual_title,'counts':{'states':len(formal['states']),'records':len(observed),'structures':len(structures),'formal_field_sources':len(sources),'handoffs':sum(bool(x['classification_snapshot'].get('handoff'))for x in snapshots)},'scope':'真实SQL正式图、当前来源、冻结快照及文件；未写数据库。'}
(r/'final-acceptance-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str));print(json.dumps({'checks':checks,'counts':out['counts'],'record_problems':record_problems},ensure_ascii=False)[:5000]);assert all(checks.values())
