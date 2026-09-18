"""材料名增量迁移与真实科学保存回归；MySQL 测试仅写回滚夹具。"""
import asyncio
import importlib.util
import os
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


def test_material_name_migration_preserves_existing_state(monkeypatch):
    migration_path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260916_0105_material_name.py'
    spec = importlib.util.spec_from_file_location('material_name_migration', migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE material_states (id INTEGER PRIMARY KEY, state_key VARCHAR(96), superconductor_id INTEGER NOT NULL)'))
            connection.execute(text("INSERT INTO material_states VALUES (1, 'tin', 7)"))
            monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            assert tuple(connection.execute(text('SELECT * FROM material_states')).one()) == (1, 'tin', 7, None)
            column = next(c for c in inspect(connection).get_columns('material_states') if c['name'] == 'material_name')
            assert column['nullable'] and column['type'].length == 255
    finally:
        engine.dispose()


@pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式选择当前 MySQL 回滚验证')
def test_current_mysql_scientific_save_and_reload(monkeypatch):
    from backend import models
    from backend.api.rag import rewrite_paper_scientific_draft
    from backend.database import DATABASE_URL
    from backend.rag import database

    async def run():
        engine = create_async_engine(DATABASE_URL.replace('mysql+pymysql://', 'mysql+asyncmy://'))
        try:
            async with engine.connect() as connection:
                outer = await connection.begin()
                try:
                    def factory():
                        return AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')

                    monkeypatch.setattr(database, 'async_session_factory', factory)
                    async with factory() as session, session.begin():
                        # 先执行出错的真实 ORM 读取，缺迁移时必须失败，不能用 create_all 掩盖。
                        await session.execute(select(models.MaterialState).limit(1))
                        reviewer = await session.scalar(select(models.User).where(models.User.role.in_(['admin', 'superadmin'])))
                        assert reviewer is not None
                        family = await session.scalar(select(models.MaterialFamily).limit(1))
                        assert family is not None
                        paper = models.Paper(title='材料名迁移回滚验收 ' + uuid.uuid4().hex, year=2026,
                            paper_type='experimental', review_status='pending', content_revision=1,
                            uploaded_by_user_id=reviewer.id, authors=['test'], journal='test',
                            abstract='test', summary='test', superconductor_kind='conventional')
                        session.add(paper)
                        await session.flush()
                        paper_id = paper.id
                        payload = dict(paper_type='experimental', superconductor_kind='conventional',
                            material_families=[dict(id=family.id, name=family.name_zh, status='confirmed')],
                            material_states=[dict(state_key='tin', material='Sn', material_name='锡样品',
                                state_kind='experimental', crystal_system='tetragonal',
                                pressure_value_gpa=0.000101, property_modules=[], structure_families=[])])
                    first = await rewrite_paper_scientific_draft(paper_id, payload, reviewer)
                    assert first['ok']
                    payload['material_states'][0]['pressure_value_gpa'] = 0.002
                    second = await rewrite_paper_scientific_draft(paper_id, payload, reviewer)
                    assert second['ok'] and not second['data']['unchanged']
                    async with factory() as session:
                        saved = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == paper_id))
                        assert saved.material_name == '锡样品'
                        assert saved.state_key == 'tin'
                        assert float(saved.pressure_value_gpa) == 0.002
                finally:
                    await outer.rollback()
                async with factory() as session:
                    assert await session.get(models.Paper, paper_id) is None
        finally:
            await engine.dispose()
    asyncio.run(run())
