"""#194：来源读取得到真实内容，科学结论由同一模型流程给出。"""
from copy import deepcopy
import json

from backend.ingest import property_evidence as ev


def case(value=0.03):
    row = {'key': 'spacing', 'item_key': 'spacing', 'field': 'paper.summary', 'kind': 'field',
           'label': '采样间距', 'current_value': value, 'claim': {'value': value},
           'required': True, 'evidences': []}
    chunks = [{'file_id': 'si', 'chunk_index': 0, 'page_start': 2,
               'content': r'Monkhorst-\\mathbf{Pack} spacing 0 . 0 3 ~ \\AA^{-1}.'}]
    return ev.complete_snapshot('upload', 'isolated', [row], chunks, {})


def test_model_locates_format_variant_without_old_matcher(monkeypatch):
    from backend.ingest.model_review import review_fields
    snap = case()
    def model(_, prompt, **kwargs):
        payload = json.loads(prompt)
        source = payload['sources'][0]
        return {'results': [{'key': 'spacing', 'status': 'supported',
            'reason': '原文的分散数字与单位表达采样间距0.03 Å⁻¹。',
            'source_ids': [source['source_id']], 'basis_kind': 'paper_quote'}]}
    monkeypatch.setattr(ev, 'locate_with_reason', lambda *a, **k: (_ for _ in ()).throw(AssertionError('旧文本匹配不得参与')))
    result = review_fields(snap['records'], snap['chunks'], model=model)['spacing']
    checked = ev.checked_result(snap['records'][0], result, snap['chunks'])
    assert checked['status'] == 'supported' and checked['evidences']
    assert checked['human_confirmed'] is False


def test_invalid_reference_is_returned_to_model_and_other_results_survive():
    from backend.ingest.model_review import review_fields
    snap = case()
    other = deepcopy(snap['records'][0]); other.update(key='other', item_key='other', field='paper.key_finding')
    calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt); calls.append(request)
        if len(calls) == 1:
            return {'results': [
                {'key': 'spacing', 'status': 'supported', 'reason': '原文已核实', 'source_ids': [request['sources'][0]['source_id']]},
                {'key': 'other', 'status': 'supported', 'reason': '需要重新定位', 'source_ids': ['invented']}]}
        assert [r['key'] for r in request['records']] == ['other']
        assert request.get('previous_error')
        return {'results': [{'key': 'other', 'status': 'supported', 'reason': '已读取并重新定位正确原文',
                              'source_ids': [request['sources'][0]['source_id']]}]}
    result = review_fields([*snap['records'], other], snap['chunks'], model=model)
    assert len(calls) == 2 and all(r['status'] == 'supported' for r in result.values())


def test_technical_failure_does_not_erase_completed_fields():
    from backend.ingest.model_review import review_fields
    snap = case(); other = deepcopy(snap['records'][0]); other.update(key='other', item_key='other')
    calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt); calls.append(request)
        if len(calls) > 1:
            raise TimeoutError('isolated timeout')
        return {'results': [{'key': 'spacing', 'status': 'supported', 'reason': '已核实原文',
                              'source_ids': [request['sources'][0]['source_id']]}]}
    result = review_fields([*snap['records'], other], snap['chunks'], model=model)
    assert result['spacing']['status'] == 'supported'
    assert result['other']['status'] == 'unchecked' and result['other']['review_error']


def test_read_only_tools_have_no_program_scientific_judgment():
    from backend.ingest.model_review import review_fields
    snap = case(); calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt); calls.append(request)
        assert 'validate_claim' not in request['tools'] and 'check_coverage' not in request['tools']
        if len(calls) == 1:
            return {'action': {'name': 'read_page', 'arguments': {'file_id': 'si', 'page': 2}}}
        source = request['observation']['blocks'][0]['metadata']['source_id']
        return {'results': [{'key': 'spacing', 'status': 'supported', 'reason': '读页后核实数值与单位',
                              'source_ids': [source]}]}
    result = review_fields(snap['records'], snap['chunks'], model=model)
    assert result['spacing']['status'] == 'supported'


def test_original_page_tool_cannot_escape_task_and_has_bounded_retries():
    from backend.ingest.model_review import review_fields
    snap = case(); calls = []
    def model(_, prompt, **kwargs):
        calls.append(json.loads(prompt))
        return {'action': {'name': 'read_original_page', 'arguments': {'file_id': 'outside-task', 'page': 2}}}
    result = review_fields(snap['records'], snap['chunks'], model=model,
                          manifest=[{'file_id': 'si', 'kind': 'pdf'}])['spacing']
    assert len(calls) == 4 and result['review_error'] == 'agent_retry_exhausted'


