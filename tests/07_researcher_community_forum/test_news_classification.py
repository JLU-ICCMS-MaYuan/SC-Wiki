"""资讯分类的数据边界、幂等、失败恢复与过期写回验证。"""
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.models import MaterialFamily, MaterialFamilyAlias
from backend.news.classification import classify_batch, classify_item, content_hash, validate_result
from backend.news.domain import Record, iso
from backend.news.models import NewsFeedClassification, NewsFeedIdentity, NewsFeedItem, NewsFeedMaterialFamily, NewsFeedSource
from backend.news.service import upsert

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


@pytest.fixture
def classification_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        for model in (MaterialFamily, MaterialFamilyAlias, NewsFeedItem, NewsFeedIdentity,
                      NewsFeedSource, NewsFeedClassification, NewsFeedMaterialFamily):
            model.__table__.create(conn)
    with Session(engine) as db, db.begin():
        db.add(MaterialFamily(id=1, code="hydrogen_based", name_zh="氢基超导体", name_en="Hydrides", normalized_name="hydrides"))
        db.add(MaterialFamily(id=2, code="iron_based", name_zh="铁基超导体", name_en="Iron based", normalized_name="iron based"))
    yield engine
    engine.dispose()


def add_item(engine, external_id="one", title="Superconductivity", summary="", **kw):
    record = Record(source="arxiv", external_id=external_id, kind="preprint", title=title,
                    summary=summary, summary_source="arxiv" if summary else "", url="https://arxiv.org/abs/" + external_id,
                    published_at=iso(NOW), **kw)
    with Session(engine) as db, db.begin():
        return upsert(db, record, iso(NOW)).id


def output(kind="theoretical", subtype="calculation", ids=None):
    return dict(paper_type=kind, theoretical_subtype=subtype, material_family_ids=[1] if ids is None else ids,
                reason="依据标题摘要的主要研究贡献分类")


@pytest.mark.parametrize("kind,subtype,ids", [
    ("experimental", None, [1]), ("theoretical", "calculation", [1]),
    ("theoretical", "method", []), ("theoretical", "theory", [1, 2]),
    ("review", None, [2]), ("review", None, []), (None, None, []),
    ("theoretical", None, []),
])
def test_classification_round_trip(classification_engine, kind, subtype, ids):
    engine = classification_engine
    item_id = add_item(engine)
    calls = []
    def complete(prompt, payload):
        body = json.loads(payload)
        assert body["summary"] == ""  # 无摘要仍可尝试，但不填入推测文本。
        assert [family["id"] for family in body["material_families"]] == [1, 2]
        assert "背景引用不代表本文主要贡献" in prompt
        calls.append(body)
        return output(kind, subtype, ids)
    assert classify_batch(engine, complete=complete, model="fixture", now=NOW) == ["completed"]
    assert classify_batch(engine, complete=complete, model="fixture", now=NOW) == []
    assert len(calls) == 1
    with Session(engine) as db:
        result = db.get(NewsFeedClassification, item_id)
        assert (result.paper_type, result.theoretical_subtype, result.model) == (kind, subtype, "fixture")
        assert list(db.scalars(select(NewsFeedMaterialFamily.material_family_id))) == ids


@pytest.mark.parametrize("bad", [
    {}, output("mixed", None), output("review", "theory"), output(ids=[99]), output(ids=[True]),
    output(ids=["1"]), {**output(), "reason": ""},
])
def test_rejects_invented_catalog_and_invalid_model_output(bad):
    with pytest.raises(ValueError):
        validate_result(bad, [{"id": 1}])


def test_updates_catalog_and_old_task_cannot_overwrite(classification_engine):
    engine = classification_engine
    item_id = add_item(engine)
    def changing_model(*args):
        with Session(engine) as db, db.begin():
            db.get(NewsFeedItem, item_id).summary = "New experimental result"
        return output()
    assert classify_item(engine, item_id, complete=changing_model, model="fixture", now=NOW) == "stale"
    assert classify_batch(engine, complete=lambda *_: output("experimental", None), now=NOW) == ["completed"]
    with Session(engine) as db, db.begin():
        db.add(MaterialFamilyAlias(material_family_id=1, alias="hydrogen-rich", normalized_alias="hydrogen-rich", language="en"))
    assert classify_batch(engine, complete=lambda *_: output(), now=NOW) == ["completed"]
    with Session(engine) as db:
        assert db.get(NewsFeedClassification, item_id).attempts == 1
        assert len(list(db.scalars(select(MaterialFamily)))) == 2


