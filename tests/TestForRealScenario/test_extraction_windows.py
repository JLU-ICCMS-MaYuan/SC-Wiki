"""真实SI表S1分段：完整原行、表头、邻页条件及来源身份不能丢失。"""
import json
from pathlib import Path

import pytest

from backend.ingest.document_ir import DocumentIR
from backend.ingest.domain_extraction import structured_chunks
from backend.ingest.document_parsers import ParserError


def source():
    return DocumentIR.model_validate_json((Path(__file__).parent /
        'fixtures/labeh8-table-s1-ir.json').read_text())


def test_default_window_splits_actual_s1_without_losing_rows_or_original_blocks():
    ir = source()
    chunks = structured_chunks(ir)
    assert len(chunks) >= 4
    assert all(len(c.content) < 90000 for c in chunks)
    contexts = [json.loads(c.content) for c in chunks]
    original = {b.block_id: b.text for b in ir.blocks}
    seen = {b['block_id']: b['text'] for c in contexts for p in c['pages'] for b in p['blocks']}
    assert set(seen) == set(original)
    # 空的表父块仅避免同一表文字重复；所有真实单元格原文逐字保留。
    parents = {t.block_id for t in ir.tables}
    assert all(text == original[key] for key, text in seen.items() if key not in parents)
    table = ir.tables[0]
    parts = [p for c in contexts for p in c['pages'] if p.get('row_groups')]
    rows = {i for p in parts for g in p['row_groups'] for i in g['row_indices']}
    assert rows == {cell.row_index for cell in table.cells}
    header_ids = {c.block_id for c in table.cells if c.row_index == 0}
    assert all(header_ids <= {b['block_id'] for b in p['blocks']} for p in parts)
    for c in contexts:
        if any(p.get('row_groups') for p in c['pages']):
            assert {20, 22} <= {p['geometry']['pdf_page'] for p in c['pages']}
        assert c['source_sha256'] == ir.source_sha256


def test_explicit_small_window_keeps_hard_limit_for_an_indivisible_original_block():
    ir = source()
    block = next(b for b in ir.blocks if b.block_type == 'paragraph')
    ir = ir.model_copy(update={'pages':[p for p in ir.pages if p.pdf_page == block.pdf_page],
        'blocks':[block.model_copy(update={'text':'original text ' * 5000})], 'tables':[]})
    chunks = structured_chunks(ir, window_chars=48000)
    assert len(chunks) == 1 and 48000 < len(chunks[0].content) < 500000
    assert json.loads(chunks[0].content)['pages'][0]['blocks'][0]['text'] == ir.blocks[0].text
    with pytest.raises(ParserError, match='单页'):
        structured_chunks(ir, max_chars=50000, window_chars=48000)


def test_hard_limit_is_not_silently_raised_to_fit_context():
    ir = source()
    with pytest.raises(ParserError):
        structured_chunks(ir, max_chars=20)
