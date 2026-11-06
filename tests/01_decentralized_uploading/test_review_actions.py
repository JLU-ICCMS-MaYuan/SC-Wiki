"""#100 新决定必须显式；历史误转交仅恢复原属主，不开放抢占。"""
from copy import deepcopy
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from test_workdraft_ownership import context
from backend import models
from backend.api.evidence import FieldReviewCommit
from backend.services import manuscript_handoffs as h,workdrafts as w
from backend.ingest.field_drafts import authorized_draft,save_fields

@pytest.mark.parametrize("status",["pending","",None])
def test_no_pending_or_missing_formal_review_action(status):
    with pytest.raises(ValidationError):
        FieldReviewCommit(paper_id=1,**({"status":status} if status is not None else {}))

def test_pending_cannot_create_handoff_even_through_service(context):
    session,paper,(author,reviewer,other)=context
    w.open_draft(session,"paper",str(paper.id),reviewer)
    count=session.scalar(select(func.count()).select_from(models.PaperHistoryEvent))
    with pytest.raises(HTTPException):
        h.review_handoff(session,paper,reviewer,status="pending",operation_id="forbidden-pending")
    assert session.scalar(select(func.count()).select_from(models.PaperHistoryEvent))==count
    assert authorized_draft(session,"paper",str(paper.id),reviewer)

def test_legacy_forward_only_original_claimant_can_resume_with_new_epoch(context):
    session,paper,(author,reviewer,other)=context
    old=w.open_draft(session,"paper",str(paper.id),reviewer).write_epoch
    draft,staged=authorized_draft(session,"paper",str(paper.id),reviewer)
    before=deepcopy(staged.draft)
    # 只模拟已经存在的旧记录，不经新审核动作创建forward。
    previous={k:v for k,v in h.latest(session,paper.id).items() if k not in {"event_id","occurred_at","actor_user_id","actor_name"}}
    event=models.PaperHistoryEvent(paper_id=paper.id,paper_revision=1,event_type="reviewed",
        actor_user_id=reviewer.id,review_status="pending",review_comment="通过",
        classification_snapshot={"handoff":{**previous,"action":"forward","holder":"review"}},
        operation_id="old-forward")
    session.add(event);session.commit()
    count=session.scalar(select(func.count()).select_from(models.PaperHistoryEvent))
    with pytest.raises(HTTPException):w.open_draft(session,"paper",str(paper.id),other)
    lease=w.open_draft(session,"paper",str(paper.id),reviewer);session.commit()
    assert lease.write_epoch!=old
    assert authorized_draft(session,"paper",str(paper.id),reviewer)[0]==before
    assert session.scalar(select(func.count()).select_from(models.PaperHistoryEvent))==count
    with pytest.raises(HTTPException):
        save_fields(session,"paper",str(paper.id),reviewer,old+":old",
            [{"path":["paper","title"],"before":"已交出","value":"旧页面迟到"}])
    with pytest.raises(HTTPException):h.require_writer(session,paper,other)
