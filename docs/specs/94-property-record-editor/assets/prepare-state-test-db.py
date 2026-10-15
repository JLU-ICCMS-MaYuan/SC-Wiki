"""仅在显式指定且为空的隔离 MySQL 测试库重建 #94 迁移前置 schema。"""
import importlib.util
import os
from pathlib import Path
from sqlalchemy import JSON, create_engine, inspect
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.database import Base
from backend import models  # noqa: F401

url = os.environ["STATE_GEOMETRY_TEST_URL"]
assert "test" in make_url(url).database.lower(), "只允许隔离测试数据库"
engine = create_engine(url)
assert not inspect(engine).get_table_names(), "必须提供空测试库，禁止覆盖已有数据"
# 仅测试建库：省略模型中 MySQL 8.4 不接受的旧 JSON 字面默认值。
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSON):
            column.server_default = None
Base.metadata.create_all(engine)
repo = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("migration94", repo / "alembic/versions/20261015_0094_state_geometry.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with engine.begin() as connection:
    module.op = Operations(MigrationContext.configure(connection))
    module.downgrade()
os.environ["DATABASE_URL"] = url
config = Config(str(repo / "alembic.ini"))
config.set_main_option("script_location", str(repo / "alembic"))
command.stamp(config, ["20260914_0052", "20261014_0137"])
command.upgrade(config, "head")
print("隔离模型 schema 的 #94 降级、双头合并升级通过")
