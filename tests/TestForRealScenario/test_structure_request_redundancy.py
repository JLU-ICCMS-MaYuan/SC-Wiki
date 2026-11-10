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