def test_catalog_change_during_model_call_is_stale(classification_engine):
    engine = classification_engine
    item_id = add_item(engine)
    def complete(*_):
        with Session(engine) as db, db.begin():
            db.get(MaterialFamily, 1).name_zh = "已更新的家族名称"
        return output()
    assert classify_item(engine, item_id, complete=complete, model="fixture", now=NOW) == "stale"


def test_limited_retries_and_crash_recovery(classification_engine):
    engine = classification_engine
    item_id = add_item(engine)
    def failure(*_):
        raise RuntimeError("must not persist secret response")
    for attempt in range(3):
        assert classify_batch(engine, complete=failure, now=NOW + timedelta(hours=attempt)) == ["failed"]
        assert classify_batch(engine, complete=failure, now=NOW + timedelta(hours=attempt, minutes=1)) == []
    assert classify_batch(engine, complete=failure, now=NOW + timedelta(days=2)) == []
    with Session(engine) as db, db.begin():
        result = db.get(NewsFeedClassification, item_id)
        assert result.reason == "RuntimeError"
        assert result.attempts == 3
        result.status, result.attempts, result.updated_at = "running", 1, iso(NOW)
    assert classify_batch(engine, complete=lambda *_: output(), now=NOW + timedelta(minutes=4)) == []
    assert classify_batch(engine, complete=lambda *_: output(), now=NOW + timedelta(minutes=5)) == ["completed"]


def test_attempt_token_rejects_expired_worker(classification_engine):
    engine = classification_engine
    item_id = add_item(engine)
    def old_worker(*_):
        assert classify_item(engine, item_id, complete=lambda *_: output("review", None),
                             model="new", now=NOW + timedelta(minutes=6)) == "completed"
        return output()
    assert classify_item(engine, item_id, complete=old_worker, model="old", now=NOW) == "stale"
    with Session(engine) as db:
        assert db.get(NewsFeedClassification, item_id).paper_type == "review"


def test_last_hard_timeout_is_finalized_as_failed(classification_engine):
    engine = classification_engine
    item_id = add_item(engine)
    def killed(*_):
        raise SystemExit("模拟进程终止，异常处理无机会运行")
    for attempt in range(3):
        with pytest.raises(SystemExit):
            classify_batch(engine, complete=killed, now=NOW + timedelta(minutes=6 * attempt))
    assert classify_batch(engine, complete=killed, now=NOW + timedelta(minutes=18)) == []
    with Session(engine) as db:
        result = db.get(NewsFeedClassification, item_id)
        assert (result.status, result.attempts, result.reason) == ("failed", 3, "classification_timeout")


def test_backfill_batch_limit_and_resume(classification_engine):
    engine = classification_engine
    for index in range(5):
        item_id = add_item(engine, str(index), title=f"Superconductivity {index}")
        with Session(engine) as db, db.begin():
            db.get(NewsFeedItem, item_id).last_seen_at = iso(NOW + timedelta(minutes=index))
    seen = []
    def complete(_prompt, payload):
        seen.append(json.loads(payload))
        return output(None, None, [])
    assert classify_batch(engine, complete=complete, now=NOW) == ["completed"] * 3
    assert [row["title"] for row in seen] == ["Superconductivity 4", "Superconductivity 3", "Superconductivity 2"]
    assert classify_batch(engine, complete=complete, now=NOW) == ["completed"] * 2
    assert classify_batch(engine, complete=complete, now=NOW) == []
    assert len(seen) == 5


def test_duplicate_collection_and_merge_cascade(classification_engine):
    engine = classification_engine
    first = add_item(engine, "first", doi="10.1234/merge")
    second = add_item(engine, "second", title="Different superconductivity title")
    assert classify_batch(engine, complete=lambda *_: output(), now=NOW) == ["completed"] * 2
    assert add_item(engine, "first", doi="10.1234/merge") == first
    assert classify_batch(engine, complete=lambda *_: output(), now=NOW) == []
    kept = add_item(engine, "second", title="Merged superconductivity title", doi="10.1234/merge")
    with Session(engine) as db:
        assert len(list(db.scalars(select(NewsFeedItem)))) == 1
        assert len(list(db.scalars(select(NewsFeedClassification)))) == 1
        assert len(list(db.scalars(select(NewsFeedMaterialFamily)))) == 1
    assert classify_batch(engine, complete=lambda *_: output("review", None), now=NOW) == ["completed"]
    with Session(engine) as db:
        result = db.get(NewsFeedClassification, kept)
        assert result.paper_type == "review"
        assert result.content_hash == content_hash("Merged superconductivity title", "")
