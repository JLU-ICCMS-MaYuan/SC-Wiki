"""新库执行完整迁移；恢复库只核验，绝不 stamp 或降级。"""
from __future__ import annotations

from contextlib import contextmanager
import os
import json
import re
from pathlib import Path

from .environment import versions


@contextmanager
def database_environment(url):
    old = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url
    try:
        yield
    finally:
        if old is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = old


def config(root):
    from alembic.config import Config
    result = Config(str(root / 'alembic.ini'))
    result.set_main_option('script_location', str(root / 'alembic'))
    return result


def structure(inspector, name):
    columns = {c['name']: {'type': str(c['type']).lower(), 'nullable': c['nullable']}
               for c in inspector.get_columns(name)}
    foreign = sorted([{'columns': f['constrained_columns'], 'table': f['referred_table'],
                       'references': f['referred_columns']} for f in inspector.get_foreign_keys(name)],
                     key=lambda f: json.dumps(f, sort_keys=True))
    unique = sorted([u['column_names'] for u in inspector.get_unique_constraints(name)])
    checks = sorted(re.sub(r"_utf8mb[34](?=')", '', re.sub(r'\s+|`', '', c['sqltext']).lower())
                    for c in inspector.get_check_constraints(name))
    return {'columns': columns, 'foreign_keys': foreign, 'unique': unique, 'checks': checks,
            'primary_key': inspector.get_pk_constraint(name)['constrained_columns']}


def verify_schema(root: Path, url: str):
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    expected = set(versions(root)['schema_heads'])
    if set(ScriptDirectory.from_config(config(root)).get_heads()) != expected:
        raise ValueError('源码迁移头与部署版本清单不一致')
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        if 'alembic_version' not in tables:
            raise ValueError('数据库缺少迁移版本；不会自动 stamp')
        with engine.connect() as conn:
            if set(conn.execute(text('SELECT version_num FROM alembic_version')).scalars()) != expected:
                raise ValueError('数据库全部迁移分支与源码不一致')
        expected_schema = json.loads((root / 'scripts/local-deploy-schema.json').read_text())
        for name, expected_table in expected_schema['tables'].items():
            if name not in tables:
                raise ValueError(f'数据库缺少表 {name}')
            actual = structure(inspector, name)
            if actual != expected_table:
                raise ValueError(f'数据库表 {name} 的列、约束或关联与受测结构不一致')
        retired = {'calculation_contexts', 'experimental_contexts', 'superconductor_properties',
                   'superconductor_property_evidences', 'tc_result_evidences', 'tc_results'}
        if tables & retired:
            raise ValueError('数据库仍有已经退役的表')
    finally:
        engine.dispose()


def initialize(root: Path, url: str):
    from alembic import command
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import Session
    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            raise ValueError('仅允许对全新空业务库初始化')
        with database_environment(url):
            cfg = config(root)
            # #90 需要显式数据切换阶段；新空库同样走真实迁移，不伪造 stamp。
            command.upgrade(cfg, 'issue90_copy_v1')
            from backend.scripts.migrate_issue90_properties import run_migration
            with engine.begin() as conn:
                if conn.execute(text('SELECT COUNT(*) FROM papers')).scalar_one():
                    raise ValueError('空库初始化期间出现业务数据，停止迁移')
                for action in ('reconcile', 'read-switch', 'write-switch', 'observe'):
                    report = run_migration(conn, action)
                    if report.get('errors'):
                        raise ValueError('空库迁移校验失败')
            previous = os.environ.get('ISSUE90_CONTRACT_CONFIRMED')
            try:
                os.environ['ISSUE90_CONTRACT_CONFIRMED'] = '1'
                for head in versions(root)['schema_heads']:
                    command.upgrade(cfg, head)
            finally:
                if previous is None:
                    os.environ.pop('ISSUE90_CONTRACT_CONFIRMED', None)
                else:
                    os.environ['ISSUE90_CONTRACT_CONFIRMED'] = previous
            from backend.scripts.init_db import seed_periodic_table_elements
            with Session(engine) as session:
                seed_periodic_table_elements(session)
        verify_schema(root, url)
    finally:
        engine.dispose()
