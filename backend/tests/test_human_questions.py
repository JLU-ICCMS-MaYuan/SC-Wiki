from copy import deepcopy
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.database import Base
from backend import models

@pytest.fixture
def database(tmp_path, monkeypatch):
    from backend.ingest import manual_evidence
    from backend import workdraft_models
    monkeypatch.setattr(manual_evidence.settings, 'sc_wiki_data_dir', tmp_path)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

def state():
    return {'task_id': 'task', 'user_id': 2, 'status': 'summarizing',
        'human_questions_policy': {'version': 1, 'enabled': True},
        'files': [{'file_id': 'main', 'role': 'main', 'sha256': 'a'*64}]}

def route(source='b'):
    return {'kind': 'human_required', 'requires_human': True, 'reason_code': 'source_conflict',
        'reason': '真实物相冲突', 'checked_context': '已查原页',
        'target_refs': [{'item_key': 'field', 'state_key': 's', 'field': 'material_states[0].reported_space_group_symbol', 'content_hash': 'v', 'source_hash': 'src'}],
        'source_refs': [{'file_id': 'main', 'block_id': 'a', 'content': 'P63/mmc'},
                        {'file_id': 'si', 'block_id': source, 'content': 'Cc'}]}

def test_first_question_is_durable_before_any_scientific_draft_and_dedup_is_not_title(database):
    from backend.ingest.human_questions import append_question, public_queue
    with Session(database) as db, db.begin():
        first = append_question(db, state(), route(), recommendation='保留当前值及冲突依据')
        same = append_question(db, state(), {**route(), 'reason': '换一种措辞的相同冲突'}, recommendation='查证')
        other = append_question(db, state(), route('another-source'), recommendation='另一冲突')
        assert first['question_id'] == same['question_id'] != other['question_id']
    with Session(database) as db:
        saved = db.get(models.ScientificUploadDraft, 'task')
        assert len(saved.state['human_questions']['questions']) == 2
        public = public_queue(saved.state)
        assert public['pending_count'] == 2 and len(public['questions'][0]['options']) >= 3
        assert not saved.state.get('paper_id') and not saved.draft.get('material_states')

def test_answer_is_explicit_idempotent_versioned_and_not_approval(database):
    from backend.ingest.human_questions import append_question, answer_question, public_queue
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='保留当前物相并说明冲突')
        assert q['state'] == 'waiting'
        payload = {'answer_id': 'answer', 'prompt_revision': q['prompt_revision'], 'target_token': q['target_token'],
            'expected_queue_revision': 1, 'choice_id': 'manual', 'manual_text': '采用Cc', 'reason': '结合附件结构裁定'}
        first = answer_question(db, state(), 2, q['question_id'], payload)
        second = answer_question(db, state(), 2, q['question_id'], payload)
        assert first == second and first['accepted'] and first['state'] == 'answer_received'
        saved = db.get(models.ScientificUploadDraft, 'task')
        assert not saved.draft.get('field_decision') and saved.state['human_questions']['revision'] == 2
        with pytest.raises(ValueError): answer_question(db, state(), 2, q['question_id'], {**payload, 'manual_text': '不同答案'})

def test_stale_answer_is_retained_without_application_and_owner_is_enforced(database):
    from backend.ingest.human_questions import append_question, answer_question
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='保留')
        payload = {'answer_id': 'a', 'prompt_revision': 1, 'target_token': q['target_token'],
            'expected_queue_revision': 1, 'choice_id': 'manual', 'manual_text': '我的输入', 'reason': '理由'}
        with pytest.raises(PermissionError): answer_question(db, state(), 3, q['question_id'], payload)
        result = answer_question(db, state(), 2, q['question_id'], payload, current_targets={'field': {'content_hash': 'changed', 'source_hash': 'src'}})
        assert not result['accepted'] and result['state'] == 'stale'
        question = db.get(models.ScientificUploadDraft, 'task').state['human_questions']['questions'][0]
        assert question['rejected_answer']['manual_text'] == '我的输入'

def test_investigate_is_not_a_scientific_decision_and_unrelated_append_does_not_lose_answer(database):
    from backend.ingest.human_questions import append_question, answer_question
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='保留')
        append_question(db, state(), route('c'), recommendation='另一题')
        result = answer_question(db, state(), 2, q['question_id'], {'answer_id': 'a', 'prompt_revision': 1,
            'target_token': q['target_token'], 'expected_queue_revision': 1, 'choice_id': 'investigate'})
        assert result['state'] == 'investigating' and result['accepted']


def test_sql_queue_survives_cache_loss_and_stale_progress_cannot_overwrite_answer(database, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend import database as database_module
    from backend.ingest import upload_tasks
    from backend.ingest.human_questions import append_question, answer_question, merge_state, read_public
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='保留来源')
        before = deepcopy(db.get(models.ScientificUploadDraft, 'task').state)
        answer_question(db, state(), 2, q['question_id'], {'answer_id': 'a', 'prompt_revision': 1,
            'target_token': q['target_token'], 'choice_id': 'recommended', 'expected_queue_revision': 1})
    monkeypatch.setattr(database_module, 'SessionLocal', sessionmaker(bind=database))
    # 从真实SQL新会话重读，不依赖Redis中是否还有镜像。
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _: state())
    restored = read_public('task', 2)
    assert restored['questions'][0]['state'] == 'answer_received'
    with Session(database) as db:
        latest = db.get(models.ScientificUploadDraft, 'task').state
        merged = merge_state(before, latest)
        assert merged['human_questions']['revision'] == 2
        assert merged['human_questions']['questions'][0]['answers'][0]['actor_user_id'] == 2


