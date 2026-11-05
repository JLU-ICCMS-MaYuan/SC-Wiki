"""覆盖处置必须逐项完整，不把未知身份或遗漏当成合法的部分答卷。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest


def captured():
    return json.loads((Path(__file__).parent / 'fixtures/lah-coverage-40-to-34.json').read_text())


def test_real_forty_to_thirty_four_response_is_rejected_instead_of_returning_partial_decisions(monkeypatch):
    from backend.ingest.domain_extraction import classify_uncovered
    from backend.rag import llm
    from backend.rag.structured_output import StructuredOutputError
    sample = captured()
    monkeypatch.setattr(llm, 'complete_json', lambda *args, **kwargs: sample['filtered_response'])
    with pytest.raises(StructuredOutputError):
        classify_uncovered(sample['items'])


@pytest.mark.parametrize('fault', ['duplicate', 'foreign', 'empty_reason', 'unknown_category'])
def test_control_response_rejects_invalid_identity_and_disposition(monkeypatch, fault):
    from backend.ingest.domain_extraction import classify_uncovered
    from backend.rag import llm
    from backend.rag.structured_output import StructuredOutputError
    sample = captured()
    items = sample['items'][:2]
    answer = {'items': deepcopy(sample['filtered_response']['items'][:2])}
    if fault == 'duplicate': answer['items'][1]['id'] = answer['items'][0]['id']
    elif fault == 'foreign': answer['items'][1]['id'] = 'block:another-document'
    elif fault == 'empty_reason': answer['items'][1]['reason'] = ''
    else: answer['items'][1]['category'] = 'invented'
    monkeypatch.setattr(llm, 'complete_json', lambda *args, **kwargs: answer)
    with pytest.raises(StructuredOutputError): classify_uncovered(items)


def test_strict_single_call_preserves_needs_extraction_and_program_owned_locators(monkeypatch):
    from backend.ingest.domain_extraction import classify_uncovered
    from backend.rag import llm
    from backend.rag.structured_output import validate_output
    sample = captured()
    items = sample['items'][:2]
    answer = {'items': [
        {'id': items[0]['id'], 'decision': 'exclude', 'category': 'reference_or_background', 'reason': 'Bibliographic reference.'},
        {'id': items[1]['id'], 'decision': 'needs_extraction', 'category': None, 'reason': 'Actual result still needs extraction.'}]}
    calls = []
    def model(system, payload, **options):
        calls.append(options)
        assert json.loads(payload)['items'] == items
        validate_output(answer, options['response_schema'])
        return answer
    monkeypatch.setattr(llm, 'complete_json', model)
    result = classify_uncovered(items)
    assert len(calls) == 1 and calls[0]['retries'] == 2
    assert result[1]['decision'] == 'needs_extraction'
    assert all(row['file_id'] == item['file_id'] and row['block_id'] == item['block_id'] for row, item in zip(result, items))


def test_each_failed_transport_receipt_keeps_partial_text_without_exception_message(monkeypatch):
    from backend.ingest.domain_extraction import classify_uncovered
    from backend.rag import llm
    events = []
    def model(*args, **options):
        options['on_partial']('{"items":[')
        options['on_call']({'attempt': 1, 'status': 'failed', 'error_type': 'RuntimeError'})
        raise RuntimeError('credential-sentinel-must-not-be-recorded')
    monkeypatch.setattr(llm, 'complete_json', model)
    with pytest.raises(RuntimeError): classify_uncovered(captured()['items'], on_event=events.append)
    assert events[0]['partial_response'] == '{"items":['
    assert 'credential-sentinel' not in json.dumps(events)
