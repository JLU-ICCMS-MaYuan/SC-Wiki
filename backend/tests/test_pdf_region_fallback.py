from types import SimpleNamespace
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api import evidence
from backend.security import get_current_user
from backend.ingest import upload_tasks
from backend.ingest.document_regions import region_document
from backend.storage.files import FileNotFound as StorageFileNotFound


def pdf(tmp_path):
    import pymupdf
    path = tmp_path / 'source.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page();page.insert_text((40, 100), 'Quantum ESPRESSO uses a 24x24x24 k grid.')
        doc.save(path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def source(monkeypatch, tmp_path):
    path, digest = pdf(tmp_path)
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _: {'user_id': 2, 'files': [{'file_id': 'main', 'stored_path': str(path), 'sha256': digest, 'size': path.stat().st_size}]})
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda *_: (_ for _ in ()).throw(StorageFileNotFound('缺少可选IR')))
    monkeypatch.setattr('backend.ingest.document_regions.resolve_file', lambda *a, **kw: path)
    return path, digest


def test_missing_optional_object_ir_uses_same_authorized_pdf(monkeypatch, tmp_path):
    path, digest = source(monkeypatch, tmp_path)
    user = SimpleNamespace(id=2, role='user', is_approved=True)
    assert region_document(None, 'upload', 't', 'main', user) == (None, path, digest)
    for actor in [SimpleNamespace(id=3, role='user', is_approved=True), SimpleNamespace(id=3, role='admin', is_approved=False)]:
        with pytest.raises(Exception) as error:region_document(None, 'upload', 't', 'main', actor)
        assert error.value.status_code == 403
    assert region_document(None, 'upload', 't', 'main', SimpleNamespace(id=3, role='admin', is_approved=True))[1] == path


def test_real_region_route_is_model_independent_but_authenticated(monkeypatch, tmp_path):
    path, digest = source(monkeypatch, tmp_path)
    app = FastAPI();app.include_router(evidence.router)
    client = TestClient(app)
    body = {'target': 'upload', 'target_id': 't', 'file_id': 'main', 'quote': 'Quantum ESPRESSO uses a 24x24x24 k grid.', 'pdf_page': 1}
    assert client.post('/api/rag/evidence/region', json=body).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='user', is_approved=True)
    monkeypatch.setattr('backend.rag.llm_context.get_catalog', lambda: (_ for _ in ()).throw(AssertionError('原PDF不读取模型目录')))
    response = client.post('/api/rag/evidence/region', json=body, headers={'X-LLM-Config-ID': 'deleted-model'})
    assert response.status_code == 200
    assert response.json()['status'] == 'located'
    assert response.json()['crops'][0]['image'].startswith('data:image/png;base64,')
    bad = client.post('/api/rag/evidence/region', json={**body, 'file_id': 'other'})
    assert bad.status_code == 404
    unlocated = client.post('/api/rag/evidence/region', json={**body, 'quote': 'not in this paper'})
    assert unlocated.json()['status'] == 'unlocated'
    monkeypatch.setattr(evidence, 'snapshot_for', lambda *_: ({'version': 'v', 'records': [], 'chunks': []}, {}))
    assert client.post('/api/rag/evidence/preflight', json={'target': 'paper', 'target_id': '1'}, headers={'X-LLM-Config-ID': 'deleted-model'}).status_code == 200


def test_changed_source_hash_never_returns_a_different_or_stale_image(monkeypatch, tmp_path):
    path, digest = source(monkeypatch, tmp_path)
    from backend.ingest.document_regions import render_region
    path.write_bytes(path.read_bytes() + b' changed source')
    result = render_region(None, path, digest, quote='Quantum ESPRESSO uses a 24x24x24 k grid.', pdf_page=1)
    assert result['status'] == 'render_unavailable'
    assert not result.get('image') and not result.get('crops')
