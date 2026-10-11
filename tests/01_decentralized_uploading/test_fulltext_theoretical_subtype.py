"""#128：全文覆盖、支撑定位和 Methods-only 拒绝。"""

import json
import copy
from contextlib import nullcontext
from types import SimpleNamespace

from backend.ingest.theoretical_subtype import classify, rerun_ready_upload, task_sources
from backend.ingest.property_evidence import aggregate_candidates, checked_result, complete_snapshot
from backend.ingest.scientific_evidence import field_records, transfer_result, PAPER_FIELDS
from backend.rag.scientific_sources import source_chunk


def _sources():
    return [
        {"file_id": "main", "chunk_index": 0, "content": "Results We predict new phases and a transition temperature for H3S.",
         "page_start": 2, "page_end": 2, "section_role": "result"},
        {"file_id": "main", "chunk_index": 1, "content": "Methods We used the established USPEX code and DFT.",
         "page_start": 5, "page_end": 5, "section_role": "method"},
    ]


def test_fulltext_result_supports_calculation_with_contribution_quote():
    calls = []
    def model(_system, prompt):
        calls.append(json.loads(prompt))
        return {"value": "calculation", "reason": "主要贡献是用既有 USPEX/DFT 预测 H3S 物相和 Tc，而非提出新算法。",
                "evidences": [{"file_id": "main", "chunk_index": 0,
                               "quote": "We predict new phases and a transition temperature for H3S."}]}
    assessment = classify(_sources(), complete=model, model="fixture")
    assert len(calls) == 1 and len(calls[0]["sources"]) == 2
    assert assessment["status"] == "completed" and assessment["value"] == "calculation"
    assert assessment["evidences"][0]["section_role"] == "result"


def test_methods_only_or_unlocated_quote_cannot_support_subtype():
    for quote in ("We used the established USPEX code and DFT.", "fabricated quote"):
        assessment = classify(_sources(), complete=lambda *_: {
            "value": "calculation", "reason": "软件名称本身不足以决定类型。",
            "evidences": [{"file_id": "main", "chunk_index": 1, "quote": quote}]})
        assert assessment["status"] == "uncertain" and assessment["value"] is None


def test_method_quote_in_same_chunk_as_results_is_still_method_only():
    chunk = {"file_id": "main", "chunk_index": 0, "content":
             "Abstract\nA material is studied.\nResults\nA phase is predicted.\nMethods\nWe used VASP.",
             "section_role": "abstract", "page_start": 1, "page_end": 1}
    result = classify([chunk], complete=lambda *_: {
        "value": "calculation", "reason": "仅提到 VASP。",
        "evidences": [{"file_id": "main", "chunk_index": 0, "quote": "We used VASP."}]})
    assert result['status'] == 'uncertain'
    assert result['evidences'][0]['section_role'] == 'method'


def test_long_paper_reads_each_window_before_final_decision():
    chunks = [
        {"file_id": "main", "chunk_index": 0, "content": "Results " + "A" * 70000,
         "page_start": 1, "page_end": 1, "section_role": "result"},
        {"file_id": "supp", "chunk_index": 0, "content": "Discussion " + "B" * 70000,
         "page_start": 2, "page_end": 2, "section_role": "discussion"},
    ]
    calls = []
    def model(system, prompt):
        payload = json.loads(prompt)
        calls.append(payload)
        if "window_summaries" in payload:
            return {"value": "theory", "reason": "以新的理论机制推导为主要贡献。",
                    "evidences": [{"file_id": "main", "chunk_index": 0, "quote": "Results " + "A" * 20}]}
        return {"summary": "本组内容已阅读", "evidences": []}
    result = classify(chunks, complete=model)
    assert len(calls) == 3 and len(calls[2]["window_summaries"]) == 2
    assert result["covered_batches"] == result["total_batches"] == 2
    assert result["value"] == "theory"


