"""已审核引用的保存只核验来源身份，不重新裁决内容。"""
from copy import deepcopy

import pytest

from backend.ingest import scientific_evidence as science


def test_reviewed_reference_survives_internal_pdf_markers():
    quote = 'The combined contribution gave an EPC parameter of 2.69.'
    chunks = [{'file_id': '42', 'chunk_id': 81, 'chunk_index': 3,
               'content': 'The combined contribution <!-- block: b --> gave an EPC parameter of 2.69.',
               'page_start': 3, 'page_end': 3}]
    value = {'evidences': [{'file_id': 'main', 'chunk_index': 3, 'quote': quote}]}
    moved = science.rebind_source_references(value, chunks, {'main': 42})
    assert len(moved['evidences']) == 1
    assert moved['evidences'][0]['chunk_id'] == 81
    assert moved['evidences'][0]['quote'] == quote


def test_synthesis_keeps_multiple_sources_and_reason_without_literal_match():
    chunks = [{'file_id': '42', 'chunk_id': index + 81, 'chunk_index': index,
               'content': text} for index, text in enumerate(['Introduction paragraph.', 'Discussion paragraph.'])]
    value = {'source_kind': 'paper_synthesis', 'reason': '综合引言与讨论的研究动机',
             'evidences': [{'file_id': 'main', 'chunk_index': index, 'quote': quote}
                          for index, quote in enumerate(['First reviewed context.', 'Second reviewed context.'])]}
    moved = science.rebind_source_references(value, chunks, {'main': 42})
    assert len(moved['evidences']) == 2
    assert moved['reason'] == value['reason'] and moved['source_kind'] == 'paper_synthesis'
    assert [e['quote'] for e in moved['evidences']] == [e['quote'] for e in value['evidences']]


@pytest.mark.parametrize('source', [
    {'file_id': 'missing', 'chunk_index': 0},
    {'file_id': 'main', 'chunk_index': 999},
])
def test_missing_reviewed_source_is_explicit_and_never_silently_dropped(source):
    chunks = [{'file_id': '42', 'chunk_id': 81, 'chunk_index': 0, 'content': 'Text.'}]
    value = {'evidences': [{**source, 'quote': 'Text.'}]}
    original = deepcopy(value)
    with pytest.raises(ValueError, match='来源'):
        science.rebind_source_references(value, chunks, {'main': 42})
    assert value == original


def test_external_bibliography_is_preserved_without_becoming_paper_text():
    source = {'file_id': 'crossref:10.1000/example', 'origin_kind': 'external_bibliography',
              'source_url': 'https://doi.org/10.1000/example', 'quote': 'Volume 1.'}
    value = {'evidences': [source]}
    assert science.rebind_source_references(value, [], {}) == value


@pytest.mark.parametrize('target', ['upload', 'revision', 'paper'])
def test_submission_reuses_synthesis_without_text_matching_or_model(monkeypatch, target):
    from backend.ingest import property_evidence as ev
    from backend.ingest.model_review import bind_result
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'Original research context.'}]
    snapshot = ev.complete_snapshot(target, '1', [{'key': 'summary', 'item_key': 'summary',
        'field': 'paper.summary', 'claim': {'value': 'A scientific synthesis.'},
        'current_value': 'A scientific synthesis.', 'required': True}], chunks, {})
    record = snapshot['records'][0]
    result = bind_result(record, {'status': 'supported', 'reason': '综合论文上下文',
        'source_kind': 'paper_synthesis', 'evidences': [{'file_id': 'main', 'chunk_index': 0,
            'quote': 'A reviewed description with different wording.'}]}, chunks)
    monkeypatch.setattr(ev, 'locate_with_reason', lambda *args: pytest.fail('入库不能再匹配引句文字'))
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *args, **kwargs: pytest.fail('入库不能再调用模型'))
    accepted = ev.resolve_results(snapshot, {record['key']: result}, 1, None, snapshot['version'])
    assert accepted[0]['status'] == 'supported'
    assert accepted[0]['evidences'][0]['quote'] == result['evidences'][0]['quote']


def test_source_identity_cannot_cross_files_even_with_identical_text():
    from backend.ingest.reviewed_sources import source_reference, SourceReferenceError
    chunks = [{'file_id': 'main', 'chunk_id': 1, 'chunk_index': 0, 'content': 'Same text.'},
              {'file_id': 'si', 'chunk_id': 2, 'chunk_index': 0, 'content': 'Same text.'}]
    with pytest.raises(SourceReferenceError):
        source_reference({'file_id': 'main', 'chunk_id': 2, 'quote': 'Same text.'}, chunks)


def test_rebinding_keeps_historical_quotes_without_claiming_current_support():
    history = [{'field': 'old', 'evidence': {'file_id': 'retired', 'quote': 'Historical text.'}}]
    value = {'evidences': [], 'legacy_source_history': history}
    assert science.rebind_source_references(value, [], {}) == value
