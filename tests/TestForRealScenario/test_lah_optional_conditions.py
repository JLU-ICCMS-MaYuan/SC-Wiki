"""#205允许未提供的条件；程序需建立空的内部预测表单，而不重问模型。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import validate


def fixture():
    data=json.loads(Path(__file__).with_name('fixtures').joinpath('lah-null-conditions.json').read_text())
    blocks=data['blocks']
    options={'allowed_blocks':{(b['file_id'],b['pdf_page'],b['block_id']) for b in blocks},
        'allowed_quote_text':{(b['file_id'],b['pdf_page'],b['block_id']):b['text'] for b in blocks},
        'form_parameters':True}
    return data['response'],options


def test_legal_protocol_null_conditions_project_to_empty_internal_form():
    from backend.ingest.domain_extraction import EXTRACTION_OUTPUT_SCHEMA,normalize_extraction
    from backend.ingest.scientific_output_schema import decode_optional_containers
    raw,options=fixture();before=deepcopy(raw)
    validate(raw,EXTRACTION_OUTPUT_SCHEMA)  # 模型已按当前严格协议返回合法的null。
    result=normalize_extraction(decode_optional_containers(raw),**options)
    record=result['material_states'][0]['property_modules'][0]['records'][0]
    original=raw['material_states'][0]['property_modules'][0]['records'][0]
    assert record['payload']['calculation_conditions']=={}
    assert record['value_number']==original['value_number']
    assert record['payload']['parameters']['lambda_ep']==original['payload']['parameters']['lambda_ep']
    assert record['evidences'] and raw==before


def test_empty_projection_does_not_repair_illegal_scientific_keys():
    from backend.ingest.domain_extraction import normalize_extraction
    from backend.ingest.scientific_output_schema import decode_optional_containers
    raw,options=fixture()
    raw['material_states'][0]['property_modules'][0]['records'][0]['payload']['pressure_ambiguity']='illegal key'
    with pytest.raises(ValueError):normalize_extraction(decode_optional_containers(raw),**options)


def test_empty_projection_does_not_replace_nonempty_wrong_condition_type():
    from backend.ingest.domain_extraction import normalize_extraction
    from backend.ingest.scientific_output_schema import decode_optional_containers
    raw,options=fixture()
    raw['material_states'][0]['property_modules'][0]['records'][0]['payload']['calculation_conditions']='wrong type'
    with pytest.raises(ValueError):normalize_extraction(decode_optional_containers(raw),**options)