def test_failure_leaves_value_empty_and_old_result_cannot_claim_support():
    def failed(*_):
        raise TimeoutError("model timeout")
    assessment = classify(_sources(), complete=failed)
    assert assessment["status"] == "failed" and assessment["value"] is None
    record = next(row for row in field_records('paper', 'paper', {'theoretical_subtype': 'calculation'}, PAPER_FIELDS)
                  if row['field'] == 'paper.theoretical_subtype')
    checked = checked_result(record, {"status": "supported", "reason": "Methods mention DFT",
                                      "evidences": [{"file_id": "main", "chunk_index": 1,
                                                     "quote": "We used the established USPEX code and DFT."}]}, _sources())
    assert checked["status"] == "uncertain"
    assert checked["source_kind"] != "paper_quote"


def test_verified_fulltext_reason_survives_field_check():
    assessment = classify(_sources(), complete=lambda *_: {
        "value": "calculation", "reason": "本文使用既有方法获得材料预测结果，并非开发新工具。",
        "evidences": [{"file_id": "main", "chunk_index": 0,
                       "quote": "We predict new phases and a transition temperature for H3S."}]})
    record = next(row for row in field_records('paper', 'paper', {'theoretical_subtype': 'calculation'},
                                               PAPER_FIELDS, assessment=assessment)
                  if row['field'] == 'paper.theoretical_subtype')
    checked = checked_result(record, {"status": "supported", "reason": "Methods mention DFT",
                                      "evidences": [{"file_id": "main", "chunk_index": 1,
                                                     "quote": "We used the established USPEX code and DFT."}]}, _sources())
    assert checked['status'] == 'supported'
    assert checked['source_kind'] == 'paper_synthesis'
    assert checked['ai_reason'] == assessment['reason']
    assert [item['section_role'] for item in checked['evidences']] == ['result']
    aggregated = aggregate_candidates([record], {record['key']: [checked]}, {record['key']: []}, 'fixture')
    assert aggregated[record['key']]['source_kind'] == 'paper_synthesis'


def test_sources_include_supplement_and_exclude_bibliography(tmp_path):
    root = tmp_path / 'markdown'
    folder = root / ('a' * 32)
    folder.mkdir(parents=True)
    (folder / 'main.md').write_text('Results\nWe predict a phase.\nReferences\nOthers predicted an earlier phase.')
    (folder / 'supp.md').write_text('Discussion\nAdditional simulations confirm the phase.')
    sources = task_sources('a' * 32, {'files': [
        {'file_id': 'main', 'role': 'main', 'kind': 'pdf'},
        {'file_id': 'supp', 'role': 'supplementary', 'kind': 'pdf'}]}, root)
    assert {item['file_id'] for item in sources} == {'main', 'supp'}
    assert not any('Others predicted' in item['content'] for item in sources)


def test_formal_rag_source_retains_synthesis_attribution():
    result = {'status': 'supported', 'required': True, 'label': '理论子类型',
              'current_value': 'calculation', 'evidences': [{'quote': 'We predict new phases.', 'page_start': 2}],
              'ai_reason': '使用已有计算工具研究材料结果。'}
    source = SimpleNamespace(id=7, paper_id=29, paper_revision=1,
                             field_path='paper.theoretical_subtype', result=result)
    chunk = source_chunk(source)
    assert chunk['source_kind'] == 'paper_synthesis'
    assert '全文' in chunk['attribution'] and '逐字记载' in chunk['attribution']


