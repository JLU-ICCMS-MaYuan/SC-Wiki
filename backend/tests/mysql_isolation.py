"""独立MySQL验收的写入准入；不把测试开关当作业务库写入许可。"""
import os
from pathlib import Path
import re

from sqlalchemy import text


def require_isolated_mysql(engine):
    url = engine.url
    assert os.environ.get('SCWIKI_SPECTRA_MYSQL_TEST') == '1', '未显式启用隔离MySQL验收'
    assert engine.dialect.name == 'mysql' and url.host in {'127.0.0.1', 'localhost'}, '只允许本机隔离实例'
    assert url.port and url.port != 3307, '不得复用本地业务MySQL端口'
    assert re.fullmatch(r'issue137_test_[a-f0-9]{12}', url.database or ''), '数据库不属于独立测试命名空间'
    expected = os.environ.get('SCWIKI_MYSQL_TEST_DATADIR')
    assert expected and Path(expected).is_absolute(), '必须声明本次独立实例的数据目录'
    with engine.connect() as connection:
        database, port, datadir = connection.execute(text('SELECT DATABASE(), @@port, @@datadir')).one()
    assert database == url.database and port == url.port, '实际MySQL目标不匹配'
    assert Path(datadir).resolve() == Path(expected).resolve(), '实际数据目录不属于本次隔离实例'
