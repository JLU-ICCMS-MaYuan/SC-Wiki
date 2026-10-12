"""人工证据从对象存储读取，不依赖 API 与 Worker 共享目录。"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ingest import manual_evidence as manual
from backend.manual_evidence_models import ScientificManualEvidence
from backend.storage import FileRef, create_storage


def _snapshot(value: str) -> dict:
    return {"target": "upload", "target_id": "task", "records": [{
        "key": "field", "item_key": "stable-field", "field": "paper.authors",
        "content_hash": value, "source_hash": "source", "current_value": value,
    }]}


def test_manual_evidence_roundtrip_without_shared_directory(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path))
        monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path / "unmounted"))
        engine = create_engine("sqlite:///:memory:")
        ScientificManualEvidence.__table__.create(engine)
        try:
            with Session(engine) as session:
                old, current = _snapshot("old"), _snapshot("new")
                manual.save_explanation(session, current, old, "stable-field", 7,
                                        reason="按来源修正", no_evidence_reason="", text_items=[])
                image = io.BytesIO()
                Image.new("RGB", (4, 4), "white").save(image, format="PNG")
                saved = manual.add_file(session, current, old, "stable-field", 7,
                                        filename="source.png", raw=image.getvalue(), source_description="图示")
                row = session.get(ScientificManualEvidence, saved["id"])
                item = row.items[0]
                assert item["storage_key"].startswith("manual_evidence/")
                assert not (tmp_path / "unmounted").exists()
                _, _, temporary = manual.file_entry(session, current, "stable-field", item["id"])
                assert temporary.read_bytes() == image.getvalue()
                temporary.unlink()
                removed = manual.remove_file(session, current, "stable-field", item["id"], 7)
                assert isinstance(removed, FileRef)
                create_storage().delete(removed)
                assert boto3.client("s3", region_name="us-east-1").list_objects_v2(
                    Bucket="scwiki-storage-test").get("KeyCount", 0) == 0
        finally:
            engine.dispose()
