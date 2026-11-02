"""收录前相关性：真实漏收元数据、模型边界、候选持久化和发布事务。"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from backend.news.domain import Record, candidate_evidence, iso
from backend.news.models import NewsFeedCandidate, NewsFeedIdentity, NewsFeedItem, NewsFeedSource
from backend.news.relevance import (BATCH_SIZE, RULE_VERSION, model_input, review_batch,
                                   review_candidate, stage_candidate, validate_result)
from backend.news.service import collect_source
from backend.news.sources import Sources, Transport

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/specs/160-news-source-semantics/assets/verification/cesium-crossref.json"


@pytest.fixture
def engine():
    db = create_engine("sqlite://")
    for model in (NewsFeedItem, NewsFeedIdentity, NewsFeedSource, NewsFeedCandidate):
        model.__table__.create(db)
    yield db
    db.dispose()


def record(**kw):
    fields = dict(source="crossref", external_id="10.1002/test", doi="10.1002/test", kind="journal_article",
                  title="Superconductivity in cesium superhydrides", url="https://doi.org/10.1002/test",
                  screening_abstract="Synthesis and stability of hydrogen-rich compounds.", published_at="2026-10-22T00:00:00Z")
    fields.update(kw)
    return Record(**fields)


def stage(engine, value=None, now=NOW):
    with Session(engine) as db, db.begin():
        return stage_candidate(db, value or record(), iso(now)).key


def output(decision="related"):
    def complete(_prompt, body):
        payload = json.loads(body)
        assert set(payload) == {"title", "abstract", "keywords"}
        return {"decision": decision, "reason": "测试给定的相关性判断", "evidence": payload["title"]}
    return complete


def test_real_cesium_enters_candidate_without_direct_superconductivity_word(engine):
    item = json.loads(FIXTURE.read_text())["message"]
    queries = []
    def get(req):
        queries.append(req.url.params["query"])
        return httpx.Response(200, json={"message": {"items": [item] if req.url.params["query"] == "hydride" else []}})
    src = Sources(Transport(httpx.Client(transport=httpx.MockTransport(get)), sleep=lambda _: None))
    assert collect_source(engine, "crossref", src, now=NOW)
    assert {"hydride", "hydrides", "hydrogen", "superhydride", "polyhydride", "hydrogen-rich"} <= set(queries)
    with Session(engine) as db:
        candidate = db.scalar(select(NewsFeedCandidate))
        snapshot = json.loads(candidate.record_json)["record"]
        assert snapshot["doi"] == "10.1002/anie.8236450"
        assert snapshot["summary"] == "" and "hydride" in snapshot["screening_abstract"]
        assert "superconduct" not in snapshot["screening_abstract"].lower()
        assert candidate.status == "pending"
        assert db.scalar(select(NewsFeedItem)) is None
    assert review_batch(engine, complete=output("insufficient"), now=NOW) == ["insufficient"]
    assert review_batch(engine, complete=output(), now=NOW + timedelta(days=1)) == []
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem)) is None
        assert db.scalar(select(NewsFeedCandidate)).status == "insufficient"


@pytest.mark.parametrize("decision", ["related", "unrelated", "insufficient"])
def test_only_related_publishes_and_identical_input_reuses_decision(engine, decision):
    key = stage(engine)
    assert review_batch(engine, complete=output(decision), model="fixture", now=NOW) == [decision]
    stage(engine, now=NOW + timedelta(days=1))
    assert review_batch(engine, complete=lambda *_: pytest.fail("unchanged input"), now=NOW + timedelta(days=1)) == []
    with Session(engine) as db:
        assert len(db.scalars(select(NewsFeedItem)).all()) == (1 if decision == "related" else 0)
        row = db.get(NewsFeedCandidate, key)
        assert row.model == "fixture" and row.attempts == 1 and row.reason


def test_new_information_rejudged_and_old_task_cannot_publish(engine):
    key = stage(engine)
    changed = record(screening_abstract="We predict superconductivity with a critical temperature of 100 K.")
    def old_task(*_):
        stage(engine, changed, NOW + timedelta(seconds=1))
        return output()(None, json.dumps(model_input(record())))
    assert review_candidate(engine, key, complete=old_task, now=NOW) == "stale"
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem)) is None
    assert review_batch(engine, complete=output(), now=NOW + timedelta(seconds=1)) == ["related"]


def test_information_insufficient_then_keywords_added(engine):
    stage(engine)
    assert review_batch(engine, complete=output("insufficient"), now=NOW) == ["insufficient"]
    stage(engine, record(screening_keywords="high-temperature superconductivity"), NOW + timedelta(days=1))
    assert review_batch(engine, complete=output(), now=NOW + timedelta(days=1)) == ["related"]


def test_cross_source_dedupe_preserves_richer_input_and_provenance(engine):
    key = stage(engine)
    second = record(source="openalex", external_id="W1", screening_abstract="", summary="", screening_keywords="")
    assert stage(engine, second) == key
    assert review_batch(engine, complete=output(), now=NOW) == ["related"]
    with Session(engine) as db:
        candidate = db.get(NewsFeedCandidate, key)
        assert json.loads(candidate.record_json)["record"]["screening_abstract"] == record().screening_abstract
        item = db.scalar(select(NewsFeedItem))
        assert {v["source"] for v in json.loads(item.links)} == {"crossref", "openalex"}
        assert len(db.scalars(select(NewsFeedIdentity)).all()) == 4


def test_failed_model_bounded_retry_and_lease_token(engine):
    key = stage(engine)
    def failure(*_):
        raise RuntimeError("secret upstream response")
    for attempt in range(3):
        assert review_batch(engine, complete=failure, now=NOW + timedelta(hours=attempt)) == ["failed"]
        assert review_batch(engine, complete=failure, now=NOW + timedelta(hours=attempt, minutes=1)) == []
    assert review_batch(engine, complete=failure, now=NOW + timedelta(days=1)) == []
    with Session(engine) as db, db.begin():
        row = db.get(NewsFeedCandidate, key)
        assert row.reason == "RuntimeError" and row.attempts == 3
        row.status, row.attempts, row.updated_at = "pending", 0, iso(NOW)
    def expired(*_):
        assert review_candidate(engine, key, complete=output("unrelated"), now=NOW + timedelta(minutes=6)) == "unrelated"
        return output()(None, json.dumps(model_input(record())))
    assert review_candidate(engine, key, complete=expired, now=NOW) == "stale"
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem)) is None


def test_crashed_final_attempt_finishes_and_rule_version_reopens(engine):
    key = stage(engine)
    def killed(*_):
        raise SystemExit()
    for attempt in range(3):
        with pytest.raises(SystemExit):
            review_batch(engine, complete=killed, now=NOW + timedelta(minutes=6 * attempt))
    assert review_batch(engine, complete=output(), now=NOW + timedelta(minutes=18)) == []
    with Session(engine) as db, db.begin():
        row = db.get(NewsFeedCandidate, key)
        assert row.status == "failed" and row.reason == "relevance_timeout"
        row.rule_version = "old"
    assert review_batch(engine, complete=output(), now=NOW + timedelta(minutes=19)) == ["related"]


def test_short_batches_resume_and_limit_is_enforced(engine):
    for index in range(5):
        stage(engine, record(doi=f"10.1002/{index}", external_id=str(index), url=f"https://doi.org/10.1002/{index}"))
    assert review_batch(engine, complete=output(), now=NOW, limit=0) == []
    assert review_batch(engine, complete=output(), now=NOW, limit=999) == ["related"] * BATCH_SIZE
    assert review_batch(engine, complete=output(), now=NOW) == ["related"] * 2


def test_missing_timestamp_does_not_hide_new_evidence_and_older_result_is_ignored(engine):
    key = stage(engine, record(source_updated_at=iso(NOW)))
    stage(engine, record(source_updated_at=iso(NOW - timedelta(days=1)), screening_keywords="old"))
    with Session(engine) as db:
        assert json.loads(db.get(NewsFeedCandidate, key).record_json)["record"]["screening_keywords"] == ""
    stage(engine, record(screening_keywords="new superconductivity evidence"))
    with Session(engine) as db:
        assert json.loads(db.get(NewsFeedCandidate, key).record_json)["record"]["screening_keywords"] == "new superconductivity evidence"


def test_failed_publication_rolls_back_decision_and_can_resume(engine, monkeypatch):
    key = stage(engine)
    import backend.news.service
    original = backend.news.service.upsert
    def failed_write(*_):
        raise RuntimeError("database write failed")
    monkeypatch.setattr(backend.news.service, "upsert", failed_write)
    with pytest.raises(RuntimeError):
        review_batch(engine, complete=output(), now=NOW)
    with Session(engine) as db:
        assert db.get(NewsFeedCandidate, key).status == "running"
        assert db.scalar(select(NewsFeedItem)) is None
    monkeypatch.setattr(backend.news.service, "upsert", original)
    assert review_batch(engine, complete=output(), now=NOW + timedelta(minutes=6)) == ["related"]


def test_repeat_discovery_does_not_starve_other_waiting_candidates(engine):
    first = stage(engine)
    stage(engine, record(doi="10.1002/later", external_id="later"), NOW + timedelta(seconds=1))
    stage(engine, now=NOW + timedelta(days=1))
    assert review_batch(engine, complete=output(), now=NOW + timedelta(days=1), limit=1) == ["related"]
    with Session(engine) as db:
        assert db.get(NewsFeedCandidate, first).status == "related"


@pytest.mark.parametrize("bad", [
    {}, {"decision": []}, {"decision": "unknown"},
    {"decision": "related", "reason": "根据未读取的全文", "evidence": "superconductivity in the full text"},
    {"decision": "related", "reason": "猜测", "evidence": ""},
    {"decision": "unrelated", "reason": "", "evidence": "Cesium"},
])
def test_invalid_or_invented_model_evidence_rejected(bad):
    with pytest.raises(ValueError):
        validate_result(bad, model_input(record()))


def test_real_model_overinterpretation_is_retained_as_insufficient():
    fixture = json.loads(FIXTURE.read_text())["message"]
    payload = {"title": " ".join(fixture["title"]), "abstract": "", "keywords": ""}
    raw = {"decision": "related", "reason": "超氢化物是潜在高温超导材料", "evidence": payload["title"]}
    decision, reason = validate_result(raw, payload)
    assert decision == "insufficient" and "保留待判" in reason


@pytest.mark.parametrize("word", ["hydride", "hydrides", "hydrogen", "hydrogen-rich", "superhydride", "polyhydride", "富氢", "氢化物"])
def test_hydrogen_terms_are_candidates_not_scientific_conclusions(word):
    assert candidate_evidence("Study of " + word)


def test_migration_roundtrip_does_not_touch_business_tables():
    engine = create_engine("sqlite://")
    spec = importlib.util.spec_from_file_location("candidates_migration", ROOT / "alembic/versions/20261102_0160_news_candidates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)"))
        conn.execute(text("INSERT INTO papers VALUES (1, 'unchanged')"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert "news_feed_candidates" in inspect(conn).get_table_names()
            module.downgrade()
            module.upgrade()
        assert conn.execute(text("SELECT title FROM papers")).scalar_one() == "unchanged"
    engine.dispose()