def test_real_storage_roundtrip_preserves_model_inference_and_source(db_session, monkeypatch):
    from backend.ingest.model_review import review_fields
    from backend.ingest import scientific_evidence as science
    snap = case()
    def model(_, prompt, **kwargs):
        request = json.loads(prompt)
        return {'results': [{'key': 'spacing', 'status': 'supported', 'basis_kind': 'paper_inference',
            'reason': '已结合上下文核实采样间距，保留论文推断身份。',
            'source_ids': [request['sources'][0]['source_id']]}]}
    results = review_fields(snap['records'], snap['chunks'], model=model)
    science.save_results(db_session, snap, results, 1)
    db_session.flush()
    loaded = science.load_results(db_session, snap)
    view = ev.public_snapshot(snap, loaded)['records'][0]
    assert view['status'] == 'supported' and not view.get('human_confirmed')
    assert view['source_kind'] == 'paper_inference' and view['evidences'][0]['file_id'] == 'si'
    assert ev.resolve_results(snap, loaded, 1, None, snap['version'])


def test_unique_system_correction_is_adopted_once_and_manual_content_is_protected(monkeypatch):
    from backend.ingest import model_review
    def rebuild(draft):
        row = {'key': 'field', 'item_key': 'field', 'field': 'paper.year', 'kind': 'field',
               'current_value': draft['paper']['year'], 'claim': {'value': draft['paper']['year']},
               'required': True, 'evidences': [], 'label': '年份'}
        return ev.complete_snapshot('upload', 'isolated', [row],
            [{'file_id': 'main', 'chunk_index': 0, 'content': 'Published in 2012.'}], {})
    calls = []
    def review(rows, chunks, **kwargs):
        calls.append(deepcopy(rows))
        result = {'status': 'unsupported', 'reason': '原文唯一给出2012年',
                  'proposal': {'values': {'': 2012}, 'supported': True, 'unique': True,
                               'final_verified': True, 'evidences': [{'file_id': 'main', 'quote': 'Published in 2012.'}]},
                  'evidences': [{'file_id': 'main', 'quote': 'Published in 2012.'}]}
        return {r['key']: model_review.bind_result(r, result, chunks) for r in rows}
    monkeypatch.setattr(model_review, 'review_fields', review)
    original = {'paper': {'year': 2011}, 'material_states': []}
    fixed, snap, results, _ = model_review.review_draft(original, rebuild)
    assert fixed['paper']['year'] == 2012 and original['paper']['year'] == 2011
    assert results['field']['status'] == 'supported' and len(calls) == 1
    protected, _, results, _ = model_review.review_draft(original, rebuild, protected_keys={'field'})
    assert protected == original and results['field']['status'] == 'unsupported'


def test_same_version_saved_result_never_calls_model_again(monkeypatch):
    from backend.ingest import model_review
    snap = case()
    row = snap['records'][0]
    result = model_review.bind_result(row, {'status': 'supported', 'evidences': [{'file_id': 'si', 'quote': 'Original'}]}, snap['chunks'])
    monkeypatch.setattr(model_review, 'review_fields', lambda *a, **k: (_ for _ in ()).throw(AssertionError('已有通过不得重复核对')))
    _, _, output, report = model_review.review_draft({'paper': {}, 'material_states': []}, lambda _: snap,
                                                   initial_results={row['key']: result})
    assert output[row['key']]['status'] == 'supported' and report['batches'] == 0


def test_partial_response_budget_keeps_successes_without_unbound_tool_name():
    from backend.ingest.model_review import review_fields
    snap = case(); rows = []
    for index in range(20):
        row = deepcopy(snap['records'][0]); row.update(key=f'field-{index}', item_key=f'field-{index}')
        rows.append(row)
    def model(_, prompt, **kwargs):
        request = json.loads(prompt)
        return {'results': [{'key': request['records'][0]['key'], 'status': 'supported', 'reason': '当前字段已查证',
                              'source_ids': [request['sources'][0]['source_id']]}]}
    output = review_fields(rows, snap['chunks'], model=model, max_rounds=20)
    assert sum(r['status'] == 'supported' for r in output.values()) == 13
    assert all(r['status'] == 'supported' or r.get('review_error') for r in output.values())


def test_source_catalog_keeps_chunk_identity_and_removes_only_locator_comments():
    from backend.ingest.model_review import source_catalog
    sources = source_catalog([{'file_id': 'f', 'chunk_index': 21,
        'content': '<!-- block: b -->Original 0 . 0 3 Å^-1.'}])
    assert sources[0]['chunk_index'] == 21 and sources[0]['content'] == 'Original 0 . 0 3 Å^-1.'
    assert not source_catalog([{'file_id': 'attachment', 'role': 'attachment', 'content': 'not paper evidence'}])


