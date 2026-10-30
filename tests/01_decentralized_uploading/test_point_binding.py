import json
from pathlib import Path
from unittest.mock import patch
from backend.ingest import property_evidence as ev

FIXTURE=Path(__file__).parents[2]/'docs/specs/183-field-evidence-bundle/assets/point-binding-failure.json'

def test_real_contradictory_supported_answer_cannot_approve_wrong_pair():
    data=json.loads(FIXTURE.read_text())
    assert data['raw_result']['status']=='supported'
    with patch('backend.rag.llm.complete_json',return_value={'results':[data['raw_result']]}):
        results=ev.evaluate_batch([data['record']],data['chunks'])
    assert results[0]['status']!='supported'

def test_explicit_source_pair_conflict_rejects_numeric_location_success():
    data=json.loads(FIXTURE.read_text())
    data['raw_result']['point_binding']={'verdict':'conflict','source_pair':{'mu_star':.13,'tc_k':220}}
    with patch('backend.rag.llm.complete_json',return_value={'results':[data['raw_result']]}):
        results=ev.evaluate_batch([data['record']],data['chunks'])
    assert results[0]['status']=='unsupported'

def test_changing_mu_cannot_reuse_tc_pass_through_same_value_field_token(db_session):
    from copy import deepcopy
    from backend.ingest import scientific_evidence as science,field_review,field_input
    data=json.loads(FIXTURE.read_text())
    def snapshot(mu):
        record=deepcopy(data['record'])
        record['claim']['context']['paired_mu_star']=mu
        record['claim']['context']['direct_inputs']['payload.parameters.mu_star']=mu
        result=ev.complete_snapshot('upload','point-cache-probe',[record],data['chunks'],{})
        field_review.bind_support_versions(result,db_session)
        return result
    before=snapshot(.1);record=before['records'][0]
    science.save_results(db_session,before,{record['key']:{'status':'supported','reason':'隔离预置的正确配对',
        'field_review_binding':{'contract':field_input.CONTRACT,'token':record['field_input_token']},
        'point_binding':{'contract':'tc-point-binding-v1','expected_point':{'mu_star':.1,'tc_k':235},
        'source_pair':{'mu_star':.1,'tc_k':235},'verdict':'match'}}},1)
    db_session.flush()
    after=snapshot(.13)
    loaded=science.load_results(db_session,after,1,include_stale=True)
    assert loaded[after['records'][0]['key']]['stale']
