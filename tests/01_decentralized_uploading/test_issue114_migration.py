"""执行真实增量 DDL 与外键；只接受全新隔离测试库或内存 SQLite。"""
import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture(params=["sqlite", "mysql"])
def connection(request):
    url="sqlite:///:memory:"
    if request.param=="mysql":
        url=os.environ.get("ISSUE114_TEST_MYSQL_URL")
        if not url:
            pytest.skip("需要隔离 MySQL 测试库")
        parsed=sa.engine.make_url(url)
        assert parsed.host in {"localhost","127.0.0.1"} and parsed.database.startswith("test_issue114_")
    engine=sa.create_engine(url)
    with engine.begin() as c:
        assert not sa.inspect(c).get_table_names(), "测试库必须为空"
        if c.dialect.name=="sqlite":
            c.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata=sa.MetaData()
        sa.Table("papers",metadata,sa.Column("id",sa.Integer,primary_key=True),sa.Column("content_revision",sa.Integer),
                 sa.UniqueConstraint("id","content_revision"))
        sa.Table("paper_files",metadata,sa.Column("id",sa.Integer,primary_key=True),sa.Column("paper_id",sa.Integer),sa.Column("paper_revision",sa.Integer),
                 sa.UniqueConstraint("id","paper_id","paper_revision"),
                 sa.ForeignKeyConstraint(["paper_id","paper_revision"],["papers.id","papers.content_revision"],onupdate="CASCADE",ondelete="CASCADE"))
        sa.Table("paper_evidences",metadata,sa.Column("id",sa.Integer,primary_key=True),sa.Column("paper_id",sa.Integer),sa.Column("paper_revision",sa.Integer),
                 sa.UniqueConstraint("id","paper_id","paper_revision"),
                 sa.ForeignKeyConstraint(["paper_id","paper_revision"],["papers.id","papers.content_revision"],onupdate="CASCADE",ondelete="CASCADE"))
        metadata.create_all(c)
        module_path=Path(__file__).parents[2]/"alembic/versions/20260923_0114_document_ir.py"
        spec=importlib.util.spec_from_file_location("migration114",module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(c)):
            module.upgrade()
        yield c
        with Operations.context(MigrationContext.configure(c)):
            module.downgrade()
        metadata.drop_all(c)
    engine.dispose()


def test_incremental_schema_revision_and_delete(connection):
    c=connection
    c.execute(sa.text("INSERT INTO papers VALUES (1,1)"))
    c.execute(sa.text("INSERT INTO paper_files VALUES (10,1,1)"))
    c.execute(sa.text("INSERT INTO paper_evidences VALUES (20,1,1)"))
    metadata=sa.MetaData();metadata.reflect(c)
    runs=metadata.tables["paper_document_parser_runs"]
    blocks=metadata.tables["paper_document_blocks"]
    locators=metadata.tables["paper_evidence_locators"]
    c.execute(runs.insert().values(id=30,paper_id=1,paper_revision=1,paper_file_id=10,parse_profile="text",
        parser_name="pymupdf",parser_version="1",mode="text",status="succeeded",document_json={}))
    c.execute(blocks.insert().values(id=40,paper_id=1,paper_revision=1,paper_file_id=10,parser_run_id=30,
        block_id="block",block_type="paragraph",pdf_page=1,text="200 K",content_hash="a"*64))
    c.execute(locators.insert().values(id=50,paper_id=1,paper_revision=1,paper_file_id=10,parser_run_id=30,
        paper_evidence_id=20,document_block_id=40,pdf_page=1,quote="200 K",parser_name="pymupdf",parser_version="1",locator_hash="b"*64))
    c.execute(sa.text("UPDATE papers SET content_revision=2 WHERE id=1"))
    for table in (runs,blocks,locators):
        assert c.scalar(sa.select(table.c.paper_revision))==2
    with c.begin_nested() as savepoint:
        c.execute(sa.text("UPDATE papers SET content_revision=3 WHERE id=1"))
        savepoint.rollback()
    assert c.scalar(sa.select(locators.c.paper_revision))==2
    c.execute(sa.text("DELETE FROM paper_evidences WHERE id=20"))
    assert c.scalar(sa.select(sa.func.count()).select_from(locators))==0
    c.execute(sa.text("DELETE FROM paper_files WHERE id=10"))
    assert c.scalar(sa.select(sa.func.count()).select_from(blocks))==0
    assert c.scalar(sa.select(sa.func.count()).select_from(runs))==0