def test_verified_native_structure_remains_separate_from_paper_evidence():
    from backend.ingest.model_review import review_fields
    snap = case(); row = snap['records'][0]
    row.update(kind='structure', key='structure', item_key='structure',
               provenance={'verified': True, 'filename': 'source.cif', 'original_text': 'data_native_structure'})
    def model(_, prompt, **kwargs):
        request = json.loads(prompt)
        item = request['human_provided_evidence']['structure']['items'][0]
        assert item['content'] == 'data_native_structure'
        return {'results': [{'key': 'structure', 'status': 'supported', 'reason': '依据实际读取的提交者结构文件核实',
            'source_ids': [], 'supplemental_evidences': [{'sha256': item['sha256'], 'quote': item['content']}]}]}
    result = review_fields([row], snap['chunks'], model=model)['structure']
    assert result['status'] == 'supported' and result['source_kind'] == 'contributor_evidence'
    assert result['evidences'] == [] and result['human_confirmed'] is False


def test_saved_human_decision_is_not_projected_back_to_model_confirmation():
    from backend.ingest.model_review import bind_result
    snap = case(); row = snap['records'][0]
    result = bind_result(row, {'status': 'supported', 'human_confirmed': True,
        'field_decision': {'action': 'approve'}, 'stored_result': True, 'evidences': []}, snap['chunks'])
    assert ev.checked_result(row, result, snap['chunks'])['human_confirmed'] is True


def test_model_pass_cannot_bypass_field_type_validation():
    from backend.ingest.model_review import review_fields
    snap = case(); row = snap['records'][0]
    row.update(current_value='unfinished-number', record_field='value_number',
               field='material_states[0].property_modules[0].records[0].value_number',
               field_schema={'type': 'number', 'nullable': True})
    calls = []
    def model(_, body, **kwargs):
        request = json.loads(body); calls.append(request)
        return {'results': [{'key': 'spacing', 'status': 'supported', 'reason': '原文给出该间距',
            'source_ids': [request['sources'][0]['source_id']],
            **({'final_value': 0.03, 'unique': True} if len(calls) > 1 else {})}]}
    result = review_fields([row], snap['chunks'], model=model)['spacing']
    assert len(calls) == 2 and calls[1]['previous_error']
    assert result['status'] == 'unsupported' and result['proposal']['values'][''] == 0.03


def test_rq_entry_uses_one_model_workflow_and_real_result_storage(sqlite_engine, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from sqlalchemy.orm import sessionmaker
    from backend import database
    from backend import manual_evidence_models, workdraft_models
    from backend.ingest import upload_tasks as tasks, scientific_evidence as science
    from test_upload_extraction_timing import MemoryRedis
    from backend.rag import llm
    database.Base.metadata.create_all(sqlite_engine)
    snap = case(); factory = sessionmaker(sqlite_engine); client = MemoryRedis()
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(tasks, 'redis_client', lambda: client)
    monkeypatch.setattr(tasks, 'load_llm_config', lambda _: SimpleNamespace(model='isolated-model'))
    monkeypatch.setattr(tasks, 'delete_llm_config', lambda _: None)
    @contextmanager
    def lock(_):
        yield
    monkeypatch.setattr(tasks, 'upload_task_lock', lock)
    monkeypatch.setattr(ev, 'upload_snapshot', lambda *a, **k: deepcopy(snap))
    monkeypatch.setattr(ev, 'evaluate_batch', lambda *a, **k: (_ for _ in ()).throw(AssertionError('旧核对链不得调用')))
    calls = []
    def model(_, body, **kwargs):
        request = json.loads(body); calls.append(request)
        return {'results': [{'key': 'spacing', 'status': 'supported', 'reason': '已核实原页对应的采样间距',
                              'source_ids': [request['sources'][0]['source_id']]}]}
    monkeypatch.setattr(llm, 'complete_json', model)
    job_id = 'a' * 32
    job = {'id': job_id, 'owner': 1, 'status': 'queued', 'snapshot': snap, 'cached': {},
           'purpose': 'submit', 'review_started_at': '2026-11-01T00:00:00+00:00'}
    client.set(ev.task_key(job_id), json.dumps(job))
    ev.run_evidence_job(job_id)
    finished = json.loads(client.get(ev.task_key(job_id)))
    assert finished['status'] == 'completed' and len(calls) == 1
    with factory() as session:
        loaded = science.load_results(session, snap)
    assert loaded['spacing']['status'] == 'supported'
    assert loaded['spacing']['review_started_at'] == job['review_started_at']
