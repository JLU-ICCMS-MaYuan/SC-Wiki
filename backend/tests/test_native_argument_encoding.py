import json
from pathlib import Path
import pytest


def test_actual_complete_native_object_with_one_extra_closer_preserves_every_value():
    from backend.rag.structured_output import decode_tool_arguments
    fixture = json.loads((Path(__file__).parent/'fixtures/native-tool-extra-closer.json').read_text())
    raw = json.loads(fixture['partial_response'])['tool_calls'][0]['arguments']
    expected, end = json.JSONDecoder().raw_decode(raw)
    assert raw[end:] == '}'
    value, encoding = decode_tool_arguments(raw)
    assert value == expected and encoding['normalization'] == 'redundant_terminal_object_closer'
    assert value['panels'][0]['points'] == expected['panels'][0]['points']


@pytest.mark.parametrize('raw', ['{"x":1', '{"x":1}}}', '{"x":1} {"x":2}',
    '{"x":1} garbage', '{"x":1}]', '{"x":1,"x":2}}', '{"x":NaN}}', '[1]}'])
def test_recovery_never_fills_or_chooses_ambiguous_content(raw):
    from backend.rag.structured_output import decode_tool_arguments, StructuredOutputError
    with pytest.raises(StructuredOutputError): decode_tool_arguments(raw)


def test_canonical_input_is_unchanged_and_extra_fields_still_fail_original_schema():
    from backend.rag.structured_output import decode_tool_arguments, validate_tool_action, StructuredOutputError
    value, encoding = decode_tool_arguments('{"x":1}')
    assert value == {'x': 1} and encoding is None
    definitions = [{'type': 'function', 'function': {'name': 'tool', 'parameters': {
        'type': 'object', 'properties': {'required': {'type': 'number'}}, 'required': ['required'], 'additionalProperties': False}}}]
    recovered, _ = decode_tool_arguments('{"x":1}}')
    with pytest.raises(StructuredOutputError): validate_tool_action({'name': 'tool', 'arguments': recovered}, definitions)


@pytest.mark.parametrize('protocol', ['chat_completions', 'responses'])
def test_actual_sdk_stream_and_registered_chart_schema_keep_original_native_identity(monkeypatch, protocol):
    from types import SimpleNamespace as NS
    import httpx
    from openai import OpenAI
    from backend.rag import llm
    from backend.ingest.chart_reading import reading_schema
    fixture = json.loads((Path(__file__).parent/'fixtures/native-tool-extra-closer.json').read_text())
    raw = json.loads(fixture['partial_response'])['tool_calls'][0]['arguments']
    expected, _ = json.JSONDecoder().raw_decode(raw)
    config = NS(model='fixture', base_url='https://gateway.invalid', provider='fixture', api_protocol=protocol)
    sent = []
    def handle(request):
        sent.append(request.url.path)
        if protocol == 'chat_completions':
            events = [{'id': 'replay', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'fixture',
                'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'original-call', 'type': 'function',
                    'function': {'name': 'report_chart_reading', 'arguments': raw}}]}, 'finish_reason': 'tool_calls'}]}]
        else:
            events = [{'type': 'response.output_item.done', 'output_index': 0, 'item': {'id': 'fc',
                'type': 'function_call', 'call_id': 'original-call', 'name': 'report_chart_reading', 'arguments': raw}},
                {'type': 'response.completed', 'response': {'id': 'replay', 'status': 'completed', 'usage': None}}]
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
            content=''.join('data: '+json.dumps(event)+'\n\n' for event in events)+'data: [DONE]\n\n')
    client = OpenAI(api_key='isolated-placeholder', base_url=config.base_url,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)), max_retries=0)
    monkeypatch.setattr(llm, 'get_llm_config', lambda: config)
    monkeypatch.setattr(llm, '_client', lambda _: client)
    try:
        # 原失败使用其真实历史工具Schema；不把旧原生响应冒充含新坐标角色的回复。
        historical=json.loads((Path(__file__).parent/'fixtures/native-tool-extra-closer-schema.json').read_text())
        result = llm.complete_json('JSON', 'fixed replay', tool_definitions=[historical])
    finally: client.close()
    assert len(sent) == 1 and result['action']['arguments'] == expected
    assert result['_tool_call']['id'] == 'original-call' and result['_tool_call']['function']['arguments'] == raw
    assert result['_argument_encoding']['normalization'] == 'redundant_terminal_object_closer'