def test_targeted_rerun_preserves_human_value_and_clears_failed_ai_value(tmp_path, monkeypatch):
    from backend.ingest import upload_tasks
    from backend.rag import llm_context

    task_id = 'a' * 32
    root = tmp_path / 'markdown'
    (root / task_id).mkdir(parents=True)
    (root / task_id / 'main.md').write_text('Results\nWe introduce a new theory of pairing in this material.')
    artifact = tmp_path / 'result.json'
    state = {'stage': 'ready', 'processing_status': 'succeeded', 'filename': 'fixture.pdf',
             'user_id': 7, 'files': [{'file_id': 'main', 'role': 'main', 'kind': 'pdf'}]}
    stored = {'paper': {'paper_type': 'theoretical', 'theoretical_subtype': 'theory'}, 'material_states': []}
    artifact.write_text(json.dumps({'ai_values': {'paper': {'theoretical_subtype': 'calculation'}}}))
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _task: state)
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda _task: copy.deepcopy(stored))
    monkeypatch.setattr(upload_tasks, 'save_draft', lambda _task, value: stored.update(copy.deepcopy(value)))
    monkeypatch.setattr(upload_tasks, 'upload_task_lock', lambda _task: nullcontext())
    monkeypatch.setattr(upload_tasks, 'artifact_path', lambda _task: artifact)
    monkeypatch.setattr(upload_tasks, 'data_path', lambda _name: root)
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: SimpleNamespace(model='fixture'))
    result = rerun_ready_upload(task_id, expected_filename='fixture.pdf', complete=lambda *_: {
        'value': 'method', 'reason': '主要贡献是新的算法。',
        'evidences': [{'file_id': 'main', 'chunk_index': 0,
                       'quote': 'We introduce a new theory of pairing in this material.'}]})
    assert result['preserved_user_edit'] is True and stored['paper']['theoretical_subtype'] == 'theory'
    stored['paper']['theoretical_subtype'] = 'calculation'
    artifact.write_text(json.dumps({'ai_values': {'paper': {'theoretical_subtype': 'calculation'}}}))
    result = rerun_ready_upload(task_id, expected_filename='fixture.pdf',
                                complete=lambda *_: (_ for _ in ()).throw(TimeoutError()))
    assert result['assessment']['status'] == 'failed' and stored['paper']['theoretical_subtype'] is None


def test_only_subtype_evidence_identity_changes_with_fulltext_assessment():
    paper = {'paper_type': 'theoretical', 'theoretical_subtype': 'calculation', 'summary': 'Same paper'}
    before = complete_snapshot('upload', 'same', field_records('paper', 'paper', paper, PAPER_FIELDS), _sources(), paper)
    assessment = classify(_sources(), complete=lambda *_: {
        'value': 'calculation', 'reason': '本文使用现有方法得到材料预测。',
        'evidences': [{'file_id': 'main', 'chunk_index': 0,
                       'quote': 'We predict new phases and a transition temperature for H3S.'}]})
    after = complete_snapshot('upload', 'same', field_records('paper', 'paper', paper, PAPER_FIELDS,
                              assessment=assessment), _sources(), paper)
    prior = {r['field']: r['source_hash'] for r in before['records']}
    current = {r['field']: r['source_hash'] for r in after['records']}
    assert prior['paper.theoretical_subtype'] != current['paper.theoretical_subtype']
    assert all(prior[field] == current[field] for field in prior if field != 'paper.theoretical_subtype')


def test_upload_to_formal_source_keeps_reason_and_relocates_quotes():
    assessment = classify(_sources(), complete=lambda *_: {
        'value': 'calculation', 'reason': '本文以现有方法预测具体材料结果。',
        'evidences': [{'file_id': 'main', 'chunk_index': 0,
                       'quote': 'We predict new phases and a transition temperature for H3S.'}]})
    row = next(r for r in complete_snapshot('upload', 'sample', field_records('paper', 'paper',
        {'theoretical_subtype': 'calculation'}, PAPER_FIELDS, assessment=assessment), _sources(), {})['records']
        if r['field'] == 'paper.theoretical_subtype')
    checked = checked_result(row, {'status': 'supported', 'reason': '已核对全文', 'evidences': []}, _sources())
    formal_chunks = [{**chunk, 'file_id': '42', 'chunk_id': 100 + chunk['chunk_index']} for chunk in _sources()]
    transferred = transfer_result(row, checked, formal_chunks, {'main': '42'})
    assert transferred['status'] == 'supported'
    assert transferred['source_kind'] == 'paper_synthesis'
    assert transferred['ai_reason'] == assessment['reason']
    assert transferred['evidences'][0]['file_id'] == '42'
    assert transferred['provenance']['assessment']['evidences'][0]['file_id'] == '42'
    assert transferred['source_hash'] == row['source_hash']
