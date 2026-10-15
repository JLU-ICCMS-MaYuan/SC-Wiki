"""共用设置只补空；来源、阶段、例外与版本均有边界。"""
from copy import deepcopy

import pytest

from backend.ingest.scientific_context import (
    build_context, read_context, apply_associations, scientific_fingerprint,
    table_packages, association_issues,
)


def record():
    return {"record_key":"r", "module_code":"superconductive_properties", "record_type":"predicted_tc",
            "property_code":"tc", "method_code":"isotropic_eliashberg", "name_raw":"Tc",
            "value_kind":"range", "value_min":281, "value_max":311, "value_raw":"281–311",
            "unit_raw":"K", "canonical_unit":"K", "payload":{"calculation_conditions":{}, "parameters":{"lambda_ep":3.94}}}


def draft():
    return {"material_states":[{"state_key":"s", "material":"LaSc2H24", "pressure_value_gpa":150,
        "property_modules":[{"module_key":"m", "module_code":"superconductive_properties", "records":[record()]}]}]}


def context():
    return build_context([{"file_id":"main", "file_role":"main", "chunk_index":0, "page_start":5,
        "content":"For LaSc2H24, phonons and EPC use a 24×24×24 k grid and 90 Ry. All pressures use these settings."}])


def candidate(d=None):
    d = d or draft()
    return {"target":"s/m/r", "expected_fingerprint":scientific_fingerprint(d['material_states'][0]['property_modules'][0]['records'][0]),
            "target_path":"/payload/calculation_conditions/k_grid", "value":"24×24×24", "version":1,
            "basis_kind":"paper_inference", "stage":"electron_phonon", "scope":{"material":"LaSc2H24"},
            "reported_value_raw":"24×24×24", "unit_raw":"1",
            "fact_evidences":[{"file_id":"main", "chunk_index":0, "quote":"24×24×24 k grid"}],
            "scope_evidences":[{"file_id":"main", "chunk_index":0, "quote":"All pressures use these settings."}],
            "explanation":"Methods 的 EPC 设置适用于同一物相的各压力结果；局部例外优先。"}


def test_nested_fill_protects_existing_values_and_is_idempotent():
    d = draft()
    original = deepcopy(d)
    applied, gaps = apply_associations(d, [candidate(d)], context())
    assert len(applied) == 1 and not gaps
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    assert r['payload']['parameters'] == original['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters']
    assert r['payload']['calculation_conditions']['k_grid'] == '24×24×24'
    assert r['record_key'] == 'r' and r['record_checksum']
    assert not association_issues(r)
    again = deepcopy(d)
    assert not apply_associations(d, [candidate(d)], context())[0]
    assert d == again
    c = candidate(d)
    c['value'] = '12×12×12'
    assert apply_associations(d, [c], context())[1][0]['reason'] in {'condition_conflict', 'quote_unlocated'}


@pytest.mark.parametrize('change,reason', [
    ({'fact_evidences':[{'file_id':'main','quote':'invented 100 Ry'}]}, 'quote_unlocated'),
    ({'scope':{'material':'H3S'}}, 'scope_ambiguous'),
    ({'scope':{'material':'LaSc2H24','pressure_value_gpa':300}}, 'scope_ambiguous'),
    ({'stage':'aimd'}, 'scope_ambiguous'),
    ({'target_path':'/value_min'}, 'scope_ambiguous'),
    ({'expected_fingerprint':'wrong'}, 'target_stale'),
    ({'basis_kind':'general_knowledge'}, 'scope_ambiguous'),
])
def test_rejects_unsupported_associations(change, reason):
    d = draft()
    c = candidate(d) | change
    assert apply_associations(d, [c], context())[1][0]['reason'] == reason
    assert not d['material_states'][0]['property_modules'][0]['records'][0]['payload']['calculation_conditions']


def test_conflicting_candidates_do_not_depend_on_response_order():
    d = draft()
    c = candidate(d)
    assert not apply_associations(d, [c, c | {'value':'12×12×12'}], context())[0]


