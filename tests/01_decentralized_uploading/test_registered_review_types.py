"""#203既有数值表达与字段审核采用同一类型规则。"""
import pytest
from backend.ingest.evidence_proposals import valid_value
from backend.ingest.fixed_form_contract import conditions_schema


@pytest.mark.parametrize('value,schema', [
    ([12, 12, 12], {'type': 'array', 'nullable': True}),
    ({'value_kind': 'number', 'value_number': 90, 'unit_raw': 'Ry'}, {'type': 'object', 'nullable': True}),
    ({'value_kind': 'number', 'value_number': 90, 'unit_raw': 'Ry', 'evidences': None},
     conditions_schema()['properties']['qe']['properties']['energy_cutoff']),
])
def test_registered_and_partial_schemas_do_not_crash_on_valid_current_values(value, schema):
    assert valid_value(value, schema)


def test_closed_registered_quantity_still_rejects_unknown_keys():
    schema = conditions_schema()['properties']['qe']['properties']['energy_cutoff']
    assert not valid_value({'value_number': 90, 'invented': 1}, schema)


def test_typed_items_and_nonfinite_numbers_still_fail():
    assert not valid_value(['wrong'], {'type': 'array', 'items': {'type': 'number'}})
    assert not valid_value(float('nan'), {'type': 'number'})


def test_same_numeric_representation_does_not_create_an_unaccepted_correction():
    from backend.ingest import property_evidence as ev
    from backend.ingest.model_review import review_fields
    row = {'key': 'pressure', 'item_key': 'pressure', 'field': 'material_states[0].pressure_value_gpa',
        'kind': 'field', 'label': '压力', 'current_value': 150.0, 'claim': {'value': 150.0}, 'required': True}
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'The pressure is 150 GPa.'}]
    snapshot = ev.complete_snapshot('upload', 'test', [row], chunks, {})
    result = review_fields(snapshot['records'], chunks, model=lambda *args, **kwargs: {'results': [{
        'key': 'pressure', 'status': 'supported', 'final_value': 150, 'source_ids': ['review-source-0'],
        'reason': '原文压力150GPa与当前值一致'}]})['pressure']
    assert result['status'] == 'supported' and result.get('proposal') is None
