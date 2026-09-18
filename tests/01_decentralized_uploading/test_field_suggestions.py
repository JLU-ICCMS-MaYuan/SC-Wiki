"""全字段建议的依据、空项与权限边界；不使用模型结果代替服务端验证。"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from backend.ingest import scientific_evidence as science, property_evidence as ev, evidence_proposals as proposals
from backend.rag.scientific_sources import source_chunk


def snapshot(target='upload', value=''):
    record = dict(key='summary', item_key='summary', field='paper.summary', kind='field', label='总结',
                  current_value=value, claim={'value': value}, required=bool(value), evidences=[])
    return ev.complete_snapshot(target, '1', [record], [dict(file_id='main', chunk_index=0, content='Tin is metallic.')], {})


def suggestion(kind='general_knowledge', **extra):
    return dict(values={'': 'Electron-phonon coupling is plausible.'}, basis_kind=kind,
                explanation='依据一般金属超导知识；本文没有直接报告机制。', supported=True, evidences=[], **extra)


def test_catalog_contains_empty_bibliography_without_submission_gate():
    rows = science.field_records('paper', 'paper', {'title': 'Tin'}, science.PAPER_FIELDS)
    by_field = {r['field']: r for r in rows}
    assert 'paper.title' in by_field and 'paper.authors' in by_field and 'paper.summary' in by_field
    assert by_field['paper.summary']['required'] is False
    # 浏览书目信息不强制引入新的科学批准门禁。
    assert by_field['paper.title']['required'] is False
    snap = ev.complete_snapshot('upload', '1', rows, [], {})
    assert not ev.public_snapshot(snap, {})['needs_check']
    assert len(ev.resolve_results(snap, {}, 1, None, snap['version'])) == len(rows)


def test_general_knowledge_suggestion_is_typed_and_never_direct_support():
    snap = snapshot()
    candidate = proposals.checked_proposal(snap['records'][0], suggestion(), snap['chunks'])
    assert candidate is not None
    assert candidate['basis_kind'] == 'general_knowledge'
    assert candidate['explanation'] and candidate['supported'] is False
    assert candidate['evidences'] == []


def test_inference_requires_real_basis_and_guesses_cannot_forge_quotes():
    snap = snapshot(); record = snap['records'][0]
    assert proposals.checked_proposal(record, suggestion('paper_inference'), snap['chunks']) is None
    raw = suggestion('paper_inference'); raw['evidences'] = [dict(file_id='main', chunk_index=0, quote='Tin is metallic.')]
    parsed = proposals.checked_proposal(record, raw, snap['chunks'])
    assert parsed and parsed['basis_kind'] == 'paper_inference' and not parsed['supported']
    raw['basis_kind'] = 'general_knowledge'; raw['evidences'][0]['quote'] = 'Tin has Tc of 40 K.'
    assert proposals.checked_proposal(record, raw, snap['chunks']) is None
    assert proposals.checked_proposal(record, suggestion('invented'), snap['chunks']) is None


def test_unadopted_optional_suggestion_does_not_block_submission():
    snap = snapshot()
    result = dict(status='missing', reason='无直接原文', proposal=suggestion(), evidences=[])
    public = ev.public_snapshot(snap, {'summary': result})
    assert not public['needs_check']
    assert public['records'][0]['proposal']['basis_kind'] == 'general_knowledge'
    assert ev.resolve_results(snap, {'summary': result}, 1, None, snap['version'])[0]['proposal']


def adopted_result(snap):
    r = snap['records'][0]
    return dict(status='missing', reason='无原文支持', evidences=[], adopted_basis='general_knowledge',
                decision=dict(accepted=True, human_confirmed=False, actor_user_id=1, basis_kind='general_knowledge',
                              final_content_hash=r['content_hash'], source_hash=r['source_hash']))


def test_adopted_guess_can_enter_pending_but_cannot_approve_without_human():
    upload = snapshot(value='Electron-phonon coupling is plausible.')
    result = adopted_result(upload)
    assert ev.resolve_results(upload, {'summary': result}, 1, None, upload['version'])
    paper = {**upload, 'target': 'paper'}
    with pytest.raises(HTTPException):
        ev.resolve_results(paper, {'summary': result}, 2, None, paper['version'])
    result['decision'].update(human_confirmed=True, actor_user_id=2, reason='根据材料与方法人工确认')
    checked = ev.resolve_results(paper, {'summary': result}, 2, None, paper['version'])[0]
    assert checked['adopted_basis'] == 'general_knowledge' and checked['human_confirmed']


def test_reasonable_model_result_cannot_erase_adopted_guess():
    snap = snapshot('paper', 'Plausible mechanism')
    raw = adopted_result(snap)
    raw.update(status='supported', evidences=[dict(file_id='main', chunk_index=0, quote='Tin is metallic.')])
    checked = ev.checked_result(snap['records'][0], raw, snap['chunks'])
    assert checked['adopted_basis'] == 'general_knowledge'
    assert checked['status'] != 'supported'
    with pytest.raises(HTTPException):
        ev.resolve_results(snap, {'summary': raw}, 2, None, snap['version'])


def test_formal_rag_source_keeps_generation_basis_after_human_approval():
    snap = snapshot('paper', 'Plausible mechanism'); raw = adopted_result(snap)
    raw['decision'].update(human_confirmed=True, actor_user_id=2, reason='专业判断')
    result = ev.checked_result(snap['records'][0], raw, snap['chunks'])
    source = SimpleNamespace(id=1, paper_id=1, paper_revision=1, field_path='paper.summary', result=result)
    chunk = source_chunk(source)
    assert '通用知识推测' in chunk['attribution']
    assert '论文' in chunk['attribution']


def test_empty_numeric_and_list_fields_have_correct_suggestion_types():
    rows = science.field_records('paper', 'paper', {}, science.PAPER_FIELDS)
    snap = ev.complete_snapshot('upload', '1', rows, [], {})
    by_field = {r['field']: r for r in snap['records']}
    assert by_field['paper.year']['editable_fields'][0]['schema']['type'] == 'integer'
    assert by_field['paper.authors']['editable_fields'][0]['schema']['type'] == 'array'
    assert proposals.valid_value([{'material': 'Sn', 'relation': 'investigates'}], proposals.schema_for([], 'material_relations'))
    assert proposals.valid_value({'lambda_ep': 0.5, 'mu_star': None}, proposals.schema_for(None, 'calculation_context'))
    assert proposals.valid_value({'applied_field_t': 0.2}, proposals.schema_for(None, 'experimental_context'))


def test_review_questionable_suggestion_loses_old_auto_accept_permission(monkeypatch):
    snap = snapshot(value='Tin')
    candidate = suggestion('paper_quote')
    candidate['evidences'] = [dict(file_id='main', chunk_index=0, quote='Tin is metallic.')]
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *args, **kwargs: {'results': [dict(key='summary',
        status='unsupported', reason='不支持结论', evidences=candidate['evidences'],
        proposal_review={'status': 'questionable', 'explanation': '旧建议并非论文结论'})]})
    result = ev.evaluate_batch(snap['records'], snap['chunks'], 'review_all', {'summary': {'proposal': candidate}})[0]
    assert result['proposal']['values'] == candidate['values']
    assert result['proposal']['supported'] is False


def test_generated_summary_enforces_existing_english_storage_contract(monkeypatch):
    snap = snapshot()
    raw = suggestion(); raw['values'] = {'': '这段建议不符合英文存储要求'}
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *args, **kwargs: {'results': [dict(key='summary', status='missing', proposal=raw)]})
    assert ev.evaluate_batch(snap['records'], snap['chunks'], 'generate')[0]['proposal'] is None


def test_transfer_disambiguates_identical_quotes_using_file_map():
    snap = snapshot(value='Tin'); record = snap['records'][0]
    result = {**record, 'proposal': {'evidences': [dict(file_id='main', chunk_index=0, quote='Tin is metallic.')]}}
    chunks = [dict(file_id=str(i), chunk_index=0, content='Tin is metallic.') for i in (41, 42)]
    transferred = science.transfer_result(record, result, chunks, {'main': 42})
    assert transferred['proposal']['evidences'][0]['file_id'] == '42'


def test_transfer_keeps_changed_upload_field_as_history_without_authority():
    snap = snapshot(value='Before save'); old = {**snap['records'][0], **adopted_result(snap)}
    current = snapshot('paper', 'After save')['records'][0]
    transferred = science.transfer_result(current, old, [])
    assert transferred['status'] == 'unchecked' and not transferred.get('decision')
    assert transferred['history'][0]['current_value'] == 'Before save'
    assert transferred['history'][0]['decision']


def test_model_batch_receives_existing_judgement_and_reviews_suggestion(monkeypatch):
    import backend.ingest.property_evidence as module
    evaluate = getattr(module, 'evaluate_batch', None)
    assert callable(evaluate), '共享字段模型执行器尚未实现'
    snap = snapshot(value='Tin mechanism')
    prior = {'summary': dict(status='supported', reason='旧判断', proposal=suggestion())}
    calls = []
    def complete(system, message, **kwargs):
        import json
        calls.append((system, json.loads(message)))
        return {'results': [dict(key='summary', status='uncertain', reason='需人工核对', evidences=[],
                                 proposal_review={'status': 'reasonable', 'explanation': '符合一般金属机制，但缺少本文证据'})]}
    monkeypatch.setattr('backend.rag.llm.complete_json', complete)
    results = evaluate(snap['records'], snap['chunks'], 'review_all', prior)
    assert calls[0][1]['records'][0]['previous_result']['reason'] == '旧判断'
    assert calls[0][1]['records'][0]['previous_result']['proposal']['basis_kind'] == 'general_knowledge'
    assert results[0]['proposal']['basis_kind'] == 'general_knowledge'
    assert results[0]['proposal_review']['status'] == 'reasonable'


def test_full_audit_does_not_reuse_supported_cache(monkeypatch):
    from backend.api import evidence as api
    snap = snapshot('paper', 'current')
    monkeypatch.setattr(api, 'snapshot_for', lambda *args: (snap, {'summary': {'status': 'supported', 'reason': 'old'}}))
    monkeypatch.setattr(api, 'get_llm_config', lambda: SimpleNamespace(api_key='fixture'))
    saved = []
    monkeypatch.setattr(api, 'redis_client', lambda: SimpleNamespace(setex=lambda *args: saved.append(args)))
    monkeypatch.setattr(api, 'save_llm_config', lambda *args: None)
    monkeypatch.setattr(api, 'upload_queue', lambda: SimpleNamespace(enqueue=lambda *args, **kwargs: None))
    api.create_job(api.Target(target='paper', target_id='1', expected_version=snap['version'], purpose='review_all'), SimpleNamespace(id=2, role='admin'))
    import json
    job = json.loads(saved[0][2])
    assert job.get('purpose') == 'review_all'
    assert job['cached'] == {}
    assert job['prior']['summary']['reason'] == 'old'


@pytest.mark.parametrize('target,role', [('upload', 'user'), ('paper', 'user'), ('upload', 'admin')])
def test_full_audit_permission_does_not_expand_upload_or_user_access(monkeypatch, target, role):
    from backend.api import evidence as api
    snap = snapshot(target)
    monkeypatch.setattr(api, 'snapshot_for', lambda *args: (snap, {}))
    with pytest.raises(HTTPException) as error:
        api.create_job(api.Target(target=target, target_id='1', expected_version=snap['version'], purpose='review_all'), SimpleNamespace(id=1, role=role))
    assert error.value.status_code == 403


def test_upload_to_paper_rebinds_nested_suggestion_sources():
    import copy
    old = snapshot(value='Tin')
    row = old['records'][0]
    source = dict(file_id='main', chunk_index=0, quote='Tin is metallic.')
    result = {**row, 'status': 'supported', 'evidences': [source],
              'proposal': {'values': {'': 'Tin is metallic.'}, 'supported': True, 'evidences': [source]}}
    new = copy.deepcopy(row); new['key'] = 'permanent-summary'
    chunks = [dict(file_id='42', chunk_id=10, chunk_index=0, content='Tin is metallic.')]
    transfer = getattr(science, 'transfer_result', None)
    assert callable(transfer)
    rebound = transfer(new, result, chunks)
    assert rebound['key'] == 'permanent-summary'
    assert rebound['proposal']['evidences'][0]['file_id'] == '42'
    assert ev.checked_result(new, rebound, chunks)['proposal'] is not None


def test_missing_normalized_condition_keeps_browsable_empty_field():
    for data, field in [({'pressure_raw': '1', 'pressure_unit_raw': 'bar'}, 'pressure_value_gpa'),
                        ({'temperature_raw': '20', 'temperature_unit_raw': 'C'}, 'temperature_value_k')]:
        rows = science.state_records({'state_key': 's', field: None, **data}, 0)
        r = next(r for r in rows if r['field'].endswith('.' + field))
        assert r['required'] is False and r['kind'] == 'field'


def test_derived_value_inherits_pending_adoption_but_not_human_authority(monkeypatch):
    rows = science.state_records({'state_key': 's', 'material': 'Sn', 'element_count': 1}, 0)
    snap = ev.complete_snapshot('upload', '1', rows, [], {})
    material = next(r for r in rows if r['field'].endswith('.material'))
    adopted = adopted_result({**snap, 'records': [material]})
    monkeypatch.setattr(ev, 'transient_results', lambda *args: (None, {}))
    result = ev.resolve_results(snap, {material['key']: adopted}, 1, None, snap['version'])
    derived = next(r for r in result if r['kind'] == 'derived')
    assert derived['adopted_basis'] == 'general_knowledge'
    assert science.adopted_suggestion(derived) and not science.human_confirmed(derived)


def test_review_preserves_saved_suggestion_with_quotes_in_separate_batches(monkeypatch):
    snap = snapshot(value='Tin')
    chunks = [*snap['chunks'], dict(file_id='appendix', chunk_index=0, content='Tin is superconducting.')]
    candidate = suggestion('paper_inference')
    candidate['evidences'] = [dict(file_id=c['file_id'], chunk_index=0, quote=c['content']) for c in chunks]
    def complete(*args, **kwargs):
        return {'results': [dict(key='summary', status='uncertain', reason='需综合全文', evidences=[])]}
    monkeypatch.setattr('backend.rag.llm.complete_json', complete)
    # 原实现把跨批次的已保存建议当成本批新引句重新校验，导致候选丢失。
    records = snap['records']
    outputs = [ev.evaluate_batch(records, [chunk], 'review_all', {'summary': {'proposal': candidate}}, source_catalog=chunks)[0] for chunk in chunks]
    result = ev.aggregate_candidates(records, {'summary': outputs}, {'summary': []}, 'fixture')['summary']
    assert result['proposal'] and len(result['proposal']['evidences']) == 2