def test_full_windows_cache_retry_and_cancellation(tmp_path):
    ctx = build_context([{'file_id':'main','chunk_index':i,'content':f'Full source block {i}.'} for i in range(6)], max_chars=300)
    assert len(ctx['windows']) > 1
    assert sum(len(w['sources']) for w in ctx['windows']) == 6
    calls = []
    def model(system, body, **kwargs):
        calls.append(body)
        if len(calls) == 1:
            raise ValueError('bad response')
        return {'settings':[]}
    ledger = read_context(ctx, model, cache_dir=tmp_path, model_identity={'model':'test'})
    assert ledger['complete'] and len(calls) == len(ctx['windows']) + 1
    read_context(ctx, model, cache_dir=tmp_path, model_identity={'model':'test'})
    assert len(calls) == len(ctx['windows']) + 1
    read_context(ctx, model, cache_dir=tmp_path, model_identity={'model':'different'})
    assert len(calls) > len(ctx['windows']) + 1
    def cancel():
        raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError, match='cancelled'):
        read_context(ctx, model, ensure_active=cancel)


def test_incomplete_source_never_fills_and_failed_window_is_reported():
    ctx = context()
    ledger = read_context(ctx, lambda *a, **kw: (_ for _ in ()).throw(ValueError('failed')))
    assert not ledger['complete'] and ledger['gaps'][0]['reason'] == 'generation_failed'
    d = draft()
    assert apply_associations(d, [candidate()], ctx | {'complete':False})[1][0]['reason'] == 'context_incomplete'


def test_metadata_stales_on_manual_scientific_edit_and_rejects_status_flags():
    d = draft()
    apply_associations(d, [candidate()], context())
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    old = r['payload']['source_associations'][0]['target_fingerprint']
    assert old == scientific_fingerprint(r)
    r['value_min'] = 280
    assert old != scientific_fingerprint(r)
    r['payload']['source_associations'][0]['supported'] = True
    assert association_issues(r)


def test_table_bundle_keeps_rows_and_cross_page_note_without_assuming_scope():
    pages = [{'geometry':{'pdf_page':p}, 'blocks':[{'block_id':f'b{p}', 'pdf_page':p, 'text':text}],
              'tables':([{'table_id':'t','block_id':'b1','pdf_page':1,'row_count':2,'cells':[{'block_id':'b1','row_index':1,'column_index':0}]}] if p==1 else [])}
             for p, text in [(1,'Table 1 header and row'),(2,'Table 1 continued. μ*=0.16 to 0.1')]]
    bundles = table_packages({'file_id':'main','pages':pages})
    assert bundles[0]['rows'][0]['row_index'] == 1
    assert {b['block_id'] for b in bundles[0]['context_candidates']} == {'b1','b2'}
    assert bundles[0]['association_status'] == 'requires_source_reading'


def test_shared_pressures_local_exception_and_stage_are_not_broadcast():
    d=draft()
    second=deepcopy(d['material_states'][0])
    second.update(state_key='s2',pressure_value_gpa=300)
    second['property_modules'][0]['records'][0]['payload']['calculation_conditions']['k_grid']='12×12×12'
    d['material_states'].append(second)
    c=candidate(d)
    c2=c | {'target':'s2/m/r','expected_fingerprint':scientific_fingerprint(second['property_modules'][0]['records'][0])}
    applied,gaps=apply_associations(d,[c,c2],context())
    assert len(applied)==1 and gaps[0]['reason']=='condition_conflict'
    assert second['property_modules'][0]['records'][0]['payload']['calculation_conditions']['k_grid']=='12×12×12'
    c3=candidate(d) | {'stage':'sscha','target_path':'/payload/calculation_conditions/extensions/-',
        'value':{'key':'sscha.k_grid','value_kind':'text','value_raw':'24×24×24'}}
    d['material_states'][0]['property_modules'][0]['records'][0]['payload']['approximation']='harmonic'
    c3['expected_fingerprint']=scientific_fingerprint(d['material_states'][0]['property_modules'][0]['records'][0])
    assert apply_associations(d,[c3],context())[1][0]['reason']=='scope_ambiguous'


def test_reference_only_source_and_unreported_numeric_value_cannot_fill():
    d=draft()
    c=candidate(d) | {'target_path':'/payload/calculation_conditions/extensions/-','value':{
        'key':'electron_phonon.energy_cutoff','value_kind':'number','value_number':100,'value_raw':'100','unit_raw':'Ry'}}
    assert apply_associations(d,[c],context())[1][0]['reason']=='quote_unlocated'
    ctx=context()
    for s in ctx['sources']:s['section_role']='reference'
    assert apply_associations(d,[candidate(d)],ctx)[1][0]['reason']=='quote_unlocated'


