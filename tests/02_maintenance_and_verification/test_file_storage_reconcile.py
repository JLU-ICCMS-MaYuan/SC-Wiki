"""隔离库中验证文件清理只删除明确未引用的头像和人工证据。"""

from __future__ import annotations

from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.manual_evidence_models import ScientificManualEvidence
from backend.models import User
from backend.scripts import migrate_file_storage, reconcile_file_storage
from backend.storage.files import FileIntegrityError, S3FileStorage
from backend.storage.reference_inventory import FileInventoryError


def test_reconcile_is_readonly_by_default_and_preserves_live_files(monkeypatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    database_url = f"sqlite:///{tmp_path / 'cleanup.db'}"
    engine = create_engine(database_url)
    User.__table__.create(engine)
    ScientificManualEvidence.__table__.create(engine)
    row_id = "a" * 32
    live_id, stale_id = "b" * 32, "c" * 32
    avatar_live = f"files/avatars/7/{live_id}.jpg"
    avatar_stale = f"files/avatars/7/{stale_id}.jpg"
    manual_live = f"manual_evidence/{row_id}/{live_id}"
    manual_stale = f"manual_evidence/{row_id}/{stale_id}"
    legacy_live, legacy_stale = "avatars/legacy.jpg", "avatars/orphan.jpg"
    with Session(engine) as session:
        session.add(User(id=7, email="owner@example.test", username="owner", password_hash="hash",
                         real_name="", avatar_key=avatar_live))
        session.add(User(id=8, email="legacy@example.test", username="legacy", password_hash="hash",
                         real_name="", avatar_key=legacy_live))
        session.add(ScientificManualEvidence(id=row_id, target="upload", target_id="task",
            item_key="field", baseline_hash="base", value_hash="value", source_hash="source",
            actor_user_id=7, reason="人工核验", items=[{"id": live_id, "kind": "image",
                "storage_key": manual_live}]))
        session.commit()
    try:
        with moto.mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
            store = S3FileStorage(endpoint="https://s3.amazonaws.com", region="us-east-1",
                                  bucket="scwiki-storage-test", access_key="test", secret_key="test")
            for key in (avatar_live, avatar_stale, manual_live, manual_stale, legacy_live, legacy_stale):
                store.put(key, BytesIO(key.encode()), "application/octet-stream")
            monkeypatch.setenv("DATABASE_URL", database_url)
            monkeypatch.setattr(migrate_file_storage, "s3_storage", lambda: store)
            assert reconcile_file_storage.reconcile() == {"unused": 3, "deleted": 0}
            with pytest.raises(FileInventoryError, match="维护窗口"):
                reconcile_file_storage.reconcile(apply=True)
            monkeypatch.setenv("SCWIKI_MAINTENANCE_MODE", "1")
            assert reconcile_file_storage.reconcile(apply=True) == {"unused": 3, "deleted": 3}
            store.head(store.describe(avatar_live))
            store.head(store.describe(legacy_live))
            store.head(store.describe(manual_live))
            with pytest.raises(FileIntegrityError):
                store.describe(avatar_stale)
            assert reconcile_file_storage.reconcile(apply=True) == {"unused": 0, "deleted": 0}
            unknown = store.put("files/avatars/unknown", BytesIO(b"unknown"), "application/octet-stream")
            with pytest.raises(FileInventoryError, match="未识别"):
                reconcile_file_storage.reconcile()
            store.delete(unknown)
    finally:
        engine.dispose()
