"""真实第3组错误的固定结构反馈：不采用非法输出，不泄露原文值。"""
import pytest

from backend.ingest.scientific_output_schema import filling_schema
from backend.rag.structured_output import StructuredOutputError, validate_output


@pytest.mark.parametrize('invalid', ['missing', 'extra'])
def test_invalid_filling_values_report_schema_keys_without_echoing_model_content(invalid):
    schema = filling_schema()
    values_schema = schema['properties']['records']['items']['properties']['values']
    values = {name: None for name in values_schema['properties']}
    values.update(value_kind='number', value_number=.019, value_raw='~0.019 states/eV/Å^3')
    if invalid == 'missing':
        values.pop('value_boolean')
    else:
        values['value_kind_note'] = 'untrusted secret source text'
    answer = dict(done=True, read_source_ids=[], search=[], excluded=[], unresolved=[], records=[dict(
        candidate_ids=['s4:m0:r0'], group='LaH6', method='dos', values=values,
        source_ids=['source-56'], reason='Original calibrated plot')])
    with pytest.raises(StructuredOutputError) as failure:
        validate_output(answer, schema)
    message = str(failure.value)
    assert 'records.0.values' in message
    assert 'value_boolean' in message
    assert 'untrusted secret source text' not in message
    assert 'value_kind_note' not in message  # 不把模型生成的任意键名带回提示。

