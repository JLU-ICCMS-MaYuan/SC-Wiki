"""Issue #92：历史 OpenAlex Zenodo 资讯清理。"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.news.models import NewsFeedIdentity, NewsFeedItem, NewsFeedSource
from backend.scripts.cleanup_zenodo_news import clean


def make_engine():
    engine = create_engine("sqlite:///:memory:")
    for table in (NewsFeedItem.__table__, NewsFeedIdentity.__table__, NewsFeedSource.__table__):
        table.create(engine)
    return engine


def seed(engine):
    with Session(engine) as db, db.begin():
        db.add_all(
            [
                NewsFeedItem(
                    id="z" * 32, kind="journal_article", title="历史 Zenodo",
                    source="openalex", url="https://zenodo.org/record/1", doi="https://doi.org/10.5281/zenodo.1",
                    discovery_source="openalex", original_source="acs", content_type="peer_reviewed",
                    display_kind="journal_article", links='[{"source":"openalex","role":"discovery"}]',
                    first_seen_at="2026-09-01T00:00:00Z", last_seen_at="2026-09-01T00:00:00Z",
                ),
                NewsFeedItem(
                    id="k" * 32, kind="journal_article", title="保留的期刊",
                    source="openalex", url="https://doi.org/10.1021/keep", doi="10.1021/keep",
                    discovery_source="openalex", content_type="peer_reviewed", display_kind="journal_article",
                    first_seen_at="2026-09-01T00:00:00Z", last_seen_at="2026-09-01T00:00:00Z",
                ),
                NewsFeedItem(
                    id="p" * 32, kind="journal_article", title="其他来源 Zenodo DOI",
                    source="crossref", url="https://zenodo.org/record/2", doi="10.5281/zenodo.2",
                    discovery_source="crossref", content_type="peer_reviewed", display_kind="journal_article",
                    first_seen_at="2026-09-01T00:00:00Z", last_seen_at="2026-09-01T00:00:00Z",
                ),
            ]
        )
        db.flush()
        db.add_all([
            NewsFeedIdentity(key="z" * 64, item_id="z" * 32),
            NewsFeedIdentity(key="keep" * 16, item_id="k" * 32),
        ])


def test_dry_run_reports_targets_without_mutation(tmp_path):
    engine = make_engine()
    seed(engine)
    result = clean(engine)
    assert result == {
        "item_count": 1,
        "identity_count": 1,
        "item_ids": ["z" * 32],
        "normalized_dois": ["10.5281/zenodo.1"],
        "dry_run": True,
    }
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "z" * 32))
        assert db.scalar(select(NewsFeedIdentity.key).where(NewsFeedIdentity.item_id == "z" * 32))


def test_execute_writes_backup_and_is_idempotent(tmp_path):
    engine = make_engine()
    seed(engine)
    backup = tmp_path / "backup.json"
    result = clean(engine, backup_file=backup, execute=True)
    assert result["item_count"] == 1
    assert result["identity_count"] == 1
    payload = json.loads(backup.read_text(encoding="utf-8"))
    assert payload["summary"] == {"item_count": 1, "identity_count": 1}
    assert payload["items"][0]["item"]["title"] == "历史 Zenodo"
    assert payload["items"][0]["identities"] == [{"key": "z" * 64, "item_id": "z" * 32}]
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "z" * 32)) is None
        assert db.scalar(select(NewsFeedIdentity.key).where(NewsFeedIdentity.item_id == "z" * 32)) is None
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "k" * 32)) == "k" * 32
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "p" * 32)) == "p" * 32
    second = clean(engine, backup_file=tmp_path / "second.json", execute=True)
    assert second["item_count"] == 0
    assert second["identity_count"] == 0


def test_execute_requires_backup_file():
    engine = make_engine()
    with pytest.raises(ValueError, match="backup_file"):
        clean(engine, execute=True)


def test_execute_rolls_back_when_delete_fails(tmp_path):
    engine = make_engine()
    seed(engine)
    backup = tmp_path / "rollback.json"

    def fail_after_identity_delete(_db):
        raise RuntimeError("injected failure")

    with pytest.raises(RuntimeError, match="injected failure"):
        clean(engine, backup_file=backup, execute=True, after_identity_delete=fail_after_identity_delete)
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "z" * 32)) == "z" * 32
        assert db.scalar(select(NewsFeedIdentity.key).where(NewsFeedIdentity.item_id == "z" * 32)) == "z" * 64
        assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "k" * 32)) == "k" * 32


@pytest.mark.skipif(not __import__("os").environ.get("ISSUE92_TEST_MYSQL_URL"), reason="需要明确的隔离 MySQL 地址")
def test_mysql_isolation_smoke(tmp_path):
    """在独立 MySQL 数据库中复用同一清理流程，防止只在 SQLite 验证。"""
    import os

    engine = create_engine(os.environ["ISSUE92_TEST_MYSQL_URL"], pool_pre_ping=True)
    try:
        for table in (NewsFeedIdentity.__table__, NewsFeedSource.__table__, NewsFeedItem.__table__):
            table.drop(engine, checkfirst=True)
        for table in (NewsFeedItem.__table__, NewsFeedIdentity.__table__, NewsFeedSource.__table__):
            table.create(engine)
        seed(engine)
        result = clean(engine)
        assert result["item_count"] == 1
        def fail_after_identity_delete(_db):
            raise RuntimeError("injected failure")

        rollback_backup = tmp_path / "issue92-mysql-rollback.json"
        with pytest.raises(RuntimeError, match="injected failure"):
            clean(engine, backup_file=rollback_backup, execute=True, after_identity_delete=fail_after_identity_delete)
        with Session(engine) as db:
            assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "z" * 32)) == "z" * 32

        backup = rollback_backup.with_name("issue92-mysql-backup.json")
        assert clean(engine, backup_file=backup, execute=True)["item_count"] == 1
        assert clean(engine, backup_file=backup.with_name("issue92-mysql-second.json"), execute=True)["item_count"] == 0
        with Session(engine) as db:
            assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "z" * 32)) is None
            assert db.scalar(select(NewsFeedItem.id).where(NewsFeedItem.id == "k" * 32)) == "k" * 32
    finally:
        engine.dispose()
