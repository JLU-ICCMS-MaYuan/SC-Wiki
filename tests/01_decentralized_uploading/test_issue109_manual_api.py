"""人工证据 API 的版本、文件与权限边界。"""

from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api import evidence
from backend.ingest import manual_evidence as manual
from backend.manual_evidence_models import ScientificManualEvidence
from backend.rag.llm_context import request_llm_config
from backend.security import get_current_user


ITEM_KEY = "a" * 64


def snapshots():
    before = {"target": "upload", "target_id": "task", "records": [{
        "key": "authors", "item_key": ITEM_KEY, "field": "paper.authors",
        "content_hash": "old", "source_hash": "source", "current_value": ["Defang Duan"],
    }]}
    current = {"target": "upload", "target_id": "task", "version": "v1", "records": [{
        "key": "authors", "item_key": ITEM_KEY, "field": "paper.authors",
        "content_hash": "new", "source_hash": "source", "current_value": ["Defang Duan", "Tian Cui"],
    }]}
    return current, before


def test_manual_api_saves_private_image_and_checks_version(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=__import__("sqlalchemy").pool.StaticPool)
    ScientificManualEvidence.__table__.create(engine)
    monkeypatch.setattr(evidence, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(evidence, "_manual_snapshots", lambda target, target_id, user: snapshots())
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    app = FastAPI()
    app.include_router(evidence.router)
    app.dependency_overrides[request_llm_config] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, username="uploader")
    client = TestClient(app)
    url = f"/api/rag/evidence/upload/task/manual/{ITEM_KEY}"

    assert client.get(url).json()["data"]["changed"] is True
    stale = client.put(url, json={"expected_version": "old", "reason": "依据截图"})
    assert stale.status_code == 409
    saved = client.put(url, json={"expected_version": "v1", "reason": "依据截图", "no_evidence_reason": ""})
    assert saved.status_code == 200
    image = BytesIO()
    Image.new("RGB", (3, 3), "white").save(image, format="PNG")
    uploaded = client.post(f"{url}/files", data={"expected_version": "v1", "source_description": "PDF 第 2 页截图"},
                           files={"file": ("screenshot.png", image.getvalue(), "image/png")})
    assert uploaded.status_code == 200
    item = uploaded.json()["data"]["items"][0]
    assert item["kind"] == "image"
    assert "storage_key" not in item
    downloaded = client.get(f"{url}/files/{item['id']}")
    assert downloaded.status_code == 200
    assert downloaded.content == image.getvalue()
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    monkeypatch.setattr(evidence, "_manual_snapshots", lambda target, target_id, user: (_ for _ in ()).throw(HTTPException(403, "forbidden")))
    assert client.get(f"{url}/files/{item['id']}").status_code == 403
    engine.dispose()
