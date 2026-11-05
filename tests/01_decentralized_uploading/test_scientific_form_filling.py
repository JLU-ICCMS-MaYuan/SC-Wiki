"""＃176：真实错误候选、模型整理与来源读取边界，不调用业务写入。"""
import json
from copy import deepcopy
from pathlib import Path

import pytest


def fixture():
    state = json.loads((Path(__file__).parents[1] / 'fixtures/issue176/cah6-candidates.json').read_text())
    from backend.ingest.fixed_form_contract import convert_conditions
    for module in state['property_modules']:
        for record in module['records']:
            old = record.get('payload', {}).get('calculation_conditions')
            if old is not None:
                record['payload']['calculation_conditions'] = convert_conditions(old)[0]
    sources = []
    for record in state['property_modules'][0]['records']:
        for evidence in record['evidences']:
            if any(s.get('block_id') == evidence.get('block_id') for s in sources):
                continue
            sources.append({**evidence, 'source_id': f'source-{len(sources)}', 'content': evidence['quote']})
    return state, sources


def response(sources):
    ids = [s['source_id'] for s in sources if s.get('pdf_page') == 3 and '235 K' in s['content']]
    assert ids
    return {'done': True, 'records': [
        {'candidate_ids': ['s0:m0:r1', 's0:m0:r2'], 'group': 'epc', 'method': 'eliashberg',
         'values': {'value_kind': 'number', 'value_number': 235, 'method_code': 'isotropic_eliashberg',
                    'parameters': {'lambda_ep': 2.69, 'mu_star': .1}}, 'source_ids': ids, 'reason': '摘要范围与正文配对点为同一结果'},
        {'candidate_ids': ['s0:m0:r1', 's0:m0:r3'], 'group': 'epc', 'method': 'eliashberg',
         'values': {'value_kind': 'number', 'value_number': 220, 'method_code': 'isotropic_eliashberg',
                    'parameters': {'lambda_ep': 2.69, 'mu_star': .13}}, 'source_ids': ids, 'reason': '正文明确对应'},
    ], 'excluded': [{'candidate_id': 's0:m0:r0', 'reason': 'S19 为曲线方法比较，未提取数值',
                      'category': 'curve_only', 'source_ids': [sources[0]['source_id']]}], 'unresolved': []}


def test_real_four_candidates_become_one_group_two_points_with_all_origins():
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    original = deepcopy(state)
    out, audit = apply_plan([state], sources, response(sources))
    records = out[0]['property_modules'][0]['records']
    assert [(r['value_number'], r['payload']['parameters']['mu_star']) for r in records] == [(235, .1), (220, .13)]
    assert len({r['payload']['tc_group']['group_key'] for r in records}) == 1
    assert len({r['payload']['tc_group']['method_key'] for r in records}) == 1
    assert not any(r['is_representative'] for r in records)
    assert all(r['payload']['parameters'].get('omega_log') is None for r in records)
    assert not any(e['key'] == 'mu_star_reported_range' for r in records for e in r['payload']['parameters'].get('extensions', []))
    assert len(audit['candidate_dispositions']) == 4
    assert state == original


def test_added_method_name_is_rejected_by_formal_processing_not_hidden_as_metadata():
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    plan = response(sources)
    plan['records'][0]['method_name'] = 'unrequested description'
    before = deepcopy(state)
    with pytest.raises(ValueError, match='字段'):
        apply_plan([state], sources, plan)
    assert state == before


def test_method_explanation_stays_in_existing_reason_not_form_payload():
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    plan = response(sources)
    reason = '同一方法在不同 μ* 下的两个 Tc；具体原文及定位由 source_ids 保留。'
    plan['records'][0]['reason'] = reason
    result, audit = apply_plan([state], sources, plan)
    assert any(reason in x.get('reasons', []) for x in audit['candidate_dispositions'].values())
    for record in result[0]['property_modules'][0]['records']:
        assert 'method_name' not in record['payload']['tc_group']
        assert record['evidences']


