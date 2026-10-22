"""显式隔离 MySQL/Redis 的迁移、RQ 与 Python→Go 契约验证，不读业务配置。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.news.classification import classify_batch
from backend.news.domain import Record
from backend.news.models import NewsFeedClassification
from backend.news.scheduler import QUEUE_NAME, enqueue_classification
from backend.news.service import collect_source

pytestmark = pytest.mark.skipif(not os.getenv("NEWS_CLASSIFICATION_TEST_MYSQL_URL"), reason="需要显式隔离 MySQL")
ROOT = Path(__file__).resolve().parents[2]


def migration(name):
    spec = importlib.util.spec_from_file_location("news_migration", ROOT / "alembic/versions" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_worker_and_go_contract(monkeypatch):
    url = make_url(os.environ["NEWS_CLASSIFICATION_TEST_MYSQL_URL"])
    assert url.host in ("localhost", "127.0.0.1") and url.database.startswith("news_test_")
    engine = create_engine(url)
    assert inspect(engine).get_table_names() == [], "只允许全新隔离数据库"
    redis_url = os.environ["NEWS_CLASSIFICATION_TEST_REDIS_URL"]
    assert make_url(redis_url).host in ("localhost", "127.0.0.1")
    connection = Redis.from_url(redis_url)
    assert connection.dbsize() == 0, "只允许全新隔离 Redis"
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration("20260831_0063_news_feed.py").upgrade()
            migration("20260903_0003_networked_news_discovery.py").upgrade()
            conn.execute(text("CREATE TABLE users (id INT PRIMARY KEY)"))
            from backend.models import MaterialFamily, MaterialFamilyAlias
            MaterialFamily.__table__.create(conn)
            MaterialFamilyAlias.__table__.create(conn)
            current = migration("20261022_0153_news_classification.py")
            current.upgrade()
            current.downgrade()
            current.upgrade()
        conn.execute(text("INSERT INTO material_families (id, code, name_zh, name_en, normalized_name) VALUES (1, 'hydrogen_based', '氢基超导体', 'Hydrides', 'hydrides')"))
        conn.execute(text("CREATE TABLE papers (id INT PRIMARY KEY, title VARCHAR(100))"))
        conn.execute(text("INSERT INTO papers VALUES (1, 'unchanged')"))

    class Sources:
        def fetch(self, source, since, until):
            return [Record(source="arxiv", external_id=f"news153-{index}", kind="preprint",
                           title=f"中文超导标题 {index}", summary="现有摘要", summary_source="arxiv",
                           published_at="2026-10-22T00:00:00Z", url=f"https://example.org/{index}") for index in range(5)]
    assert collect_source(engine, "arxiv", Sources(), now=datetime.now(timezone.utc))
    import backend.database
    import backend.rag.llm
    from backend.rag.llm_context import LlmConfig
    import backend.rag.llm_context
    monkeypatch.setattr(backend.database, "engine", engine)
    monkeypatch.setattr(backend.rag.llm_context, "get_llm_config", lambda: LlmConfig("fixture", "", "fixture", ""))
    monkeypatch.setenv("REDIS_URL", redis_url)
    calls = []
    def complete(*args, **kwargs):
        calls.append(args)
        return dict(paper_type="theoretical", theoretical_subtype="calculation", material_family_ids=[1], reason="隔离接口样本")
    monkeypatch.setattr(backend.rag.llm, "complete_json", complete)
    unrelated = Queue("pdf-test-sentinel", connection=connection)
    unrelated.enqueue("builtins.len", [1], job_id="news153-sentinel")
    assert enqueue_classification(connection)
    assert not enqueue_classification(connection)
    worker = SimpleWorker([QUEUE_NAME], connection=connection)
    worker.work(burst=True, logging_level="WARNING")
    assert len(calls) == 3
    assert enqueue_classification(connection)
    worker.work(burst=True, logging_level="WARNING")
    assert len(calls) == 5
    assert unrelated.job_ids == ["news153-sentinel"]
    assert classify_batch(engine, complete=complete) == []
    with Session(engine) as db:
        assert len(db.scalars(select(NewsFeedClassification).where(NewsFeedClassification.status == "completed")).all()) == 5
        assert db.execute(text("SELECT title FROM papers WHERE id=1")).scalar_one() == "unchanged"
    go = os.getenv("NEWS_TEST_GO_BINARY", str(ROOT / ".local/go/bin/go"))
    dsn = f"{url.username}:{url.password}@tcp({url.host}:{url.port})/{url.database}?charset=utf8mb4&parseTime=true"
    result = subprocess.run([go, "test", "./handlers", "-run", "^TestNewsFeedMySQLContract$", "-count=1"], cwd=ROOT / "goserver",
                            env={**os.environ, "NEWS_TEST_MYSQL_DSN": dsn, "NEWS_TEST_REQUIRE_CLASSIFICATION": "1"},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    engine.dispose()
