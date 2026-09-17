"""全科学数据核对的稳定身份、来源与持久结果契约。"""
from backend.ingest import scientific_evidence as science
from backend.ingest import property_evidence as ev


def test_unchecked_derived_input_is_not_reported_as_missing_and_human_input_is_traceable():
    records = science.state_records({'state_key':'Sn','material':'Sn','element_count':1}, 0)
    snap = ev.complete_snapshot('paper','29',records,[],{})
    result = ev.public_snapshot(snap,{})
    derived = next(r for r in result['records'] if r.get('kind') == 'derived')
    assert derived['status'] == 'unchecked'
    assert derived['provenance']['verified']
    material = next(r for r in snap['records'] if r['field'].endswith('.material'))
    decision = {'human_confirmed':True,'accepted':True,'actor_user_id':3,'reason':'Sn 表示锡元素，依据元素定义确认',
                'final_content_hash':material['content_hash'],'source_hash':material['source_hash']}
    result = ev.public_snapshot(snap,{material['key']:{'status':'unchecked','evidences':[],'decision':decision,'resolution':decision['reason']}})
    derived = next(r for r in result['records'] if r.get('kind') == 'derived')
    assert derived['human_confirmed'] and science.human_confirmed(derived)
    assert derived['decision']['derived_from'] == material['item_key']
    assert derived['evidences'] == []
    assert result['needs_check'] is False


def test_fusion_keeps_each_source_and_its_human_attribution():
    from backend.rag.core.prompts import build_fusion_prompt
    prompt = build_fusion_prompt('比较', rag_chunks=[
        {'paper_id':29,'content':'管理员确认的元素计数','attribution':'人工判断，论文未直接支持'},
        {'paper_id':9,'content':'论文原始测量值'},
    ])
    assert '管理员确认的元素计数' in prompt
    assert '人工判断，论文未直接支持' in prompt
    assert '论文原始测量值' in prompt


def test_scientific_fields_exclude_bibliography_and_empty_claims():
    rows = science.field_records('paper', 'paper', {
        'title': 'Bibliography', 'key_finding': 'Tc is 10 K', 'summary': '',
        'superconductor_kind': 'unknown', 'methodology': ['resistivity'],
    }, science.PAPER_FIELDS)
    assert {r['field'] for r in rows} == {'paper.key_finding', 'paper.methodology'}


def test_evidence_insertion_does_not_change_scientific_version():
    records = [dict(key='1', item_key='s/m/r', field='x', claim={'value': 10}, evidences=[])]
    before = ev.complete_snapshot('paper', '1', records, [], {})
    version = before['version']
    records[0]['evidences'] = [{'quote': 'Tc 10 K'}]
    after = ev.complete_snapshot('paper', '1', records, [], {})
    assert version == after['version']


def test_structure_source_is_not_a_paper_quote():
    record = dict(key='s', field='structure', evidences=[], provenance={
        'kind': 'contributor_structure', 'submitted_by_user_id': 7,
        'submitted_by_name': 'alice', 'structure_hash': 'abc', 'verified': True,
    })
    result = ev.checked_result(record, {'status': 'missing', 'reason': '论文未提供'}, [])
    assert result['status'] == 'uncertain'
    assert result['evidences'] == []
    assert '论文' in result['reason']
    assert result['provenance']['submitted_by_name'] == 'alice'


def test_unknown_structure_provider_cannot_override_missing():
    record = dict(key='s', field='structure', evidences=[], provenance={
        'kind': 'contributor_structure', 'submitted_by_user_id': None, 'verified': True,
    })
    assert ev.checked_result(record, {'status': 'missing'}, [])['status'] == 'missing'


def test_item_hash_is_stable_and_distinguishes_same_local_keys():
    assert science.item_identity('state-a', 'module', 'record') != science.item_identity('state-b', 'module', 'record')
    assert science.item_identity('a/b', 'c') != science.item_identity('a', 'b/c')


def test_derived_mismatch_cannot_be_overridden_by_model_support():
    record = science.state_records({"state_key": "s", "material": "Sn", "element_count": 2}, 0)
    for row in record:
        row.update(status="supported", evidences=[{"quote": "Sn"}])
    derived = next(r for r in science.apply_derived(record) if r["kind"] == "derived")
    assert derived["status"] == "missing"
    assert derived["evidences"] == []


def test_condition_change_invalidates_property_claim_but_evidence_insertion_does_not():
    record = {"record_key": "r", "payload": {"experimental_conditions": {"field_t": 1}}}
    before = science.record_claim(record, {"material": "Sn"})
    record["payload"]["experimental_conditions"]["field_t"] = 2
    assert science.record_claim(record, {"material": "Sn"}) != before


def test_pressure_conversion_requires_source_and_program_rechecks_value():
    rows = science.state_records({"state_key": "s", "pressure_raw": "100", "pressure_unit_raw": "MPa", "pressure_value_gpa": 0.1}, 0)
    for row in rows:
        row.update(status="supported", evidences=[{"quote": "100 MPa"}])
    result = next(r for r in science.apply_derived(rows) if r["kind"] == "derived")
    assert result["status"] == "supported"
    assert result["provenance"]["expected"] == "0.100"
    bad = science.state_records({"state_key": "s", "pressure_raw": "100", "pressure_unit_raw": "MPa", "pressure_value_gpa": 100}, 0)
    for row in bad:
        row.update(status="supported", evidences=[{"quote": "100 MPa"}])
    assert next(r for r in science.apply_derived(bad) if r["kind"] == "derived")["status"] == "missing"
