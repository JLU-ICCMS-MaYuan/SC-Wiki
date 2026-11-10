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


def test_partial_repair_must_not_replace_complete_structure_report(tmp_path):
    from backend.ingest.structure_reading import extract_structure_candidates
    path = tmp_path / 'two-structures.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), '\n'.join([
            'NaCl 10 GPa Pm-3m fractional coordinates',
            'a = b = c = 5.64 Angstrom', 'alpha = beta = gamma = 90 degree',
            'Na 0.000 0.000 0.000', 'Cl 0.500 0.500 0.500',
            'KCl 20 GPa Pm-3m coordinates', 'K 0.000 0.000 0.000']))
        pdf.save(path)
    source = {'file_id': 'si', 'role': 'supplementary', 'filename': path.name,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    calls, initial = [], []
    class Captured(Exception):
        pass
    def model(system, payload, **options):
        request = json.loads(payload)
        calls.append(request)
        if len(calls) == 1:
            args = {'file_id': 'si', 'page': 1}
            return {'action': {'name': 'read_original_page', 'arguments': args}, '_tool_call': {
                'id': 'page', 'type': 'function', 'function': {'name': 'read_original_page', 'arguments': json.dumps(args)}}}
        rows = request['sources']
        def ref(prefix):
            return next(row['source_id'] for row in rows if row['content'].startswith(prefix))
        if len(calls) == 2:
            for material, pressure, element, mode in [('NaCl', 10, 'Na', 'fractional'), ('KCl', 20, 'K', 'unknown')]:
                initial.append({'material': material, 'pressure_value_gpa': pressure, 'space_group_symbol': 'Pm-3m',
                    'coordinate_mode': mode, 'length_unit': 'angstrom', 'angle_unit': 'degree',
                    'position_unit': 'dimensionless', 'cell_parameters': dict(a=5.64,b=5.64,c=5.64,alpha=90,beta=90,gamma=90),
                    'cell_source_ids': [ref('a ='), ref('alpha =')], 'source_ids': [ref(material + ' ')],
                    'atoms': [{'element': element, 'coordinates': [0,0,0], 'source_id': ref(element + ' ')},
                              {'element': 'Cl', 'coordinates': [.5,.5,.5], 'source_id': ref('Cl ')}],
                    'uncertainties': [], 'reason': '保留当前原页的结构行和坐标类型。'})
            items = initial
        elif len(calls) == 3:
            items = [initial[1]]  # 模型只回答了有问题的邻项。
        else:
            receipt = json.loads(options['tool_history'][-1]['content'])
            assert receipt['missing_structures'][0]['material'] == 'NaCl'
            assert len(receipt['required_report_inventory']) == 2
            assert '完整' in receipt['required_next_step']
            raise Captured()
        result = {'structures': items, 'uncertainties': [], 'reason': '报告已读原表'}
        return {'action': {'name': 'report_structures', 'arguments': result}, '_tool_call': {
            'id': f'report-{len(calls)}', 'type': 'function', 'function': {
                'name': 'report_structures', 'arguments': json.dumps(result)}}}
    with pytest.raises(Captured):
        extract_structure_candidates('', source=source, pdf_path=path, model=model)


def test_report_inventory_keeps_independent_same_condition_source_slots():
    from copy import deepcopy
    from backend.ingest.structure_reading import _missing_structure_reports
    first = dict(material='XH6', pressure_value_gpa=200, space_group_symbol='P1',
        source_ids=['table'], cell_source_ids=['shared-cell'], atoms=[{'source_id': 'method-a-sites'}])
    second = {**first, 'atoms': [{'source_id': 'method-b-sites'}]}
    assert _missing_structure_reports([first, second], [first, deepcopy(first)]) == [second]
    assert _missing_structure_reports([first, second], [second, first]) == []
    # 原项的相同完整来源允许纠正条件；本检查不合并或恢复科学值。
    corrected = {**first, 'space_group_symbol': 'P-1'}
    assert _missing_structure_reports([first], [corrected]) == []