def test_failed_transaction_does_not_claim_an_answer_was_saved(database):
    from backend.ingest.human_questions import append_question, answer_question
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='保留')
    with pytest.raises(OSError), Session(database) as db, db.begin():
        answer_question(db, state(), 2, q['question_id'], {'answer_id': 'a', 'prompt_revision': 1,
            'target_token': q['target_token'], 'choice_id': 'recommended', 'expected_queue_revision': 1})
        raise OSError('isolated commit failed')
    with Session(database) as db:
        assert db.get(models.ScientificUploadDraft, 'task').state['human_questions']['questions'][0]['state'] == 'waiting'


def test_answer_direction_is_saved_as_field_specific_human_material_without_approval(database):
    from backend.ingest.human_questions import append_question, answer_question, persist_directions
    from backend.ingest.manual_evidence import read_field
    from backend.ingest import manual_evidence as manual
    row = {'key': 'field', 'item_key': 'field', 'field': 'paper.summary', 'content_hash': 'v',
           'source_hash': 'src', 'current_value': 'Original current summary', 'required': True}
    snapshot = {'target': 'upload', 'target_id': 'task', 'records': [row]}
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='采用附件归属并保留冲突')
        answer_question(db, state(), 2, q['question_id'], {'answer_id': 'a', 'prompt_revision': 1,
            'target_token': q['target_token'], 'choice_id': 'recommended', 'expected_queue_revision': 1})
        saved = db.get(models.ScientificUploadDraft, 'task')
        assert persist_directions(db, saved.state, snapshot, {'field'}) == {'field'}
        first = read_field(db, snapshot, snapshot, 'field', include_history=False)
        assert first['items'][0]['kind'] == 'text_file'
        field = db.get(manual.ScientificManualEvidence, first['id'])
        raw = manual._read_file(field.id, field.items[0]).decode()
        assert '采用附件归属并保留冲突' in raw
        from backend.ingest.human_questions import answer_context
        assert raw == answer_context(saved.state, [row])['field']['items'][0]['content']
        assert first['items'][0]['submitted_by_user_id'] == 2
        persist_directions(db, saved.state, snapshot, {'field'})
        second = read_field(db, snapshot, snapshot, 'field', include_history=False)
        assert first == second
        assert row['current_value'] == 'Original current summary' and not row.get('field_decision')


def test_default_is_enabled_and_queue_summary_does_not_embed_full_question_text():
    from backend.rag.config import RagSettings
    from backend.ingest.upload_contracts import public_task_state, apply_state_changes, new_extraction_timing
    assert RagSettings(_env_file=None).upload_human_questions_enabled
    value = {**state(), 'extraction_timing': new_extraction_timing()}
    running = apply_state_changes(value, now=100, status='extracting')
    paused = apply_state_changes(running, now=110, status='pausing', pause_reason='human_questions')
    assert paused['extraction_timing']['elapsed_seconds'] == 10
    paused = apply_state_changes(paused, now=500, status='paused')
    assert paused['extraction_timing']['elapsed_seconds'] == 10
    public = public_task_state(paused)
    assert public['human_questions_summary']['queue_revision'] == 0
    assert 'human_questions' not in public and public['pause_reason'] == 'human_questions'


def test_question_answer_never_rewrites_existing_manual_text_origin_or_author(database):
    from backend.ingest.human_questions import append_question, answer_question, persist_directions
    from backend.ingest import manual_evidence as manual
    row = {'key': 'field', 'item_key': 'field', 'field': 'paper.summary', 'content_hash': 'v',
           'source_hash': 'src', 'current_value': 'Existing value', 'required': True}
    snapshot = {'target': 'upload', 'target_id': 'task', 'records': [row]}
    with Session(database) as db, db.begin():
        q = append_question(db, state(), route(), recommendation='本次处理方向')
        answer_question(db, state(), 2, q['question_id'], {'answer_id': 'a', 'prompt_revision': 1,
            'target_token': q['target_token'], 'choice_id': 'recommended', 'expected_queue_revision': 1})
        manual.save_explanation(db, snapshot, snapshot, 'field', 2, reason='原人工理由', no_evidence_reason='',
            text_items=[{'text': '原人工资料，不能被本次回答改写', 'source_description': '原贡献者说明'}])
        prior = manual.read_field(db, snapshot, snapshot, 'field', include_history=False)
        assert persist_directions(db, db.get(models.ScientificUploadDraft, 'task').state, snapshot, {'field'}) == {'field'}
        after = manual.read_field(db, snapshot, snapshot, 'field', include_history=False)
        original = next(item for item in after['items'] if item['id'] == prior['items'][0]['id'])
        assert original == prior['items'][0]
        assert after['reason'] == prior['reason']