@pytest.mark.parametrize('bad', ['missing_candidate', 'unknown_source', 'mixed_method', 'invented_candidate', 'lost_parameter'])
def test_invalid_plan_cannot_drop_or_misplace_results(bad):
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    plan = response(sources)
    if bad == 'missing_candidate': plan['excluded'] = []
    if bad == 'unknown_source': plan['records'][0]['source_ids'] = ['source-not-real']
    if bad == 'mixed_method': plan['records'][0]['values']['method_code'] = 'Eliashberg and McMillan'
    if bad == 'invented_candidate': plan['records'][0]['candidate_ids'] += ['imaginary']
    if bad == 'lost_parameter': plan['records'][0]['values']['parameters'].pop('lambda_ep')
    with pytest.raises(ValueError):
        apply_plan([state], sources, plan)


def test_missing_source_is_requested_once_and_no_information_loop_stops():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    state, _ = fixture()
    calls = []
    def model(system, prompt):
        calls.append(json.loads(prompt))
        return {'done': False, 'read_source_ids': ['source-0'], 'search': []}
    result, report = fill_scientific_forms([state], [{'file_id':'main','content':'Only a method description.'}], model)
    assert result == [state]
    assert len(calls) <= 2
    assert report['status'] != 'completed'
    assert report['attempts']


def test_numeric_result_cannot_be_excluded_as_curve_text():
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    plan = response(sources)
    plan['records'][0]['candidate_ids'].remove('s0:m0:r2')
    plan['excluded'].append({'candidate_id':'s0:m0:r2','category':'curve_only','source_ids':['source-0'],'reason':'wrong'})
    with pytest.raises(ValueError):
        apply_plan([state], sources, plan)


def test_llm_requests_unread_block_then_fills_missing_value():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    state, _ = fixture()
    state['property_modules'][0]['records'] = state['property_modules'][0]['records'][:1]
    # 本例使用下面的合成文档，不携带另一份真实PDF的旧块身份。
    state['property_modules'][0]['records'][0]['evidences'] = []
    chunks = [{'file_id':'main','content': 'x' * 39000},
              {'file_id':'si','content': 'The missing result is 12 K with mu*=0.15. ' + 'y' * 39000}]
    calls = []
    def model(system, prompt):
        request = json.loads(prompt)
        calls.append(request)
        if len(calls) == 1:
            assert [s['source_id'] for s in request['sources']] == ['source-0']
            return {'done': False, 'search':['missing result']}
        assert {s['source_id'] for s in request['sources']} == {'source-0','source-1'}
        return {'done': True, 'records':[{'candidate_ids':['s0:m0:r0'],'group':'g','method':'m',
            'values':{'value_kind':'number','value_number':12,'method_code':'other','method_raw':'Named solver',
                      'parameters':{'mu_star':.15}},'source_ids':['source-1'],'reason':'补充材料明确报告'}],
            'excluded':[],'unresolved':[]}
    result, audit = fill_scientific_forms([state], chunks, model)
    record = result[0]['property_modules'][0]['records'][0]
    assert audit['status'] == 'completed' and len(calls) == 2
    assert record['value_number'] == 12 and record['method_raw'] == 'Named solver'
    assert record['evidences'][0]['file_id'] == 'si'


def test_range_equivalence_requires_opt_in_and_matching_method():
    from types import SimpleNamespace as Claim
    from backend.ingest.document_claims import missing_tc_measurements
    def claim(name, value):
        return Claim(claim_id=name, target_path='state.records.'+name, value=value)
    base = {'property_code':'tc','record_type':'predicted_tc','method_code':'isotropic_eliashberg'}
    before = [claim('range',{**base,'value_min':220,'value_max':235})]
    after = [claim('a',{**base,'value_number':220}),claim('b',{**base,'value_number':235})]
    assert missing_tc_measurements(before,after) == ['range']
    assert not missing_tc_measurements(before,after,allow_paired_range=True)
    after[1].value['method_code']='allen_dynes'
    assert missing_tc_measurements(before,after,allow_paired_range=True) == ['range']


