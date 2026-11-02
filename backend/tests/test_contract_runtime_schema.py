"""固定本机受测迁移头；暂缓分支必须显式登记，不能放行未知源码或数据库头。"""
import json
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, text
from alembic.script import ScriptDirectory
from scripts.local_deploy import schema


@pytest.mark.parametrize('source_heads,db_heads,deferred,success', [
    (['applied','parallel'], ['applied'], ['parallel'], True),
    (['applied','parallel','unreviewed'], ['applied'], ['parallel'], False),
    (['applied','parallel'], ['applied','parallel'], ['parallel'], False),
    (['applied','parallel'], ['applied'], ['applied','parallel'], False),
])
def test_explicit_pinned_runtime_schema(tmp_path, monkeypatch, source_heads, db_heads, deferred, success):
    (tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/local-deploy-schema.json').write_text(json.dumps({
        'schema_heads':['applied'], 'deferred_source_heads':deferred, 'tables':{}}))
    monkeypatch.setattr(schema, 'versions', lambda root: {'schema_heads':['applied']})
    monkeypatch.setattr(schema, 'config', lambda root: None)
    monkeypatch.setattr(ScriptDirectory, 'from_config', lambda cfg: SimpleNamespace(get_heads=lambda:source_heads))
    url = 'sqlite:///' + str(tmp_path/'isolated.sqlite')
    with create_engine(url).begin() as conn:
        conn.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(64))'))
        for head in db_heads:
            conn.execute(text('INSERT INTO alembic_version VALUES (:head)'), {'head':head})
    if success:
        schema.verify_schema(tmp_path,url)
    else:
        with pytest.raises(ValueError):
            schema.verify_schema(tmp_path,url)
