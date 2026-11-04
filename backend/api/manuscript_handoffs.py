"""正式交接记录与冻结整稿的只读接口。"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.security import get_current_user
from backend.services import manuscript_handoffs as h

router=APIRouter(prefix='/api/rag/handoffs', tags=['manuscript-handoffs'])


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
    return {'paper_id':paper.id,'events':events[:limit],'state':state,
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
