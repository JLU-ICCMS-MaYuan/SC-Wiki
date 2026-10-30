"""正式交接记录与冻结整稿的只读接口。"""
from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend import models
from backend.database import get_db
from backend.security import get_current_user
from backend.services import manuscript_handoffs as h

router=APIRouter(prefix='/api/rag/handoffs', tags=['manuscript-handoffs'])


class ReturnRevision(BaseModel):
    operation_id:str=Field(min_length=1,max_length=64)
    expected_snapshot_id:str | None=None
    comment:str=Field(default='',max_length=4000)


@router.post('/{paper_id}/return')
def return_to_author(paper_id:int,body:ReturnRevision,user=Depends(get_current_user),session:Session=Depends(get_db,use_cache=False)):
    try:
        paper=session.scalar(select(models.Paper).where(models.Paper.id==paper_id).with_for_update())
        h.readable(paper,user)
        if user.role not in {'admin','superadmin'} or user.id==paper.uploaded_by_user_id:
            h.error('handoff_forbidden','须由其他合法审核人员正式交还',403)
        done=session.scalar(select(models.PaperHistoryEvent).where(models.PaperHistoryEvent.operation_id==body.operation_id))
        if done:
            if done.paper_id!=paper_id or done.actor_user_id!=user.id or (done.classification_snapshot or {}).get('handoff',{}).get('action')!='return_revision':
                h.error('handoff_operation_conflict','该操作身份属于其他交接')
            return {'ok':True,'paper_id':paper_id,'handoff':(done.classification_snapshot or {}).get('handoff')}
        state=h.latest(session,paper_id,current_read=True)
        if state and body.expected_snapshot_id!=state['snapshot_id']:
            h.error('handoff_stale','交接版本已变化，请刷新后重试')
        if state is None and session.get(models.ScientificReviewDraft,paper_id) is not None:
            h.error('workdraft_claimed','已有尚未交出的存量暂存稿，已保留；请先完成当前稿件处理')
        if state and state['holder']!='published':
            h.require_writer(session,paper,user)
        from backend.ingest import property_evidence as ev,scientific_evidence as science
        from backend.services.paper_revisions import current_draft
        if state and state['holder']=='review':
            content=h.current_review_content(session,paper,user)
        else:
            snap=ev.paper_snapshot(session,paper_id,0,'',check_access=False)
            cached=science.load_results(session,snap,user.id,include_stale=True)
            content=h.capture(session,paper,current_draft(session,paper),snap,ev.public_snapshot(snap,cached)['records'])
        result=h.record_handoff(session,paper,user,action='return_revision',holder='author',
            operation_id=body.operation_id,comment=body.comment,initial=state is None or state['holder']=='published',**content)
        if paper.review_status!='approved':
            paper.review_status='rejected'
            paper.review_comment=body.comment
        h.author_working_copy(session,paper,paper.uploaded_by_user_id,content['draft'],content['records'])
        staged=session.get(models.ScientificReviewDraft,paper.id)
        if staged is not None:session.delete(staged)
        session.commit()
        return {'ok':True,'paper_id':paper_id,'handoff':result}
    except Exception:
        session.rollback()
        raise


def resolve(session, target, target_id, user):
    if target=='upload':
        from backend.ingest.upload_tasks import get_state
        state=get_state(target_id) or {}
        if state.get('user_id')!=user.id:
            h.error('handoff_forbidden','无权查看这份稿件',403)
        paper_id=state.get('paper_id')
        if not paper_id:return None
    elif target=='revision':
        paper_id=session.scalar(select(models.PaperRevisionDraft.paper_id).where(
            models.PaperRevisionDraft.revision_id==target_id))
    else:
        if not target_id.isdigit():h.error('paper_not_found','论文不存在',404)
        paper_id=int(target_id)
    paper=session.get(models.Paper,paper_id) if paper_id else None
    h.readable(paper,user)
    return paper


@router.get('')
def list_handoffs(target:Literal['upload','paper','revision'], target_id:str,
                  limit:int=Query(default=20,ge=1,le=100),offset:int=Query(default=0,ge=0),
                  user=Depends(get_current_user), session:Session=Depends(get_db,use_cache=False)):
    paper=resolve(session,target,target_id,user)
    if paper is None:return {'paper_id':None,'events':[],'state':None}
    events=h.event_headers(session,paper.id,limit=limit+1,offset=offset,descending=True)
    state=h.latest(session,paper.id)
    can_return=bool(user.role in {'admin','superadmin'} and user.id!=paper.uploaded_by_user_id and
        (state and state['holder']=='published' or state is None and paper.review_status=='approved'
         and session.get(models.ScientificReviewDraft,paper.id) is None))
    return {'paper_id':paper.id,'events':events[:limit],'state':state,'can_return':can_return,
            'has_more':len(events)>limit,'offset':offset,'legacy_public':state is None and paper.review_status=='approved'}


@router.get('/{paper_id}/snapshots/{snapshot_id}')
def read_snapshot(paper_id:int,snapshot_id:str,event_id:int | None=None,user=Depends(get_current_user),session:Session=Depends(get_db,use_cache=False)):
    result=h.public_snapshot(session,session.get(models.Paper,paper_id),user,snapshot_id)
    header=next((event for event in h.event_headers(session,paper_id) if event['snapshot_id']==snapshot_id
        and (event_id is None or event['event_id']==event_id)),None)
    if header is None:h.error('handoff_missing','该交接与快照不对应',404)
    return {**result,'handoff':header}


@router.get('/{paper_id}/snapshots/{snapshot_id}/files/{file_id}')
def read_file(paper_id:int,snapshot_id:str,file_id:str,user=Depends(get_current_user),session:Session=Depends(get_db,use_cache=False)):
    paper=session.get(models.Paper,paper_id);h.readable(paper,user)
    row=h.snapshot_event(session,paper_id,snapshot_id)
    files=row.classification_snapshot['manuscript_snapshot'].get('files') or []
    source=next((f for f in files if str(f['file_id'])==file_id),None)
    if source is None:h.error('snapshot_source_missing','该快照没有此依据文件',404)
    from backend.storage.paths import resolve_file
    path=resolve_file(source['stored_path'],size=source['size'],sha256=source['sha256'],
                      media_type=source['media_type'],namespace=snapshot_id)
    return FileResponse(path,media_type=source['media_type'],filename=source.get('original_filename'))
