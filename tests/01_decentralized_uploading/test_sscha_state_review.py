"""#149 状态范围、新增来源与准确原文查证的回归。"""
from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest import field_review, field_decisions, evidence_audit
from backend.ingest.state_field_review import initial_state_value, bind_scope_events


def snapshot(optimization='sscha', note=None):
    state = {'state_key': 's', 'material': 'LaSc2H24', 'pressure_value_gpa': 300,
             'state_kind': 'theoretical', 'structure_optimization': optimization,
             'material_dimensionality': 'three_dimensional', 'note': note}
    chunks = [{'file_id': 'main', 'chunk_index': 0,
               'content': 'SSCHA relaxation of LaSc2H24 at 300 GPa retains a three-dimensional cage network.'}]
    snap = ev.complete_snapshot('upload', 'task', science.state_records(state, 0), chunks, {})
    return snap, next(r for r in snap['records'] if r['field'].endswith('.material_dimensionality'))


def test_scope_is_sent_and_binds_reuse_without_unrelated_note(monkeypatch):
    from backend.rag import llm
    snap, row = snapshot()
    static, other = snapshot('classical_static')
    assert snap['version'] != static['version']
    old = {**row, 'status': 'supported'}
    assert field_review.reusable(row, old)
    assert not field_review.reusable(other, old)
    _, unrelated = snapshot(note='new unrelated note')
    assert field_review.reusable(unrelated, old)
    def model(system, user, **kwargs):
        data = json.loads(user)
        assert data['records'][0]['state_review_context']['structure_optimization'] == 'sscha'
        return {'results': [{'key': row['key'], 'status': 'supported', 'reason': '同一材料同压力的 SSCHA 原文支持。',
                             'evidences': [{'source_id': 'review-source-0'}]}]}
    monkeypatch.setattr(llm, 'complete_json', model)
    result = ev.evaluate_batch([row], snap['chunks'], purpose='field')[0]
    assert result['status'] == 'supported'
    assert result['evidences'][0]['quote'] == snap['chunks'][0]['content']


def test_legacy_result_does_not_survive_later_scope_edit():
    snap, row = snapshot()
    old = {k:v for k,v in row.items() if k != 'state_review_context'}
    old.update(status='supported', review_started_at='2026-10-20T00:00:00+00:00')
    assert field_review.reusable(row, old)
    scope_key = science.item_identity(science.item_identity('state','s'), 'structure_optimization')
    snap['_field_change_events'] = [{'item_key': scope_key, 'before_value':'classical_static',
         'after_value':'sscha','occurred_at':'2026-10-21T00:00:00+00:00'}]
    bind_scope_events(snap)
    assert not field_review.reusable(row, old)


@pytest.mark.parametrize('origin', ['human_input','model_extraction','system_assembly'])
def test_creation_does_not_require_manual_materials_or_grant_approval(origin):
    snap, row = snapshot()
    user = SimpleNamespace(id=2, username='mayuan')
    events = evidence_audit.field_change_events({'records':[]}, snap, user, value_origin=origin)
    snap['_field_change_events'] = events
    assert initial_state_value(snap,row)
    assert next(e for e in events if e['item_key']==row['item_key'])['state_creation']['value_origin']==origin
    detail=field_decisions.detail({**snap,'records':[row]}, {})
    assert detail['record']['automatic_source_lookup']
    assert not detail['can_approve']
    assert not detail['record']['human_confirmed']
    changed=deepcopy(row);changed['current_value']='two_dimensional'
    assert not initial_state_value(snap,changed)


def test_filling_blank_existing_field_is_not_new_state():
    snap,row=snapshot()
    old=deepcopy(snap)
    next(r for r in old['records'] if r['key']==row['key'])['current_value']=None
    snap['_field_change_events']=evidence_audit.field_change_events(old,snap,SimpleNamespace(id=2,username='mayuan'))
    assert not initial_state_value(snap,row)
    row['current_value']=None
    assert not initial_state_value(snap,row)


@pytest.mark.parametrize('reference', [
    {'source_id':'review-source-999'},
    {'source_id':'review-source-0','file_id':'wrong'},
    {'source_id':'review-source-0','quote':'Invented content'},
])
def test_bad_reference_is_unfinished_not_false_scientific_rejection(reference):
    snap,row=snapshot()
    resolved=ev.resolve_review_sources([reference],snap['chunks'])
    result=ev.checked_result(row,{'status':'supported','reason':'有依据','suggestion':'无需修改',
                                 'evidences':resolved},snap['chunks'])
    assert result['status']=='unchecked'
    assert result['location_check']=='failed'
    assert '有依据' not in result['reason']
    assert result['suggestion']!='无需修改'
    assert result['model_opinion']['reason']=='有依据'


def test_missing_reference_does_not_keep_contradictory_advice():
    snap,row=snapshot()
    result=ev.checked_result(row,{'status':'supported','reason':'有依据','suggestion':'无需修改','evidences':[]},snap['chunks'])
    assert result['status']=='missing'
    assert '有依据' not in result['reason']
    assert result['model_opinion']['reason']=='有依据'


def test_wrong_chunk_same_file_cannot_be_rescued_by_global_search():
    chunks=[{'file_id':'main','chunk_index':0,'content':'first paragraph'},
            {'file_id':'main','chunk_index':1,'content':'second paragraph'}]
    result=ev.resolve_review_sources([{'source_id':'review-source-0','quote':'second paragraph'}],chunks)
    assert ev.locate(result[0],chunks) is None


def test_soft_hyphen_layout_recovers_exact_original_not_model_retyping():
    original='The LaSc2H24 structure consists of a unique three-\u00addimensional H clathrate network.'
    model_quote='The LaSc2H24 structure consists of a unique three- dimensional H clathrate network.'
    chunks=[{'file_id':'main','chunk_index':0,'content':original}]
    found,error=ev.locate_with_reason({'file_id':'main','quote':model_quote},chunks)
    assert error is None and found['quote']==original
    assert ev.locate({'file_id':'main','quote':model_quote.replace('LaSc2H24','LaSc2H25')},chunks) is None


def test_sign_and_number_changes_are_not_layout_equivalence():
    chunks=[{'file_id':'main','chunk_index':0,'content':'energy -3 eV at 300 GPa'}]
    assert ev.locate({'quote':'energy 3 eV at 300 GPa'},chunks) is None
    assert ev.locate({'quote':'energy -3 eV at 350 GPa'},chunks) is None
