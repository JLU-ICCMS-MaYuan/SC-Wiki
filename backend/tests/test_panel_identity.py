"""技术面板身份由服务器原图几何限定，不修补科学内容。"""
from copy import deepcopy


def test_missing_identity_uses_unique_closed_column_frame_without_rewriting_observations():
    from backend.rag.panel_identity import bind
    action={'name':'digitize_image_elements','arguments':{'region_id':'region','panel':{
        'figure':'Fig. S15','quantity':'lambda_ep','axis':{'bounds':[40,440]},
        'points':[{'x':860,'y':40,'pixel_error':3}]}}}
    context={'version':'program-panel-id-v1','default_region_id':'region','regions':{'region':{
        'source_sha256':'a'*64,'pdf_page':14,'localization_resolution':1,'band_candidates':[],
        'panel_frames':[{'bbox':[50,50,600,450]},{'bbox':[620,50,780,450]},
            {'bbox':[800,50,960,450]},{'bbox':[800,530,960,950]}]}}}
    before=deepcopy(action)
    bound,bindings=bind(action,context)
    assert bindings[0]['bbox']==[800,50,960,450]
    bound['arguments']['panel'].pop('panel')
    assert bound==before and action==before
    ambiguous=deepcopy(context)
    ambiguous['regions']['region']['panel_frames'].append({'bbox':[800,50,960,450]})
    with pytest.raises(StructuredOutputError):bind(action,ambiguous)
import pytest
from backend.rag.structured_output import validate_tool_action, StructuredOutputError

CONTEXT = {'version': 'program-panel-id-v1', 'default_region_id': 'region', 'regions': {
    'region': {'source_sha256': 'a'*64, 'pdf_page': 13, 'localization_resolution': .52,
               'band_candidates': [{'bbox': [0, 76.549, 1000, 344.598]},
                                   {'bbox': [0, 344.598, 1000, 611.367]}]}}}
DEFINITIONS = [{'type': 'function', 'function': {'name': 'digitize_image_elements', 'parameters': {
    'type': 'object', 'additionalProperties': False, 'required': ['region_id', 'panel'], 'properties': {
        'region_id': {'type': 'string', 'enum': ['region']}, 'panel': {'type': 'object',
            'additionalProperties': False, 'required': ['panel', 'axis'], 'properties': {
                'panel': {'type': 'string'}, 'axis': {'type': 'object'}}}}}}}]

def test_missing_panel_uses_unique_original_geometry_without_changing_values():
    action = {'name': 'digitize_image_elements', 'arguments': {'region_id': 'region',
        'panel': {'axis': {'bounds': [344.6, 611.4], 'ticks': [{'position': 400, 'value': 4}]}}}}
    original = deepcopy(action)
    with pytest.raises(StructuredOutputError): validate_tool_action(action, DEFINITIONS)
    bound, records = validate_tool_action(action, DEFINITIONS, argument_context=CONTEXT)
    assert bound['arguments']['panel']['panel'].startswith('panel-geometry-')
    bound['arguments']['panel'].pop('panel')
    assert bound == original and action == original
    assert records[0]['model_original_label'] is None

def test_existing_label_is_preserved_in_binding_and_identity_survives_point_changes():
    from backend.rag.panel_identity import remember
    context = deepcopy(CONTEXT)
    action = {'name': 'digitize_image_elements', 'arguments': {'region_id': 'region',
        'panel': {'panel': 'middle', 'axis': {'bounds': [344.6, 611.4]}}}}
    remember(context, [action['arguments']['panel']], 'region')
    action['arguments']['panel']['panel'] = 'printed-middle-label'
    bound, records = validate_tool_action(action, DEFINITIONS, argument_context=context)
    action['arguments']['panel']['axis']['bounds'] = [344.7, 611.3]
    second, _ = validate_tool_action(action, DEFINITIONS, argument_context=context)
    assert bound['arguments']['panel']['panel'] == second['arguments']['panel']['panel']
    assert records[0]['model_original_label'] == 'printed-middle-label'

@pytest.mark.parametrize('mode', ['ambiguous', 'outside', 'type', 'extra', 'region'])
def test_binding_never_hides_other_invalid_output(mode):
    context = deepcopy(CONTEXT)
    action = {'name': 'digitize_image_elements', 'arguments': {'region_id': 'region',
        'panel': {'axis': {'bounds': [344.6, 611.4]}}}}
    if mode == 'ambiguous': context['regions']['region']['band_candidates'].append(deepcopy(context['regions']['region']['band_candidates'][1]))
    if mode == 'outside': action['arguments']['panel']['axis']['bounds'] = [700, 800]
    if mode == 'type': action['arguments']['panel']['panel'] = None
    if mode == 'extra': action['arguments']['panel']['invented_science'] = 42
    if mode == 'region': action['arguments']['region_id'] = 'another'
    with pytest.raises(StructuredOutputError): validate_tool_action(action, DEFINITIONS, argument_context=context)


def test_real_si_missing_label_replay_preserves_every_scientific_value_and_source():
    from pathlib import Path
    import json
    from backend.ingest.chart_reading import reading_schema
    from backend.ingest.scientific_output_schema import obj
    saved = json.loads((Path(__file__).parent/'fixtures/panel_identity/si-s14-missing-panel.json').read_text())
    action, context = saved['action'], saved['context']
    definitions = [{'type': 'function', 'function': {'name': 'digitize_image_elements', 'parameters': obj({
        'region_id': {'type': 'string', 'enum': list(context['regions'])},
        'panel': reading_schema()['properties']['panels']['items']})}}]
    with pytest.raises(StructuredOutputError): validate_tool_action(action, definitions)
    bound, bindings = validate_tool_action(action, definitions, argument_context=context)
    assert bindings[0]['program_panel_id'] == 'panel-geometry-f27a865c2ba0c9aa'
    bound['arguments']['panel'].pop('panel')
    assert bound == action


def test_native_sdk_binding_keeps_original_tool_call_and_does_not_send_internal_context(monkeypatch):
    import json
    import httpx
    from openai import OpenAI
    from types import SimpleNamespace
    from backend.rag import llm
    raw = {'region_id': 'region', 'panel': {'axis': {'bounds': [344.6, 611.4]}}}
    sent = []
    def handle(request):
        sent.append(json.loads(request.content))
        chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'fixture',
            'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'delta': {'tool_calls': [{
                'index': 0, 'id': 'real-native-call', 'type': 'function', 'function': {
                    'name': 'digitize_image_elements', 'arguments': json.dumps(raw)}}]}}]}
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
            content='data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n')
    client = OpenAI(api_key='isolated-test', base_url='https://fixture.invalid',
                    http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(llm, '_client', lambda _: client)
    monkeypatch.setattr(llm, 'get_llm_config', lambda: SimpleNamespace(model='fixture', base_url='https://fixture.invalid'))
    try:
        result = llm._stream_json('Return JSON', 'source', images=None, on_partial=None,
            read_timeout=30, tool_definitions=DEFINITIONS, _tool_argument_context=CONTEXT)
    finally: client.close()
    assert result['action']['arguments']['panel']['panel'].startswith('panel-geometry-')
    assert json.loads(result['_tool_call']['function']['arguments']) == raw
    assert result['_tool_call']['id'] == 'real-native-call'
    assert '_tool_argument_context' not in sent[0]
