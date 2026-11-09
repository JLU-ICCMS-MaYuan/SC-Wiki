"""正式入库的论文级材料所有权；所有临时业务行由外层事务回滚。"""
import asyncio
import os
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式启用本机MySQL回滚验证')


@pytest.mark.parametrize('materials', [['Reviewed calcium hydrides'], []])
def test_paper_materials_survive_formal_mysql_create_and_reread(monkeypatch, materials):
    async def run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from backend import models
        from backend.api import rag
        from backend.rag import database
        url = database.engine.url
        assert url.host in {'127.0.0.1', 'localhost'}
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    factory = async_sessionmaker(bind=connection, expire_on_commit=False,
                        join_transaction_mode='create_savepoint')
                    monkeypatch.setattr(database, 'async_session_factory', factory)
                    identity = uuid4().hex
                    async with factory() as session, session.begin():
                        user = models.User(email=identity+'@isolated.invalid', username='owner'+identity[:12],
                            real_name='隔离所有权验证', password_hash='unused', role='user', is_approved=True)
                        session.add(user); await session.flush()
                        user_id = user.id
                        family = await session.scalar(select(models.MaterialFamily).limit(1))
                        assert family is not None
                        selection = {'id': family.id, 'name': family.name_en or family.name_zh, 'status': 'approved'}
                    draft = {'paper': {'title': 'Isolated paper ownership '+identity, 'authors': [],
                        'year': 2026, 'paper_type': 'review', 'superconductor_kind': 'unknown',
                        'research_materials': materials, 'material_families': [selection]},
                        'material_states': [{'material': 'CaH6', 'material_name': 'CaH6',
                            'state_kind': 'theoretical', 'pressure_value_gpa': 150,
                            'structure_optimization': 'classical_static', 'property_modules': []}]}
                    await rag._create_pending_paper(identity, {'user_id': user_id}, draft)
                    async with factory() as session:
                        paper = await session.scalar(select(models.Paper).where(models.Paper.upload_task_id == identity))
                        assert paper is not None and paper.research_materials == materials
                        assert paper.uploaded_by_user_id == user_id and paper.review_status == 'pending'
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())
