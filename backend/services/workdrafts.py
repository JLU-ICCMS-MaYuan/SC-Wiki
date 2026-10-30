"""工作稿归属、周期与轻量修订；业务写入和修订推进共用事务。"""
from copy import deepcopy
import uuid
from sqlalchemy import select, inspect
from backend import models
from backend.workdraft_models import ScientificWorkDraft
from backend.ingest.field_drafts import fail

def row(session, target, target_id, lock=False):
    if not inspect(session.connection()).has_table(ScientificWorkDraft.__tablename__):
        return None
    query=select(ScientificWorkDraft).where(ScientificWorkDraft.target==target,
        ScientificWorkDraft.target_id==str(target_id))
    return session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)

def cycle(session, target, target_id):
    if target=='upload':
        from backend.ingest.upload_tasks import get_state,authoritative_state
        state=authoritative_state(target_id,session) or get_state(target_id) or {}
        if state.get('paper_id'): fail('draft_already_submitted','草稿已交出')
        return 'upload:'+str(target_id)
    if target=='revision':
        saved=session.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id==target_id))
        if saved is None or saved.submitted_revision: fail('manuscript_handed_off','返修稿已交出')
        return saved.revision_id
    from backend.services.manuscript_handoffs import latest
    state=latest(session,int(target_id))
    return str(state['event_id']) if state else 'legacy'

def require(session, target, target_id, user, expected=None):
    current=row(session,target,target_id)
    if current is None:return None
    if current.owner_id!=user.id:fail('workdraft_claimed','工作稿已由其他审核员接手')
    if current.document_key!=cycle(session,target,target_id):
        fail('workdraft_ended','工作稿周期已结束，请重新打开')
    from backend.services.workdraft_context import epoch
    expected = expected if expected is not None else epoch.get()
    if expected is not None and expected!=current.write_epoch:
        fail('workdraft_ended','此页面属于已结束的工作稿')
    return current

def open_draft(session,target,target_id,user):
    if not inspect(session.connection()).has_table(ScientificWorkDraft.__tablename__):
        fail('workdraft_schema_required','工作稿功能尚未完成数据库迁移')
    if target=='paper':
        session.scalar(select(models.Paper).where(models.Paper.id==int(target_id)).with_for_update())
    from backend.ingest.field_drafts import authorized_draft,draft_version
    from backend.services.workdraft_context import epoch
    token=epoch.set(None)
    try:
        draft,saved=authorized_draft(session,target,target_id,user,lock=True,allow_new_cycle=True)
    finally:epoch.reset(token)
    active=cycle(session,target,target_id)
    current=row(session,target,target_id,True)
    if current is not None and current.document_key==active:
        require(session,target,target_id,user)
        current._paper_header={k:(draft.get('paper') or {}).get(k) for k in ('title','doi','year')}
        return current
    if current is not None:session.delete(current);session.flush()
    if target=='paper':
        if isinstance(saved,models.Paper):
            saved=models.ScientificReviewDraft(paper_id=saved.id,owner_id=user.id,
                base_revision=saved.content_revision,base_fingerprint=draft_version(draft),draft=deepcopy(draft))
            session.add(saved);session.flush()
        else:saved.owner_id=user.id
        if not draft.get('_spectrum_target_id'):
            reference=uuid.uuid4().hex
            draft={**draft,'_spectrum_target_id':reference}
            from backend.ingest.tc_contexts import map_draft
            saved.draft=map_draft(draft,compact=True)
            from backend.services.spectra import copy_to_revision_sync
            copy_to_revision_sync(session,session.get(models.Paper,int(target_id)),reference,preserve_review=True)
    from backend.ingest.tc_contexts import map_draft
    current=ScientificWorkDraft(id=uuid.uuid4().hex,document_key=active,target=target,target_id=str(target_id),
        owner_id=user.id,write_epoch=uuid.uuid4().hex,revision=1,body=map_draft(draft,compact=True) if target=='upload' else {})
    if target=='upload':
        from backend.ingest.upload_tasks import get_state,authoritative_state
        task_state=authoritative_state(target_id,session) or get_state(target_id)
    session.add(current);session.flush()
    if target=='upload':
        from backend.ingest.scientific_evidence import persist_upload
        persist_upload(session,target_id,task_state,draft)
    current._paper_header={k:(draft.get('paper') or {}).get(k) for k in ('title','doi','year')}
    return current

def touch(session,target,target_id,user,body=None,expected=None):
    current=require(session,target,target_id,user,expected)
    if current is None:current=open_draft(session,target,target_id,user)
    if body is not None and target=='upload':
        from backend.ingest.tc_contexts import map_draft
        current.body=map_draft(body,compact=True)
    current.revision+=1;session.flush()
    return current

def _scope_index(session,target,target_id):
    if not inspect(session.connection()).has_table(ScientificWorkDraft.__tablename__):return None
    return session.execute(select(ScientificWorkDraft.owner_id,ScientificWorkDraft.document_key,
        ScientificWorkDraft.write_epoch,ScientificWorkDraft.revision).where(
        ScientificWorkDraft.target==target,ScientificWorkDraft.target_id==str(target_id))).first()

def metadata(session,target,target_id,user):
    current=_scope_index(session,target,target_id)
    if current is None or current.document_key!=cycle(session,target,target_id):
        return dict(revision=None,write_epoch=None)
    if current.owner_id!=user.id:fail('workdraft_claimed','工作稿已由其他审核员接手')
    from backend.services.workdraft_context import epoch
    if epoch.get() is not None and epoch.get()!=current.write_epoch:
        fail('workdraft_ended','此页面属于已结束的工作稿')
    return dict(revision=current.revision,write_epoch=current.write_epoch)


def bump(session,target,target_id):
    current=row(session,target,target_id,True)
    if current is not None:current.revision+=1


def context_token(session,target,target_id):
    current=_scope_index(session,target,target_id)
    if current is not None:
        active=cycle(session,target,target_id)
        return current.write_epoch if current.document_key==active else 'cycle:'+active
    if target=='paper' and str(target_id).isdigit() and inspect(session.connection()).has_table(models.PaperHistoryEvent.__tablename__):
        from backend.services.manuscript_handoffs import latest
        state=latest(session,int(target_id),current_read=True)
        return 'cycle:'+str(state['event_id']) if state else 'cycle:legacy'
    return 'cycle:'+target+':'+str(target_id)


def watch_spectra(session,target,target_id):
    from sqlalchemy import event
    scopes=session.info.setdefault('workdraft_spectrum_scopes',set())
    scopes.add((target,str(target_id)))
    if session.info.get('workdraft_spectrum_watch'):
        return
    session.info['workdraft_spectrum_watch']=True
    def before_commit(db):
        changed=any(isinstance(item,(models.SpectrumCollection,models.SpectrumRun)) for item in [*db.new,*db.dirty,*db.deleted])
        if changed:
            for scope,identity in list(db.info.get('workdraft_spectrum_scopes') or []):
                bump(db,scope,identity)
    def after_commit(db):
        db.info.get('workdraft_spectrum_scopes',set()).clear()
    event.listen(session,'before_commit',before_commit)
    event.listen(session,'after_commit',after_commit)
