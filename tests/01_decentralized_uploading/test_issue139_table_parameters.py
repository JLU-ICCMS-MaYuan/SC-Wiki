"""独立 8 行答案、参数归一化及兼容输入边界。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.ingest.scientific_contracts import normalize_parameters
from backend.ingest.scientific_drafts import _property_modules_for_state
from backend.ingest.upload_contracts import convert_legacy_state
from backend.ingest.upload_contracts import convert_legacy_scientific_draft


def test_eight_rows_keep_approximation_parameters_and_pairing():
    expected = json.loads((Path(__file__).parents[1]/'fixtures/issue139/expected-table.json').read_text())
    records = []
    for row in expected['rows']:
        r = {'value_kind':'range','value_min':row['tc_min'],'value_max':row['tc_max'], 'payload':{
            'approximation':row['approximation'], 'parameters':{'lambda_ep':row['lambda_ep'], 'omega_log_k':row['omega_log'],
                'mu_star':{'min':0.1,'max':0.16,'value_raw':'0.16 to 0.1','tc_pairing':'inverse'}}}}
        normalize_parameters(r)
        p = r['payload']['parameters']
        assert p['lambda_ep'] == row['lambda_ep'] and p['omega_log'] == row['omega_log']
        assert next(e for e in p['extensions'] if e['key']=='mu_star')['value_max'] == 0.16
        records.append(r)
    assert len(records)==8
    assert records[1]['payload']['approximation'] != records[7]['payload']['approximation']


def test_unpaired_range_does_not_bind_tc_endpoints():
    r = {'payload':{'parameters':{'mu_star':'0.10–0.16'}}}
    normalize_parameters(r)
    assert r['payload']['parameters']['extensions'][0]['key'] == 'mu_star_reported_range'


def test_wrapped_metadata_alias_thousands_unit_and_idempotence():
    r = {'payload':{'parameters':{'omega_log_k':{'value_number':'1,294','unit':'K','evidence':{'quote':'1,294 K'},'source':'table 1'},
                                'lambda_ep':'2.20'}}}
    normalize_parameters(r)
    assert r['payload']['parameters']['omega_log']==1294
    extension = next(e for e in r['payload']['parameters']['extensions'] if e['key']=='omega_log_reported')
    assert extension['reported']['evidence']['quote']=='1,294 K'
    again=deepcopy(r)
    normalize_parameters(r)
    assert r==again
    unknown={'payload':{'parameters':{'omega_log':{'value_number':1200,'unit':'unknown'}}}}
    normalize_parameters(unknown)
    assert 'omega_log' not in unknown['payload']['parameters']
    assert unknown['payload']['parameters']['extensions'][0]['unit_raw']=='unknown'
    alias={'payload':{'parameters':{'omega_log':None,'omega_log_k':745}}}
    normalize_parameters(alias)
    assert alias['payload']['parameters']['omega_log']==745


def test_legacy_per_result_context_preserved_without_state_broadcast():
    state={'material':'LaSc2H24','calculation_context':{'lambda_ep':99,'k_grid':'wrong'},'tc_results':[
        {'tc_method':'isotropic_eliashberg','tc_min_k':281,'tc_max_k':311,'calculation_context':{'lambda_ep':3.94,'omega_log_k':745}},
        {'tc_method':'allen_dynes','tc_value_k':260,'lambda_ep':2.61,'omega_log_k':1165}]}
    normalized=convert_legacy_state(state)
    records=normalized['property_modules'][0]['records']
    assert records[0]['payload']['parameters']['lambda_ep']==3.94
    assert records[1]['payload']['parameters']['omega_log']==1165
    persisted=_property_modules_for_state(state)[0]['records']
    assert [r['payload']['parameters']['lambda_ep'] for r in persisted]==[3.94,2.61]
    assert not any(r['payload']['calculation_conditions'].get('k_grid') for r in persisted)


def test_legacy_explicit_row_pressures_split_and_ranges_keep_both_endpoints():
    original={'material_states':[{'material':'LaSc2H24','pressure_value_gpa':300,'tc_results':[
        {'tc_method':'Eliashberg','pressure_value_gpa':150,'approximation':'anharmonic','tc_value_k':281,'tc_min_k':281,'tc_max_k':311,
         'parameters':{'lambda_ep':3.94,'omega_log_k':745}},
        {'tc_method':'Eliashberg','pressure_value_gpa':300,'approximation':'harmonic','tc_min_k':303,'tc_max_k':329,
         'parameters':{'lambda_ep':3.34,'omega_log_k':968}}]}]}
    states=convert_legacy_scientific_draft(original)['material_states']
    assert [s['pressure_value_gpa'] for s in states]==[150,300]
    r=states[0]['property_modules'][0]['records'][0]
    assert r['value_kind']=='range' and r['value_number'] is None and r['value_max']==311
    assert r['method_code']=='isotropic_eliashberg'
    assert r['payload']['approximation']=='anharmonic'


def test_result_pressure_is_not_replaced_by_phase_stability_range():
    from backend.ingest.scientific_contracts import resolve_reported_pressures
    results={'material_states':[{'material':'LaSc2H24','pressure_value_gpa':None,
        'pressure_min_gpa':167,'pressure_max_gpa':300,'pressure_raw':'167 to 300 GPa',
        'evidences':[],'property_modules':[{'module_code':'superconductive_properties','records':[
            {'property_code':'tc','value_min':281,'value_max':311,'evidences':[],
             'payload':{'calculation_conditions':{'pressure_gpa':150}}},
            {'property_code':'tc','value_min':266,'value_max':294,'evidences':[],
             'payload':{'calculation_conditions':{'pressure_gpa':350}}}]}]}]}
    resolve_reported_pressures(results)
    assert [s['pressure_value_gpa'] for s in results['material_states']]==[150,350]
    assert all(s['pressure_min_gpa'] is None and s['pressure_max_gpa'] is None for s in results['material_states'])
    assert all(b['original_pressure_raw']=='167 to 300 GPa' for b in results['_pressure_bindings'])
