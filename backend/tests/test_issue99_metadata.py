"""#99：在当前 MySQL 和 Redis 验证书目往返，所有测试数据清理或回滚。"""

import asyncio
import json
import os
import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.api import rag
from backend.ingest.upload_jobs import _normalize_draft


@pytest.mark.parametrize("value, expected", [(None, None), ("S1", "S1"), ("3-4", "3-4"), (3, "3")])
def test_issue_number_normalization(value, expected):
    paper = _normalize_draft({"paper": {"issue_number": value, "volume": "12", "pages": "100-108"}})["paper"]
    assert paper["issue_number"] == expected
    assert paper["volume"] == "12"
    assert paper["pages"] == "100-108"


def test_chunk_metadata_keeps_issue_separate_from_year_and_volume():
    from backend.ingest.upload_jobs import _build_candidate_draft

    draft = _build_candidate_draft([{"result": {"metadata": {
        "title": "测试论文", "journal": "Nature", "year": 2026,
        "issue_number": "3-4", "volume": "12", "pages": "100-108",
    }}}])
    assert draft["paper"]["issue_number"] == "3-4"
    assert draft["paper"]["volume"] == "12"
    assert draft["paper"]["year"] == 2026
    assert draft["paper"]["pages"] == "100-108"


@pytest.mark.skipif(os.getenv("SCWIKI_CURRENT_MYSQL") != "1", reason="需要显式选择当前 MySQL")
def test_current_mysql_draft_save_reload_and_submit(monkeypatch):
    from backend.ingest import upload_tasks
    from backend.rag import database

    task_id = uuid.uuid4().hex
    client = upload_tasks.redis_client()

    async def scenario():
        assert database.database_url.startswith("mysql+"), "禁止建立临时数据库"
        engine = create_async_engine(database.database_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    factory = async_sessionmaker(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
                    monkeypatch.setattr(database, "async_session_factory", factory)
                    async with factory() as session:
                        user = await session.scalar(select(models.User).where(models.User.account_status == "active"))
                        family = await session.scalar(select(models.MaterialFamily))
                        assert user and family
                    state = {"task_id": task_id, "user_id": user.id, "status": "ready", "processing_status": "succeeded", "files": [], "cleanup_at": int(time.time()) + 600}
                    client.setex(upload_tasks.task_key(task_id), 600, json.dumps(state))
                    draft = _normalize_draft({"paper": {
                        "title": "Issue 99 书目验证", "journal": "Physical Review Letters", "year": 2026,
                        "issue_number": "S1", "volume": "12", "pages": "100-108", "paper_type": "review",
                        "material_families": [{"id": family.id, "name": family.name_zh, "status": "confirmed"}],
                    }})
                    result = await rag.put_upload_draft(task_id, draft, user)
                    assert result["data"]["paper"]["issue_number"] == "S1"
                    reloaded = await rag.get_upload_draft(task_id, user)
                    assert reloaded["data"]["paper"]["issue_number"] == "S1"
                    paper_id = await rag._create_pending_paper(task_id, state, reloaded["data"])
                    async with factory() as session:
                        paper = await session.get(models.Paper, paper_id)
                        assert (paper.issue_number, paper.volume, paper.pages, paper.year) == ("S1", "12", "100-108", 2026)
                        assert paper.review_status == "pending"
                finally:
                    await transaction.rollback()
                assert await connection.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id)) is None
        finally:
            await engine.dispose()

    try:
        asyncio.run(scenario())
    finally:
        client.delete(upload_tasks.task_key(task_id), upload_tasks.draft_key(task_id))
        directory = upload_tasks.task_directory(task_id)
        directory.rmdir()