@pytest.mark.parametrize('property_code,unit', [('dos_fermi','states/eV/f.u.')])
def test_other_scientific_record_preserves_definition_units_and_sources(property_code,unit):
    from backend.ingest.scientific_form_filling import apply_plan
    state, sources = fixture()
    base = state['property_modules'][0]['records'][2]
    base.update(record_type='property', property_code=property_code, module_code='electronic_properties',
                method_code=None, value_number=1.2, value_raw='1.2 '+unit, canonical_unit=unit, unit_raw=unit,
                definition_key='record.electronic_properties.'+property_code, payload={})
    state['property_modules']=[{'module_code':'electronic_properties','records':[base]}]
    plan={'done':True,'records':[{'candidate_ids':['s0:m0:r0'],'values':{'value_kind':'number','value_number':1.2},
           'source_ids':['source-0'],'reason':'同一带隙记录保留来源'}],'excluded':[],'unresolved':[]}
    result,_=apply_plan([state],sources,plan)
    r=result[0]['property_modules'][0]['records'][0]
    assert r['canonical_unit']==unit and 'tc_group' not in r['payload']
    assert r['definition_key']=='record.electronic_properties.'+property_code


def test_retired_band_gap_remains_readable_without_new_model_generation():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    state, _ = fixture()
    record = state['property_modules'][0]['records'][0]
    record.update(property_code='band_gap', record_type='property', module_code='electronic_properties')
    state['property_modules'][0]['records'] = [record]
    original = deepcopy(state)
    result, report = fill_scientific_forms([state], [], lambda *args: pytest.fail('历史带隙不能重新生成'))
    assert result == [original] and report['status'] == 'not_needed'


def test_cancel_propagates_and_technical_failure_keeps_candidates():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    from backend.ingest.upload_jobs import UploadCancelled
    state,_=fixture()
    def cancelled(*args):
        raise UploadCancelled('cancelled')
    with pytest.raises(UploadCancelled):
        fill_scientific_forms([state],[{'file_id':'main','content':'text'}],cancelled)
    def broken(*args):
        raise ConnectionError('isolated connection error')
    result,audit=fill_scientific_forms([state],[{'file_id':'main','content':'text'}],broken,max_rounds=2)
    assert result==[state] and audit['status']=='incomplete' and len(audit['attempts'])==2


def test_form_sources_use_ir_original_blocks_instead_of_markdown_comments(tmp_path):
    import pymupdf
    from backend.ingest.document_parsers import DocumentSource, ParseOptions, PyMuPDFParser
    from backend.ingest.scientific_form_filling import form_sources
    from backend.ingest.scientific_context import build_context
    pdf=tmp_path/'source.pdf'
    document=pymupdf.open()
    page=document.new_page();page.insert_text((50,50),'The reported transition temperature is 12 K.')
    document.save(pdf);document.close()
    source=DocumentSource(file_id='main',path=pdf,role='main')
    ir=PyMuPDFParser().parse(source,ParseOptions())
    sources=form_sources({'main':ir},[{'file_id':'main','file_role':'main','content':'<!-- block: b -->\nWrong Markdown'}])
    context=build_context(sources)
    assert any('12 K' in s['content'] and s.get('block_id') for s in context['sources'])
    assert all('Wrong Markdown' not in s['content'] for s in context['sources'])


def test_combined_methods_do_not_select_first_keyword():
    from backend.ingest.domain_extraction import _normalize_tc_method
    assert _normalize_tc_method('Eliashberg and McMillan equations','predicted_tc')=='unknown'
    assert _normalize_tc_method('SCDFT and Eliashberg','predicted_tc')=='unknown'
    assert _normalize_tc_method('Allen-Dynes-modified McMillan equation','predicted_tc')=='allen_dynes'


def test_measured_tc_keeps_experimental_conditions_and_does_not_get_theory_group():
    from backend.ingest.scientific_form_filling import apply_plan
    state,sources=fixture()
    base=state['property_modules'][0]['records'][2]
    base.update(record_type='measured_tc',method_code='resistivity',
                definition_key='record.superconductive_properties.measured_tc.resistivity',
                payload={'experimental_conditions':{'description':'four-probe'}})
    state.update(state_kind='experimental')
    state['property_modules'][0]['records']=[base]
    plan={'done':True,'records':[{'candidate_ids':['s0:m0:r0'],
        'values':{'value_kind':'number','value_number':235},'source_ids':['source-0'],'reason':'保留测量结果'}],
        'excluded':[],'unresolved':[]}
    result,_=apply_plan([state],sources,plan)
    record=result[0]['property_modules'][0]['records'][0]
    assert record['record_type']=='measured_tc' and record['method_code']=='resistivity'
    assert record['payload']==base['payload']
