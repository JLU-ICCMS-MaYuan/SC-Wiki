"""隔离验收入口须在连接/写入前拒绝业务地址和不明确的目标。"""
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from backend.tests.mysql_isolation import require_isolated_mysql


@pytest.mark.parametrize('url', [
    'mysql+pymysql://root@127.0.0.1:3307/issue137_test_123456abcdef',
    'mysql+pymysql://root@127.0.0.1:54321/scwiki',
    'mysql+pymysql://root@remote.example:54321/issue137_test_123456abcdef',
    'mysql+pymysql://root@127.0.0.1:54321/issue137_test_ambiguous',
])
def test_nonisolated_target_is_refused_before_connecting(monkeypatch,url,tmp_path):
    monkeypatch.setenv('SCWIKI_SPECTRA_MYSQL_TEST','1')
    monkeypatch.setenv('SCWIKI_MYSQL_TEST_DATADIR',str(tmp_path))
    engine=SimpleNamespace(url=make_url(url),dialect=SimpleNamespace(name='mysql'),
        connect=lambda:pytest.fail('不应连接非本次隔离目标'))
    with pytest.raises(AssertionError):require_isolated_mysql(engine)


def test_missing_explicit_authorization_is_refused(monkeypatch):
    monkeypatch.delenv('SCWIKI_SPECTRA_MYSQL_TEST',raising=False)
    engine=SimpleNamespace(url=make_url('mysql+pymysql://root@127.0.0.1:54321/issue137_test_123456abcdef'))
    with pytest.raises(AssertionError,match='未显式启用'):require_isolated_mysql(engine)
