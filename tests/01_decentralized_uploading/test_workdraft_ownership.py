"""真实SQL往返验证领取、私稿隔离及跨交接周期的旧请求拒写。"""
from copy import deepcopy
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend import models
from backend.services import manuscript_handoffs as h, workdrafts as w
from backend.ingest.field_drafts import authorized_draft,save_fields
from backend.ingest.field_sources import compact,expand

@pytest.fixture
def context(sqlite_engine):
    with Session(sqlite_engine) as session:
        people=[]
        for i,role in enumerate(['user','admin','superadmin'],1):
            user=models.User(id=i,username='u'+str(i),email=f'u{i}@isolated.invalid',real_name='隔离用户',
                role=role,password_hash='isolated',is_approved=True)
            session.add(user);people.append(user)
        paper=models.Paper(title='已交出',year=2026,uploaded_by_user_id=1,review_status='pending')
        session.add(paper);session.flush()
        draft={'paper':{'title':'已交出','year':2026},'material_states':[]}
        h.record_handoff(session,paper,people[0],action='submit',operation_id='first',draft=draft,records=[],initial=True)
        session.commit()
        yield session,paper,people

def test_first_reviewer_claims_and_other_reviewers_cannot_read_private_work(context):
    session,paper,(author,reviewer,other)=context
    lease=w.open_draft(session,'paper',str(paper.id),reviewer);session.commit()
    result=save_fields(session,'paper',str(paper.id),reviewer,lease.write_epoch+':old-content',
        [{'path':['paper','title'],'before':'已交出','value':'尚未交出私稿'}])
    session.commit()
    assert authorized_draft(session,'paper',str(paper.id),reviewer)[0]['paper']['title']=='尚未交出私稿'
    with pytest.raises(HTTPException):authorized_draft(session,'paper',str(paper.id),other)
    with pytest.raises(HTTPException):w.open_draft(session,'paper',str(paper.id),other)
    assert h.public_snapshot(session,paper,other,h.latest(session,paper.id)['snapshot_id'])['content']['draft']['paper']['title']=='已交出'
    assert result['changed']

def test_same_reviewer_next_cycle_rejects_old_page_epoch(context):
    session,paper,(author,reviewer,other)=context
    old=w.open_draft(session,'paper',str(paper.id),reviewer).write_epoch
    draft,staged=authorized_draft(session,'paper',str(paper.id),reviewer)
    h.record_handoff(session,paper,reviewer,action='return',holder='author',operation_id='back',draft=draft,records=[])
    session.delete(staged);session.flush()
    h.record_handoff(session,paper,author,action='submit',holder='review',operation_id='again',draft=draft,records=[])
    new=w.open_draft(session,'paper',str(paper.id),reviewer).write_epoch
    assert new!=old
    with pytest.raises(HTTPException) as rejected:
        save_fields(session,'paper',str(paper.id),reviewer,old+':same-values',
            [{'path':['paper','title'],'before':'已交出','value':'旧页面迟到覆盖'}])
    assert rejected.value.detail['code']=='workdraft_ended'

def test_source_catalog_deduplicates_shared_quote_and_keeps_per_field_binding(context):
    session,_,_=context
    from backend.workdraft_models import ScientificSourceItem,ScientificFieldSourceUse
    from sqlalchemy import select,func
    snapshot={'target':'upload','target_id':'isolated','_source_digest':'s'}
    result={'evidences':[{'file_id':'main','quote':'Same source','field_path':'payload.parameters.lambda_ep'}]}
    a=compact(session,snapshot,{'item_key':'a','source_hash':'sa'},result)
    result['evidences'][0]['field_path']='payload.calculation_conditions.k_grid'
    b=compact(session,snapshot,{'item_key':'b','source_hash':'sb'},result)
    session.flush()
    assert session.scalar(select(func.count()).select_from(ScientificSourceItem))==1
    assert session.scalar(select(func.count()).select_from(ScientificFieldSourceUse))==2
    assert expand(session,a)['evidences'][0]['field_path']=='payload.parameters.lambda_ep'
    assert expand(session,b)==result
    c=compact(session,snapshot,{'item_key':'c','source_hash':'sc','record_group_key':'common'},{
        'evidences':[{'file_id':'main','quote':'Same source'},{'file_id':'main','quote':'Unique source for c'}]})
    assert [entry['quote'] for entry in expand(session,c)['evidences']]==['Same source','Unique source for c']
    source_id=a['evidences'][0]['source_ref']
    compact(session,snapshot,{'item_key':'a','source_hash':'sa'},{'evidences':[{'file_id':'main','quote':'New source'}]})
    assert session.get(ScientificSourceItem,source_id).payload['quote']=='Same source'

def test_multiple_states_methods_and_points_keep_source_ownership_after_reorder(context):
    session,_,_=context
    from backend.workdraft_models import ScientificFieldSourceUse
    from backend.ingest.scientific_evidence import item_identity
    from sqlalchemy import select
    snapshot={'target':'upload','target_id':'identity-matrix','_source_digest':'same-source'}
    expected={}
    for state in ['s1','s2']:
      for method in ['eliashberg','allen_dynes']:
        for point in ['p1','p2']:
          for field in ['tc','mu']:
            key=item_identity(state,method,point,field)
            binding={'scope':{'state_key':state,'method_key':method,'point_key':point},'field_path':field}
            value={'evidences':[{'file_id':'main','quote':'Shared table',**binding}]}
            expected[key]=value
            compact(session,snapshot,{'item_key':key,'source_hash':'s'},value)
    session.flush()
    rows=list(session.scalars(select(ScientificFieldSourceUse).where(ScientificFieldSourceUse.work_key=='upload:identity-matrix')))
    assert len(rows)==16
    for row in rows:
        scope=row.binding_json['bindings'][0]['scope']
        if scope['state_key']=='s1' and scope['point_key']=='p1':session.delete(row)
    session.flush()
    rows=list(session.scalars(select(ScientificFieldSourceUse).where(ScientificFieldSourceUse.work_key=='upload:identity-matrix')))
    assert len(rows)==12
    # 删除首点与显示重排不会改变剩余点的稳定身份和依据归属。
    for row in reversed(rows):
        value=expand(session,{'evidences':[{'source_ref':row.source_id,'binding':row.binding_json['bindings'][0]}]})
        assert value==expected[row.item_key]
