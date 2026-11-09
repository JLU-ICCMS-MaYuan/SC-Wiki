"""同版本真实图片读取结果可复用，缺回执或摘要不符仍读取原图。"""
from copy import deepcopy

import json
import pytest

from backend.tests.test_chart_reading import original, fake_model
from backend.ingest.chart_reading import enrich_document
from backend.ingest.state_inventory import plan_states, FIELDS


@pytest.mark.parametrize('matching_receipt', [True, False])
def test_same_source_chart_receipt_avoids_repeated_pixels_without_losing_quotes(tmp_path, monkeypatch, matching_receipt):
    path, ir, source = original(tmp_path)
    enrich_document(ir, path, source, fake_model([]))
    block = next(b for b in ir.blocks if 'chart_reading' in b.metadata)
    if not matching_receipt:
        ir.coverage['chart_reading']['source_sha256'] = '0' * 64
    from backend.storage import paths
    monkeypatch.setattr(paths, 'resolve_file', lambda *_a, **_kw: path)
    evidence = {'file_id': 'main', 'block_id': block.block_id, 'pdf_page': 1, 'quote': block.text}
    record = {'record_key': 'r', 'record_type': 'predicted_tc', 'property_code': 'tc',
              'value_kind': 'number', 'value_number': 100, 'evidences': [evidence]}
    state = {'state_key': 's', 'material': 'YH10', 'material_name': 'YH10', 'state_kind': 'theoretical',
        'structure_optimization': 'unknown', 'pressure_value_gpa': None,
        'property_modules': [{'module_key': 'm', 'module_code': 'superconductive_properties', 'records': [record]}]}
    draft = {'material_states': [deepcopy(state)]}
    chunks = [{'file_id': 'main', 'block_id': b.block_id, 'page_start': 1, 'content': b.text}
              for b in ir.blocks if b.text]
    def model(_prompt, body, **options):
        request = json.loads(body)
        assert len(options.get('images') or []) == (0 if matching_receipt else 1)
        assert bool(request['reused_original_pages']) == matching_receipt
        reference = request['candidates'][0]['property_modules'][0]['records'][0]['evidences'][0]
        assert set(reference) == {'source_id', 'quote_span'}
        source = next(s for s in request['sources'] if s['source_id'] == reference['source_id'])
        a, b = reference['quote_span']
        assert source['content'][a:b] == evidence['quote']
        return {'states': [{'values': {k: (400 if k == 'pressure_value_gpa' else state.get(k)) for k in FIELDS},
            'reason': '实际来源说明400 GPa', 'source_ids': [reference['source_id']]}],
            'assignments': [{'candidate_state_key': 's', 'target_index': 0, 'status': 'supported',
                'reason': '原图结果对应本状态', 'source_ids': [reference['source_id']]}], 'record_assignments': []}
    plan_states(draft, chunks, model, documents={'main': ir},
        files=[{**source, 'kind': 'pdf', 'stored_path': str(path), 'size': path.stat().st_size}])
    assert draft['material_states'][0]['property_modules'][0]['records'][0] == record
