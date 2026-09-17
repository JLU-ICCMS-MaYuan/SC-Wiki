"""建议必须有来源、类型正确并绑定精确内容；不使用 LLM 代替确定性校验。"""
import copy
import pytest
from fastapi import HTTPException
from backend.ingest import evidence_proposals as p, property_evidence as ev


def fixture():
    record = dict(key='summary', item_key='summary', field='paper.summary', label='论文总结', kind='field', current_value='Tc 20 K', claim={'value': 'Tc 20 K'}, evidences=[])
    snap = ev.complete_snapshot('paper', '1', [record], [dict(file_id='1', chunk_index=0, content='Tc is 10 K.')], {})
    source = dict(file_id='1', chunk_index=0, quote='Tc is 10 K.')
    return snap, source


def test_candidate_requires_actual_quote_and_typed_value():
    snap, source = fixture(); record = snap['records'][0]
    raw = dict(values={'': 'Tc 为 10 K'}, supported=True, evidences=[source])
    proposal = p.checked_proposal(record, raw, snap['chunks'])
    assert proposal['values'] == {'': 'Tc 为 10 K'}
    assert p.checked_proposal(record, {**raw, 'values': {'': 10}}, snap['chunks']) is None
    assert p.checked_proposal(record, {**raw, 'values': {'paper.title': '伪造'}}, snap['chunks']) is None
    assert p.checked_proposal(record, {**raw, 'evidences': [{**source, 'quote': 'Tc is 30 K.'}]}, snap['chunks']) is None
    assert p.checked_proposal(record, {'suggestion': '改成 10 K'}, snap['chunks']) is None


def test_conflicting_candidates_do_not_pick_first_value():
    snap, source = fixture(); record = snap['records'][0]
    candidates = [ev.checked_result(record, {'status':'unsupported', 'reason':'温度不符', 'evidences':[source],
        'proposal':{'values':{'':value},'supported':True,'evidences':[source]}},snap['chunks']) for value in ['10 K', '20 K']]
    result = ev.aggregate_candidates([record], {'summary':candidates}, {'summary':[]}, 'test')
    assert result['summary']['proposal'] is None
    assert result['summary']['evidences']


def test_structure_cannot_be_generated_and_unknown_provider_cannot_confirm():
    snap, _ = fixture(); record = {**snap['records'][0], 'kind':'structure'}
    assert p.editable_fields(record) == []
    with pytest.raises(HTTPException): p.check_source(record, {}, snap['chunks'])
    with pytest.raises(HTTPException): p.check_source({**record,'provenance':{'verified':True}}, {}, [])
    known = {**record,'provenance':{'verified':True,'submitted_by_user_id':2}}
    assert p.check_source(known, {}, []) == []


def test_program_verifies_numbers_and_does_not_bind_changed_dependencies():
    record = dict(kind='property',claim={'record':{'value_number':'4.29','payload':{'pressure':10}},'state':{'temperature_value_k':'4.29'}})
    claim = p.expected_claim(record, {'value_number':3.78})
    assert claim['state'] == record['claim']['state']
    assert claim['record']['value_number'] == 3.78
    assert not p.valid_value(float('nan'), {'type':'number'})
    assert not p.valid_value(True, {'type':'number'})
    assert not p.valid_value(1.1, {'type':'integer'})


def test_original_judgement_and_human_decision_remain_separate():
    snap, source = fixture(); record = snap['records'][0]
    result = ev.checked_result(record, {'status':'uncertain','reason':'AI 原判断','evidences':[source],
        'decision':{'actor_user_id':2,'reason':'人工根据原文判断','final_content_hash':record['content_hash'],'source_hash':record['source_hash']}},snap['chunks'])
    assert result['reason'] == 'AI 原判断'
    assert result['decision']['reason'] == '人工根据原文判断'
    changed = copy.deepcopy(record); changed['content_hash'] = 'different'
    assert ev.checked_result(changed, result, snap['chunks'])['decision'] is None
