"""显式隔离 MySQL/Redis：迁移、真实 RQ、候选发布和 Go 公开接口。"""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from redis import Redis
from rq import SimpleWorker
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.news.domain import Record
from backend.news.models import NewsFeedCandidate, NewsFeedItem, NewsFeedSource
from backend.news.scheduler import QUEUE_NAME, enqueue_relevance
from backend.news.service import collect_source

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not os.getenv("NEWS_RELEVANCE_TEST_MYSQL_URL"), reason="需要显式隔离MySQL/Redis")


def test_candidate_migration_queue_and_go(monkeypatch):
    url = make_url(os.environ["NEWS_RELEVANCE_TEST_MYSQL_URL"])
    assert url.host in ("127.0.0.1", "localhost") and url.database.startswith("news_test_")
    redis_url = os.environ["NEWS_RELEVANCE_TEST_REDIS_URL"]
    assert make_url(redis_url).host in ("127.0.0.1", "localhost")
    engine = create_engine(url)
    connection = Redis.from_url(redis_url)
    assert not inspect(engine).get_table_names() and connection.dbsize() == 0
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER PRIMARY KEY, title VARCHAR(100))"))
        conn.execute(text("INSERT INTO papers VALUES (1, 'unchanged')"))
        conn.execute(text("CREATE TABLE material_families (id INTEGER PRIMARY KEY, name_zh TEXT, name_en TEXT)"))
        with Operations.context(MigrationContext.configure(conn)):
            for name in ("20260831_0063_news_feed.py", "20260903_0003_networked_news_discovery.py",
                         "20261022_0153_news_classification.py", "20261102_0160_news_candidates.py"):
                spec = importlib.util.spec_from_file_location("migration", ROOT / "alembic/versions" / name)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.upgrade()
            migration.downgrade()
            migration.upgrade()

    class Sources:
        def fetch(self, *_):
            return [Record(source="crossref", external_id=str(i), doi=f"10.1002/relevance{i}", kind="journal_article",
                           title=title, url=f"https://doi.org/10.1002/relevance{i}",
                           published_at="2026-10-22T00:00:00Z", screening_abstract="内部筛选摘要，不公开")
                    for i, title in enumerate(("Superconductivity 中文相关", "Hydrogen 无关", "Hydride 信息不足"))]
    assert collect_source(engine, "crossref", Sources(), now=datetime(2026, 11, 2, tzinfo=timezone.utc))
    with Session(engine) as db:
        assert db.scalar(select(NewsFeedItem)) is None
        assert len(db.scalars(select(NewsFeedCandidate)).all()) == 3
        assert db.get(NewsFeedSource, "crossref").status == "success"

    import backend.database
    import backend.rag.llm
    import backend.rag.llm_context
    from backend.rag.llm_context import LlmConfig
    monkeypatch.setattr(backend.database, "engine", engine)
    monkeypatch.setattr(backend.rag.llm_context, "get_llm_config", lambda: LlmConfig("fixture", "", "fixture", ""))
    def complete(_prompt, body, **kwargs):
        title = json.loads(body)["title"]
        decision = "related" if "中文相关" in title else "unrelated" if "无关" in title else "insufficient"
        return {"decision": decision, "reason": "隔离链路判断", "evidence": title}
    monkeypatch.setattr(backend.rag.llm, "complete_json", complete)
    assert enqueue_relevance(connection)
    assert not enqueue_relevance(connection)
    SimpleWorker([QUEUE_NAME], connection=connection).work(burst=True, logging_level="WARNING")
    with Session(engine) as db:
        assert {r.status for r in db.scalars(select(NewsFeedCandidate))} == {"related", "unrelated", "insufficient"}
        public = db.scalars(select(NewsFeedItem)).all()
        assert len(public) == 1 and public[0].summary == ""
        assert db.execute(text("SELECT title FROM papers")).scalar_one() == "unchanged"
    go = str(ROOT / ".local/go/bin/go")
    dsn = f"{url.username}:{url.password or ''}@tcp({url.host}:{url.port})/{url.database}?charset=utf8mb4&parseTime=true"
    result = subprocess.run([go, "test", "./handlers", "-run", "^TestNews", "-count=1"],
                            cwd=ROOT / "goserver", env={**os.environ, "NEWS_TEST_MYSQL_DSN": dsn},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    engine.dispose()
