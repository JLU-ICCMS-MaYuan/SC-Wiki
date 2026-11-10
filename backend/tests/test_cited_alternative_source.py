"""真实候选的Marker原文不得在填写交接时变成目录外来源。"""
import gzip
import json
import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from backend.ingest.document_ir import DocumentIR
from backend.ingest.scientific_context import build_context
from backend.ingest.scientific_form_filling import form_sources, _source_identity, _evidence


def test_actual_two_missing_originals_join_form_sources_without_routing_or_quote_change(tmp_path):
    value = json.loads(gzip.decompress((Path(__file__).parent /
        'fixtures/cited_alternative/failed-source-handoff.json.gz').read_bytes()))
    ir = DocumentIR.model_validate(value['document'])
    before = ir.model_dump(mode='json')
    missing = value['missing_evidences']
    assert len(missing) == 2
    actual = {_source_identity(source) for source in value['actual_read_sources']}
    assert all(_source_identity(evidence) not in actual for evidence in missing)
    files = [{'file_id': ir.source_file_id, 'file_role': 'main', 'content': ''}]
    documents = {ir.source_file_id: ir}
    primary = build_context(form_sources(documents, files))['sources']
    assert all(_source_identity(evidence) not in {_source_identity(s) for s in primary} for evidence in missing)
    sources = build_context(form_sources(documents, files, references=missing))['sources']
    by_id = {s['source_id']: s for s in sources}
    for evidence in missing:
        block = ir.block(evidence['block_id'])
        assert block.metadata['selected_for_reading'] is False
        assert block.metadata['source_parser'] == 'marker'
        ids = [s['source_id'] for s in sources if _source_identity(s) == _source_identity(evidence)]
        assert ids
        restored = _evidence(ids, by_id)
        assert all(row['quote'] == block.text for row in restored)
        assert all(_source_identity(row) == _source_identity(evidence) for row in restored)
        assert all(row['source_version'] == ir.source_version for row in restored)
    path = tmp_path / 'original-sources.json'
    path.write_text(json.dumps(sources, ensure_ascii=False))
    assert json.loads(path.read_text()) == sources
    assert ir.model_dump(mode='json') == before