def test_whole_source_reference_restores_exact_text_and_decimal_hash_stays_stable():
    from decimal import Decimal
    from backend.ingest.scientific_context import located
    ctx=context()
    e=located({'source_id':ctx['sources'][0]['source_id']},ctx['sources'])
    assert e['quote']==ctx['sources'][0]['content']
    assert not located({'source_id':ctx['sources'][0]['source_id'],'block_id':'forged'},ctx['sources'])
    r=record()
    before=scientific_fingerprint(r)
    r['value_min']=Decimal('281.0000000000')
    assert scientific_fingerprint(r)==before


def test_atomic_assignment_copies_verified_values_and_protects_model_targets():
    from backend.ingest.scientific_context import generate_context_associations
    d=draft();ctx=context()
    def model(system,body,**kw):
        import json
        data=json.loads(body)
        if 'sources' in data:
            return {'settings':[{'key':'k_grid','value':'24×24×24','stage':'electron_phonon','scope':{},
                'reported_value_raw':'24×24×24','unit_raw':'1','fact_evidences':[{'source_id':data['sources'][0]['source_id']}],
                'scope_evidences':[{'source_id':data['sources'][0]['source_id']}],'explanation':'明确报告的网格'}]}
        return {'assignments':[{'setting_id':'setting-0','targets':[data['targets'][0]['target'],'forged/target'],
                'basis_kind':'paper_inference','scope':{'material':'LaSc2H24'},'value':'invented value ignored',
                'explanation':'Methods 明确说明各压力沿用同样的 EPC 设置，仍需核对局部例外。'}]}
    ledger=generate_context_associations(d,ctx,model)
    assert ledger['complete'] and ledger['gaps'][0]['reason']=='target_stale'
    assert ledger['associations'][0]['value']=='24×24×24'
    assert apply_associations(d,ledger['associations'],ctx)[0]


def test_large_table_row_groups_repeat_original_context_without_cutting_cells():
    import json
    from backend.ingest.scientific_context import split_table_page
    cells=[{'row_index':i,'column_index':0,'block_id':f'cell-{i}'} for i in range(12)]
    blocks=[{'block_id':f'cell-{i}','text':('original-cell-'+str(i))*35} for i in range(12)]
    caption={'block_id':'caption','text':'Table 1. Original note and units.'}
    page={'geometry':{'pdf_page':4},'blocks':[caption,*blocks],
          'tables':[{'table_id':'t','row_count':12,'pdf_page':4,'cells':cells}]}
    encode=lambda pages:json.dumps(pages)
    parts=split_table_page(page,encode,2200)
    assert len(parts)>1
    assert [i for part in parts for group in part['row_groups'] for i in group['row_indices']]==list(range(12))
    assert all(caption in p['blocks'] and blocks[0] in p['blocks'] for p in parts)
    assert all(b in [caption,*blocks] for p in parts for b in p['blocks'])


def test_changed_document_hash_invalidates_even_when_old_quote_survives():
    from backend.ingest.scientific_context import bind_snapshot_source_documents
    from backend.ingest import property_evidence as ev
    ctx=context()
    ctx['sources'][0]['source_sha256']='a'*64
    d=draft()
    apply_associations(d,[candidate(d)],ctx)
    rows=[r for r in ev.draft_records(d,{}) if r['kind']=='property']
    snap=ev.complete_snapshot('upload','task',rows,ctx['sources'],d)
    bind_snapshot_source_documents(snap,{'main':{'sha256':'a'*64,'role':'main'}})
    before=snap['version']
    assert not snap['records'][0]['source_associations'][0]['stale']
    bind_snapshot_source_documents(snap,{'main':{'sha256':'a'*64,'role':'main'}})
    assert snap['version']==before
    bind_snapshot_source_documents(snap,{'main':{'sha256':'b'*64,'role':'main'}})
    assert snap['records'][0]['source_associations'][0]['stale']
    assert snap['version']!=before


def test_derived_space_group_number_is_equivalent_but_pressure_or_phase_changes_stale():
    from backend.ingest.scientific_context import state_fingerprint
    s={'material':'LaSc2H24','pressure_value_gpa':150,'reported_space_group_symbol':'P6/mmm'}
    before=state_fingerprint(s)
    assert state_fingerprint(s|{'reported_space_group_number':191})==before
    assert state_fingerprint(s|{'reported_space_group_number':225})!=before
    assert state_fingerprint(s|{'pressure_value_gpa':300})!=before
