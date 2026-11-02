"""上传删除遵守#35/#185：清理当前工作稿，保留共享来源目录。"""
from sqlalchemy import select
from backend.ingest.scientific_evidence import delete_target
from backend.workdraft_models import ScientificWorkDraft, ScientificFieldSourceUse, ScientificSourceItem


def test_delete_upload_removes_working_form_and_uses_but_keeps_source_catalog(db_session):
    task = 'a' * 32
    db_session.add(ScientificSourceItem(id='s' * 64, namespace='original', payload={'quote': 'Retained source'}))
    db_session.add(ScientificWorkDraft(id='work', document_key='doc', target='upload', target_id=task,
        owner_id=1, write_epoch='b' * 32, revision=1, body={'paper': {'title': 'Old draft'}}))
    db_session.flush()
    db_session.add(ScientificFieldSourceUse(work_key='upload:' + task, item_key='i' * 64,
        source_id='s' * 64, role='direct', binding_json={}))
    db_session.flush()
    delete_target(db_session, 'upload', task)
    assert db_session.scalar(select(ScientificWorkDraft).where(ScientificWorkDraft.target_id == task)) is None
    assert db_session.scalar(select(ScientificFieldSourceUse).where(ScientificFieldSourceUse.work_key == 'upload:' + task)) is None
    assert db_session.get(ScientificSourceItem, 's' * 64) is not None
