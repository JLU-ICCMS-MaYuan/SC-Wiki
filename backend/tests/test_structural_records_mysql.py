"""#49：实际 MySQL 新增迁移、正式科学保存入口与事务回滚。"""

import asyncio
import importlib.util
import os
from pathlib import Path
import pytest


def test_migration_scientific_write_revision_and_rollback(monkeypatch):
    url = os.environ.get("STRUCTURAL_MYSQL_TEST_URL")
    if not url:
        pytest.skip("需要专用隔离 MySQL 测试库")
    from sqlalchemy import create_engine, inspect, select, func
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from backend import models
    from backend.structural_models import PaperStructuralRecord as Record
    from backend.services import structural_records as service
    from backend.ingest.scientific_drafts import persist_scientific_draft
    from backend.tests.test_structural_records import geometry, observation

    parsed = make_url(url)
    assert parsed.database.startswith("test_scwiki_struct49_")
    assert parsed.host in {None, "localhost", "127.0.0.1"}
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), "测试库必须为空"
    models.Base.metadata.create_all(engine, tables=[models.User.__table__, models.Paper.__table__])
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261020_0049_structural_records.py"
    spec = importlib.util.spec_from_file_location("structural_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
    assert service.available(Session(engine))
    report = os.environ.get("STRUCTURAL_SCHEMA_REPORT")
    if report:
        import json
        from scripts.local_deploy.schema import structure

        Path(report).write_text(
            json.dumps(structure(inspect(engine), Record.__tablename__), ensure_ascii=False, indent=2)
        )
    with Session(engine) as session:
        user = models.User(
            email="structural@example.test",
            username="structural-test",
            real_name="隔离测试",
            password_hash="unused",
            role="user",
            account_status="active",
            is_approved=True,
            is_email_verified=True,
        )
        session.add(user)
        session.flush()
        paper = models.Paper(
            title="Isolated structural facts",
            year=2026,
            paper_type="review",
            superconductor_kind="unknown",
            review_status="pending",
            content_revision=1,
            uploaded_by_user_id=user.id,
        )
        session.add(paper)
        session.commit()
        paper_id = paper.id
    async_url = parsed.set(drivername="mysql+asyncmy").render_as_string(hide_password=False)

    async def run():
        async_engine = create_async_engine(async_url, poolclass=NullPool)
        factory = async_sessionmaker(async_engine, expire_on_commit=False)
        draft = dict(
            paper=dict(superconductor_kind="unknown"),
            material_states=[],
            structure_candidates=[geometry()],
            structural_observations=[observation()],
        )
        async with factory() as session:
            async with session.begin():
                paper = await session.get(models.Paper, paper_id)
                targets = await persist_scientific_draft(session, paper, draft)
                assert targets == []
        async with factory() as session:
            rows = (await session.scalars(select(Record).where(Record.paper_id == paper_id))).all()
            assert len(rows) == 1 and all(r.state_key is None for r in rows)
            assert next(r for r in rows if r.kind == "model").material == "LaSc2"
            paper = await session.get(models.Paper, paper_id)
            restored = await session.run_sync(
                lambda sync: service.supplement_draft(
                    sync, paper, dict(material_states=[], structure_candidates=[])
                )
            )
            assert restored["structure_candidates"][0]["retention"] == "retained"
        with pytest.raises(RuntimeError, match="rollback"):
            async with factory() as session:
                async with session.begin():
                    paper = await session.get(models.Paper, paper_id)
                    paper.content_revision = 2
                    await persist_scientific_draft(session, paper, draft)
                    raise RuntimeError("rollback")
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(Record)) == 1
            assert (await session.get(models.Paper, paper_id)).content_revision == 1
        async with factory() as session:
            async with session.begin():
                paper = await session.get(models.Paper, paper_id)
                paper.content_revision = 2
                await persist_scientific_draft(session, paper, draft)
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(Record)) == 2
        await async_engine.dispose()

    asyncio.run(run())
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
    assert not inspect(engine).has_table(Record.__tablename__)
    engine.dispose()
