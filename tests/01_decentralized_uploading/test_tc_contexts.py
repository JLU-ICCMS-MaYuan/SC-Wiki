from copy import deepcopy
import json
import pytest
from backend.ingest.tc_contexts import compact_module,expand_module

def fixture():
    return {'module_key':'m','records':[dict(record_key='p'+str(i),record_type='predicted_tc',
        method_code='isotropic_eliashberg',method_raw='Eliashberg',
        value_number=tc,payload=dict(parameters=dict(mu_star=mu,lambda_ep=2.69),
        calculation_conditions={'calculation_code':'QE','k_grid':'24x24x24'},
        tc_group=dict(version=1,group_key='g',method_key='e',point_key='p'+str(i))))
        for i,(mu,tc) in enumerate([(0.1,230),(0.13,220),(0.16,210)])]}

def test_three_points_store_conditions_once_and_roundtrip():
    original=fixture();stored=compact_module(original)
    assert json.dumps(stored).count('24x24x24')==1
    assert json.dumps(stored).count('2.69')==1
    assert all('calculation_conditions' not in r['payload'] and r['method_code'] is None for r in stored['records'])
    assert expand_module(stored)=={**original,'metadata':{}}
    assert compact_module(stored)==stored
    assert original==fixture()

def test_point_update_does_not_change_shared_context_or_other_points():
    stored=compact_module(fixture());view=expand_module(stored)
    view['records'][1]['value_number']=225
    changed=compact_module(view)
    assert changed['metadata']==stored['metadata']
    assert changed['records'][0]==stored['records'][0]

def test_legacy_is_not_guessed_and_conflicting_group_is_rejected():
    old=fixture()
    for r in old['records']:r['payload'].pop('tc_group')
    assert 'tc_contexts' not in compact_module(old)['metadata']
    wrong=fixture();wrong['records'][1]['payload']['parameters']['lambda_ep']=3.0
    with pytest.raises(ValueError):compact_module(wrong)

def test_scdft_absence_and_real_zero_are_distinct():
    value=fixture()
    for r in value['records']:
        r['method_code']='scdft';r['payload']['parameters'].update(mu_star=None,mu_star_status='not_applicable')
    value['records'][1]['payload']['parameters'].update(mu_star=0,mu_star_status='reported')
    assert expand_module(compact_module(value))['records'][1]['payload']['parameters']['mu_star']==0
    assert expand_module(compact_module(value))['records'][0]['payload']['parameters']['mu_star'] is None

def test_shared_source_association_stored_once_without_losing_point_order():
    value=fixture()
    shared={'target_path':'/payload/calculation_conditions/k_grid','explanation':'共同范围原文','evidence':{'quote':'Shared evidence'}}
    for index,record in enumerate(value['records']):
        record['payload']['source_associations']=[{'target_path':'/payload/parameters/mu_star','explanation':str(index)},deepcopy(shared)]
    stored=compact_module(value)
    assert json.dumps(stored).count('Shared evidence')==1
    assert expand_module(stored)=={**value,'metadata':{}}
