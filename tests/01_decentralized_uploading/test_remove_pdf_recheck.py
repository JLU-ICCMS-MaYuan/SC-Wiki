"""后置文字匹配不得撤回科学结果；正式持久化及重读使用外层回滚。"""
import os
from contextlib import nullcontext
from copy import deepcopy
from uuid import uuid4

import pymupdf
import pytest

from backend import database, models
from backend.ingest import field_review, property_evidence as ev, scientific_evidence as science, upload_tasks
from backend.ingest.document_parsers import DocumentSource
from test_scientific_evidence_mysql import current_mysql


@pytest.mark.skipif(os.getenv('SCWIKI_CURRENT_MYSQL') != '1', reason='显式启用本机MySQL外层回滚')
@pytest.mark.parametrize('target', ['upload', 'paper', 'revision'])
@pytest.mark.parametrize('status', ['supported', 'unsupported'])
def test_scientific_result_survives_save_and_read(current_mysql, monkeypatch, tmp_path, target, status):
    monkeypatch.setenv('FILE_STORAGE_BACKEND', 'local')
    path = tmp_path / 'source.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 60), 'CaH6 stabi- lizes above pressure 150 GPa.')
        pdf.save(path)
    draft = {'paper': {'paper_type': 'theoretical'}, 'material_states': [
        {'state_key': 'state', 'material': 'CaH6', 'pressure_value_gpa': 150}]}
    chunks = [{'file_id': 'main', 'chunk_index': 0,
               'content': 'CaH6 stabilizes above pressure 150 GPa. This is a theoretical prediction.'}]
    target_id = uuid4().hex
    if target == 'paper':
        with current_mysql.begin() as db:
            paper = models.Paper(title='isolated-pdf-recheck', year=2012,
                                 uploaded_by_user_id=2, review_status='pending')
            db.add(paper)
            db.flush()
            target_id = str(paper.id)
    snap = ev.complete_snapshot(target, target_id, ev.draft_records(draft, {}), chunks, draft)
    snap['records'] = [r for r in snap['records'] if r['field'] in {
        'paper.paper_type', 'material_states[0].pressure_value_gpa'}]
    snap['pdf_manifest'] = [{'file_id': 'main', 'role': 'main', 'kind': 'pdf', 'stored_path': str(path),
        'sha256': DocumentSource(path, 'main').resolved_sha256()}]
    results = {r['key']: ev.checked_result(r, {'status': status,
        'reason': '原文的理论预测在150 GPa下给出稳定性，支撑当前字段并保留适用压力。',
        'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': chunks[0]['content']}]}, chunks)
        for r in snap['records']}
    assert {r['status'] for r in results.values()} == {status}
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    monkeypatch.setattr(upload_tasks, 'upload_task_lock', lambda _: nullcontext())
    monkeypatch.setattr(ev, 'upload_snapshot', lambda *_a, **_kw: deepcopy(snap))
    monkeypatch.setattr(field_review, 'validate_support_versions', lambda *_a: None)
    from backend.services import paper_revisions
    monkeypatch.setattr(paper_revisions, 'revision_snapshot', lambda *_a: deepcopy(snap))
    snap['draft_version'] = 'isolated'
    ev.persist_completed_results(snap, results, 2)
    with current_mysql() as db:
        restored = science.load_results(db, snap, 2)
    assert len(restored) == 2
    for record in snap['records']:
        result = restored[record['key']]
        assert result['status'] == status
        assert result['evidences'][0]['quote'] == chunks[0]['content']
        assert not result.get('location_check')
        assert field_review.blocking(record, result) is (status != 'supported')


def test_extraction_still_rejects_invented_source():
    located, error = ev.locate_with_reason({'file_id': 'main', 'quote': 'invented 200 GPa'},
        [{'file_id': 'main', 'chunk_index': 0, 'content': 'CaH6 at 150 GPa.'}])
    assert located is None and error
