"""结构请求保留全文与原生回执，同一已提供来源不再重复附带整行元数据。"""
import hashlib
import json

import pymupdf
import pytest


def test_real_read_document_receipt_references_current_sources_without_repeating_blocks(tmp_path):
    from backend.ingest.structure_reading import extract_structure_candidates, _native_document
    path = tmp_path / 'source.pdf'
    with pymupdf.open() as pdf:
        for index in range(3):
            page = pdf.new_page()
            for row in range(30):
                page.insert_text((40, 40 + row * 20), f'Original row {index}-{row}: reported number {row}.')
        pdf.save(path)
    source = {'file_id':'current-si','role':'supplementary','filename':path.name,
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    ir = _native_document(path, source)
    originals = {b.block_id:b.text for b in ir.blocks}
    requests, events = [], []
    class Captured(Exception):
        pass
    def model(_system, payload, **options):
        request = json.loads(payload)
        requests.append(request)
        rows = {r['source_id']:r for r in request['sources']}
        assert len(rows)==len(originals)
        assert {row['content'] for row in rows.values()} == set(originals.values())
        assert all(set(row)=={'source_id','pdf_page','content'} for row in rows.values())
        original_rows=events[-1]['original_context']['request']['sources']
        assert {row['block_id']:row['content'] for row in original_rows}==originals
        assert all(rows[row['source_id']]['pdf_page']==row['pdf_page'] for row in original_rows)
        if len(requests) == 1:
            return {'action':{'name':'read_document','arguments':{'file_id':'current-si'}},
                '_tool_call':{'id':'actual-read-document','type':'function',
                    'function':{'name':'read_document','arguments':'{"file_id":"current-si"}'}}}
        history = options['tool_history']
        assert history[0]['tool_calls'][0]['id'] == history[1]['tool_call_id'] == 'actual-read-document'
        receipt = json.loads(history[1]['content'])
        assert receipt['truncated'] is False
        assert 'blocks' not in receipt
        assert set(receipt['source_ids'])==set(rows)
        full_receipt=json.loads(events[-1]['original_context']['tool_history'][1]['content'])
        assert {b['block_id']:b['text'] for b in full_receipt['blocks']}==originals
        assert request['source_index']==[]
        raise Captured()
    with pytest.raises(Captured):
        extract_structure_candidates('', source=source, pdf_path=path, model=model,on_event=events.append)
    assert len(requests) == 2


def test_changed_or_unavailable_source_is_never_replaced_by_a_reference():
    from backend.ingest.structure_reading import _compact_structure_history
    blocks = [{'block_id':'same','pdf_page':1,'text':'actual original',
        'metadata':{'source_id':'s0'}},
        {'block_id':'changed','pdf_page':2,'text':'other actual text','metadata':{'source_id':'s1'}}]
    history = [{'role':'assistant','content':None,'tool_calls':[{'id':'native'}]},
        {'role':'tool','tool_call_id':'native','content':json.dumps({'blocks':blocks})}]
    before = json.dumps(history)
    read = {'s0':{'source_id':'s0','block_id':'same','pdf_page':1,'content':'actual original'},
        's1':{'source_id':'s1','block_id':'changed','pdf_page':2,'content':'different'}}
    compact = _compact_structure_history(history, read)
    assert json.dumps(history) == before
    result = json.loads(compact[1]['content'])['blocks']
    assert result[0] == {'source_id':'s0','block_id':'same','pdf_page':1}
    assert result[1] == blocks[1]
    assert _compact_structure_history(history, {}) == history


def test_structure_tool_aliases_roundtrip_exact_original_block_and_reject_unknown():
    from backend.ingest.structure_reading import structure_tool_transport
    block = 'pdf-row-' + 'a' * 32
    definitions = [{'type': 'function', 'function': {'name': 'read_region',
        'parameters': {'properties': {'block_id': {'type': 'string', 'enum': [block]}}}}}]
    before = json.dumps(definitions)
    catalog = {'structure-source-0': {'source_id': 'structure-source-0', 'block_id': block}}
    projected, restore = structure_tool_transport(definitions, catalog)
    assert projected[0]['function']['parameters']['properties']['block_id']['enum'] == ['structure-source-0']
    assert restore('read_region', {'file_id': 'si', 'block_id': 'structure-source-0'}) == {'file_id': 'si', 'block_id': block}
    with pytest.raises(ValueError):
        restore('read_region', {'file_id': 'si', 'block_id': 'unregistered'})
    assert restore('read_page', {'file_id': 'si', 'page': 1}) == {'file_id': 'si', 'page': 1}
    assert json.dumps(definitions) == before


def test_current_observation_is_referenced_only_when_matching_last_native_receipt():
    from backend.ingest.structure_reading import compact_model_context
    observation = {'verification_issues': [{'reason': 'original unresolved geometry'}]}
    history = [{'role': 'assistant', 'tool_calls': [{'id': 'native-current'}]},
        {'role': 'tool', 'tool_call_id': 'native-current', 'content': json.dumps(observation)}]
    request = {'sources': [], 'source_index': [], 'observation': observation}
    payload, messages = compact_model_context(request, history)
    assert payload['observation'] == {'observation_location': 'tool_history', 'tool_call_id': 'native-current'}
    assert json.loads(messages[-1]['content']) == observation
    assert request['observation'] == observation
    changed = {**request, 'observation': {'verification_issues': ['different current finding']}}
    assert compact_model_context(changed, history)[0]['observation'] == changed['observation']
    assert compact_model_context(request, [])[0]['observation'] == observation


@pytest.mark.parametrize('name', ['read_region', 'read_complete_object'])
def test_real_reader_restores_alias_before_document_or_image_tool(tmp_path, name):
    from backend.ingest.structure_reading import extract_structure_candidates, _native_document
    path = tmp_path / 'alias.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), 'Actual original PDF row.')
        pdf.save(path)
    source = {'file_id': 'si', 'role': 'supplementary', 'filename': path.name,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    original = _native_document(path, source).blocks[0]
    events, requests = [], []
    def model(system, payload, **options):
        request = json.loads(payload)
        requests.append(request)
        if len(requests) == 1:
            definition = next(d['function'] for d in options['tool_definitions'] if d['function']['name'] == name)
            alias = request['sources'][0]['source_id']
            assert alias in definition['parameters']['properties']['block_id']['enum']
            arguments = {'file_id': 'si', 'block_id': alias}
            return {'action': {'name': name, 'arguments': arguments}, '_tool_call': {
                'id': 'native-alias', 'type': 'function', 'function': {
                    'name': name, 'arguments': json.dumps(arguments)}}}
        receipt = json.loads(options['tool_history'][-1]['content'])
        assert 'tool_error' not in receipt
        assert options['tool_history'][-1]['tool_call_id'] == 'native-alias'
        if name == 'read_region':
            assert receipt['source_ids'] == [request['sources'][0]['source_id']]
        else:
            assert options['images'][0].startswith('data:image/png;base64,')
        return {'structures': [], 'uncertainties': [], 'reason': '验证原工具实际取源，不生成科学数据'}
    extract_structure_candidates('', source=source, pdf_path=path, model=model, on_event=events.append)
    audit = next(event['audit'] for event in reversed(events) if event['status'] == 'completed')
    assert any(row['status'] == 'completed' for row in audit)
    if name == 'read_region':
        assert audit[0]['arguments']['block_id'] == original.block_id



def test_incremental_schema_uses_distinct_ids_even_for_same_condition_sources():
    from backend.ingest.structure_reading import _repair_structure_schema, _schema, _apply_structure_updates
    from backend.rag.structured_output import output_format
    first = dict(material='XH6', pressure_value_gpa=200, space_group_symbol='P1',
                 source_ids=['table'], cell_source_ids=['cell'], atoms=[{'source_id':'method-a'}])
    second = {**first, 'atoms':[{'source_id':'method-b'}]}
    rows = {'first':{'status':'valid','structure':first},
            'second':{'status':'blocked','structure':second}}
    schema = _repair_structure_schema(_schema(['table','cell','method-a','method-b']), rows)
    output_format(schema)
    assert schema['properties']['updates']['items']['properties']['reading_id']['enum'] == ['second']
    updated = _apply_structure_updates([{'reading_id':'second','structure':second}], rows)
    assert updated == {'second':second}
    assert rows['first']['structure'] is first


def test_coverage_only_feedback_accepts_no_structure_rewrites():
    from jsonschema import Draft202012Validator
    from backend.ingest.structure_reading import _repair_structure_schema, _schema
    from backend.rag.structured_output import output_format
    schema = _repair_structure_schema(_schema(['source']), {'good':{'status':'valid'}})
    output_format(schema)
    Draft202012Validator(schema).validate({'updates':[], 'uncertainties':['仍有未读页'], 'reason':'只补覆盖范围'})
    assert schema['properties']['updates']['maxItems'] == 0
