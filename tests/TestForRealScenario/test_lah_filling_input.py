"""候选证据只在请求中集中传递，原始候选、来源身份和落库表示保持。"""
from copy import deepcopy
import json


def test_repeated_evidence_is_pooled_without_mutating_candidates():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    evidence = {'file_id': 'main', 'block_id': 'table', 'pdf_page': 1,
                'quote': 'One complete original table. ' * 2000}
    record = {'record_key': 'first', 'property_code': 'tc', 'value_number': 274,
              'evidences': [evidence, deepcopy(evidence)]}
    second = {**deepcopy(record), 'record_key': 'second', 'value_number': 286}
    states = [{'state_key': 'state', 'material': 'LaH10', 'pressure_value_gpa': 210,
               'property_modules': [{'records': [record, second]}]}]
    before = deepcopy(states)
    seen = []
    def model(_, content):
        request = json.loads(content);seen.append(request)
        assert len(request['candidate_evidences']) == 1
        refs = [r['record']['evidences'] for r in request['candidates']]
        assert refs[0] == refs[1] and len(refs[0]) == 1
        assert request['candidate_evidences'][refs[0][0]['evidence_id']] == evidence
        return {'done': True, 'records': [], 'excluded': [],
                'unresolved': [{'candidate_id': c['candidate_id'], 'category': 'ambiguous',
                                'reason': '固定回归仅核对输入保真，不作科学判断'} for c in request['candidates']]}
    result, report = fill_scientific_forms(states, [{'file_id': 'main', 'content': 'Original context'}], model)
    assert seen and report['status'] == 'completed'
    assert states == before and result == before


def test_same_quote_at_different_locations_keeps_separate_evidence():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    evs=[{'file_id': f, 'block_id': 'block', 'pdf_page': p, 'quote': 'same words'}
         for f,p in [('main',1),('si',1),('main',2)]]
    states=[{'property_modules':[{'records':[{'record_key':'r','property_code':'tc','evidences':evs}]}]}]
    def model(_, content):
        request=json.loads(content)
        assert list(request['candidate_evidences'].values()) == evs
        read={s['source_id'] for s in request['sources']}
        assert not read & {s['source_id'] for s in request['source_index']}
        return {'done':True,'records':[],'excluded':[],
                'unresolved':[{'candidate_id':'s0:m0:r0','category':'ambiguous','reason':'保留三个真实来源身份'}]}
    _,report=fill_scientific_forms(states,[{'file_id':'main','content':'same words'}],model)
    assert report['status']=='completed'
