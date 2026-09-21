"""业务数据库原生导出与恢复，运行目录和权限由调用方隔离。"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlparse, quote

from .bundle import write_json
from .paths import FILE_DIRS, FILE_NAMES, JSON_COLUMNS, relocate, references


def redis_connection(values):
    from redis import Redis
    return Redis.from_url(values['REDIS_URL'], decode_responses=True, socket_timeout=10)


def assert_no_jobs(client):
    from rq import Queue
    from rq.registry import StartedJobRegistry, ScheduledJobRegistry, DeferredJobRegistry
    from redis import Redis
    # RQ 的二进制作业载荷绝不反序列化；只检查队列和 registry 的数量。
    connection = Redis(connection_pool=client.connection_pool)
    for queue in Queue.all(connection=connection):
        if queue.count or any(client.zcard(reg(queue.name, connection=connection).key)
                              for reg in (StartedJobRegistry, ScheduledJobRegistry, DeferredJobRegistry)):
            raise ValueError('存在执行、排队或延迟重试任务；请处理完毕后打包')


def export_redis(client) -> dict:
    from backend.ingest.upload_contracts import RUNNING_STATUSES, UPLOAD_STATE_SCHEMA_VERSION
    assert_no_jobs(client)
    result = {'exported_at': time.time(), 'tasks': []}
    for key in sorted(client.scan_iter('upload:*:state')):
        match = re.fullmatch(r'upload:([0-9a-f]{32}):state', key)
        if not match:
            raise ValueError('存在不支持的上传状态键')
        raw = client.get(key)
        if raw is None:
            continue
        state = json.loads(raw)
        if state.get('status') in RUNNING_STATUSES:
            raise ValueError('存在尚未结束的上传任务，不能打包')
        if state.get('state_schema_version') != UPLOAD_STATE_SCHEMA_VERSION or not state.get('user_id'):
            raise ValueError('上传任务状态版本或用户归属无效')
        task = {'task_id': match[1], 'state': state}
        for suffix in ('state', 'draft'):
            name = f'upload:{match[1]}:{suffix}'
            value = client.get(name)
            ttl = client.pttl(name)
            task[suffix] = json.loads(value) if value is not None else None
            task[suffix + '_expires_at'] = time.time() + ttl / 1000 if ttl >= 0 else None
        result['tasks'].append(task)
    return result


def restore_redis(client, payload: dict, users: set, source: Path, target: Path) -> dict:
    if client.dbsize():
        raise ValueError('Redis 目标必须为空')
    counts = {'restored': 0, 'expired': 0}
    for task in payload['tasks']:
        state = task['state']
        if state['user_id'] not in users:
            raise ValueError('草稿引用不存在的用户')
        deadlines = [v for v in (task['state_expires_at'], state.get('cleanup_at')) if v is not None]
        if deadlines and min(deadlines) <= time.time():
            counts['expired'] += 1
            continue
        with client.pipeline(transaction=True) as pipeline:
            for suffix in ('state', 'draft'):
                data = task[suffix]
                if data is None:
                    continue
                expiry = task[suffix + '_expires_at']
                if suffix == 'state' and deadlines:
                    expiry = min(deadlines)
                if expiry is not None and expiry <= time.time():
                    continue
                data = relocate(data, source, target)
                if suffix == 'state':
                    data = {k: v for k, v in data.items() if k not in ('job_id', 'processing_job_id')}
                key = f"upload:{task['task_id']}:{suffix}"
                pipeline.set(key, json.dumps(data, ensure_ascii=False))
                if expiry is not None:
                    pipeline.pexpireat(key, math.ceil(expiry * 1000))
            pipeline.zadd(f"upload:user:{state['user_id']}:tasks", {task['task_id']: state['updated_at']})
            pipeline.execute()
        counts['restored'] += 1
    # 提升目录前先落盘，不能把仅在内存里的草稿报告为已经恢复。
    client.save()
    return counts


def mysql_connection(url: str):
    import pymysql
    parsed = urlparse(url)
    return pymysql.connect(host=parsed.hostname, port=parsed.port or 3306,
                           user=unquote(parsed.username or ''), password=unquote(parsed.password or ''),
                           database=parsed.path.lstrip('/'), charset='utf8mb4',
                           connect_timeout=10, read_timeout=300, autocommit=True)


def identifier(name):
    return '`' + name.replace('`', '``') + '`'


def normalized_ddl(value):
    value = re.sub(r' AUTO_INCREMENT=\d+', '', value)
    value = re.sub(r'DEFINER=`(?:[^`]|``)*`@`(?:[^`]|``)*`', 'DEFINER=CURRENT_USER', value)
    return value


def mysql_inventory(url: str) -> dict:
    with mysql_connection(url) as connection, connection.cursor() as cursor:
        cursor.execute('SHOW FULL TABLES')
        tables = cursor.fetchall()
        result = {'tables': {}, 'objects': {}, 'database': urlparse(url).path.lstrip('/')}
        for name, kind in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {identifier(name)}')
            count = cursor.fetchone()[0]
            cursor.execute(f'SHOW CREATE TABLE {identifier(name)}')
            ddl = normalized_ddl(cursor.fetchone()[1])
            result['tables'][name] = {'rows': count, 'kind': kind, 'ddl': hashlib.sha256(ddl.encode()).hexdigest()}
        cursor.execute('SELECT version_num FROM alembic_version ORDER BY version_num')
        result['heads'] = [row[0] for row in cursor.fetchall()]
        for category, query in (
            ('triggers', 'SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()'),
            ('routines', 'SELECT ROUTINE_NAME,ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE()'),
            ('events', 'SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE()'),
        ):
            cursor.execute(query)
            definitions = []
            for row in cursor.fetchall():
                object_type = row[1] if category == 'routines' else ('TRIGGER' if category == 'triggers' else 'EVENT')
                cursor.execute(f'SHOW CREATE {object_type} {identifier(row[0])}')
                columns = [c[0].lower() for c in cursor.description]
                values = cursor.fetchone()
                ddl_index = next(i for i, column in enumerate(columns) if column.startswith('create ') or column == 'sql original statement')
                definitions.append({'name': row[0], 'type': object_type,
                                    'ddl': hashlib.sha256(normalized_ddl(values[ddl_index]).encode()).hexdigest()})
            result['objects'][category] = sorted(definitions, key=lambda v: (v['name'], v['type']))
        return result


@contextmanager
def mysql_defaults(url: str):
    parsed = urlparse(url)
    def escaped(value):
        return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    with tempfile.TemporaryDirectory(prefix='scwiki-mysql-') as temporary:
        path = Path(temporary) / 'client.cnf'
        path.touch(mode=0o600)
        fields = {'host': parsed.hostname, 'port': parsed.port or 3306,
                  'user': unquote(parsed.username or ''), 'password': unquote(parsed.password or '')}
        path.write_text('[client]\n' + ''.join(f'{k}="{escaped(v)}"\n' for k, v in fields.items()))
        yield path


def check_mysql_export(url: str, *, inspection_connection=None):
    """只读确认完整事件可见性及实际写入风险，不修改调度开关。"""
    with mysql_connection(url) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT @@server_uuid')
        server_uuid = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE '
                       'WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_SCHEMA IS NOT NULL '
                       'AND REFERENCED_TABLE_SCHEMA<>DATABASE()')
        if cursor.fetchone()[0]:
            raise ValueError('业务库存在跨库外键，不能独立迁移')
    factory = inspection_connection or (lambda: mysql_connection(url))
    with factory() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT @@server_uuid')
        if cursor.fetchone()[0] != server_uuid:
            raise ValueError('事件检查连接与业务库不是同一 MySQL 实例')
        cursor.execute('SHOW GRANTS')
        privileges = [row[0].split(' ON *.* ', 1)[0].removeprefix('GRANT ').split(', ')
                      for row in cursor.fetchall() if ' ON *.* ' in row[0]]
        if not any('ALL PRIVILEGES' in grant or 'EVENT' in grant for grant in privileges):
            raise ValueError('事件检查需要全局 EVENT 可见权限，不能把不可见事件当作不存在')
        cursor.execute('SELECT @@event_scheduler')
        scheduler = str(cursor.fetchone()[0]).upper()
        cursor.execute("SELECT COUNT(*) FROM information_schema.EVENTS WHERE STATUS='ENABLED'")
        enabled = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM performance_schema.threads WHERE NAME='thread/sql/event_worker'")
        if cursor.fetchone()[0]:
            raise ValueError('MySQL 事件正在执行，请等待结束后再冻结')
        if scheduler == 'ON' and enabled:
            raise ValueError(f'MySQL 存在 {enabled} 个启用事件，无法保证冻结期间不写入；请先确认其计划')


def export_mysql(url: str, binary: Path, output: Path, *, inspection_connection=None):
    check_mysql_export(url, inspection_connection=inspection_connection)
    output.parent.mkdir(parents=True, exist_ok=True)
    before = mysql_inventory(url)
    with mysql_defaults(url) as defaults, output.open('wb') as stream:
        result = subprocess.run([str(binary), f'--defaults-file={defaults}', '--single-transaction',
                                 '--routines', '--triggers', '--events', '--hex-blob', '--set-gtid-purged=OFF',
                                 '--no-tablespaces', '--default-character-set=utf8mb4', before['database']],
                                stdout=stream, stderr=subprocess.PIPE, timeout=1800)
        if result.returncode:
            raise ValueError('MySQL 导出失败；未发布迁移包')
    check_mysql_export(url, inspection_connection=inspection_connection)
    if mysql_inventory(url) != before:
        raise ValueError('MySQL 导出期间发生写入，拒绝发布包')
    return before


def restore_mysql(url: str, binary: Path, source: Path):
    with mysql_connection(url) as connection, connection.cursor() as cursor:
        cursor.execute('SHOW TABLES')
        if cursor.fetchall():
            raise ValueError('MySQL 恢复目标必须为空')
    # dump 只接受本工具生成且完整校验过的可信私有包。
    with tempfile.TemporaryDirectory(prefix='scwiki-sql-') as temporary:
        rewritten = Path(temporary) / 'business.sql'
        rewritten.touch(mode=0o600)
        with source.open() as src, rewritten.open('w') as dst:
            for line in src:
                # 仅在 mysqldump 的对象定义指令中替换 DEFINER，不碰 INSERT 科学文本。
                if line.startswith(('/*!', 'CREATE DEFINER=')):
                    line = re.sub(r'DEFINER=`(?:[^`]|``)*`@`(?:[^`]|``)*`', 'DEFINER=CURRENT_USER', line)
                dst.write(line)
        with mysql_defaults(url) as defaults, rewritten.open('rb') as stream:
            result = subprocess.run([str(binary), f'--defaults-file={defaults}', '--binary-mode',
                                     urlparse(url).path.lstrip('/')], stdin=stream,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
            if result.returncode:
                raise ValueError('MySQL 导入失败，临时实例未发布')


@contextmanager
def preserve_revision_baselines(url):
    """仅将源端仍有效的返修并发基线随路径迁移，绝不修复原有冲突。"""
    from sqlalchemy import create_engine, select, update
    from sqlalchemy.orm import Session
    from .schema import database_environment
    with database_environment(url):
        from backend.models import Paper, PaperRevisionDraft
        from backend.services.paper_revisions import fingerprint
    engine = create_engine(url)
    valid = []
    try:
        with Session(engine) as session:
            for saved in session.scalars(select(PaperRevisionDraft).where(PaperRevisionDraft.draft.is_not(None))):
                paper = session.get(Paper, saved.paper_id)
                if (paper and paper.review_status == 'rejected' and saved.base_revision == paper.content_revision
                        and saved.base_fingerprint == fingerprint(session, paper)):
                    valid.append((saved.paper_id, saved.revision_id, saved.base_fingerprint))
        yield
        with Session(engine) as session:
            for paper_id, revision_id, old in valid:
                saved = session.get(PaperRevisionDraft, paper_id)
                if saved.revision_id != revision_id or saved.base_fingerprint != old:
                    raise ValueError('恢复期间返修草稿发生并发变化')
                new = fingerprint(session, session.get(Paper, paper_id))
                session.execute(update(PaperRevisionDraft).where(PaperRevisionDraft.paper_id == paper_id)
                                .values(base_fingerprint=new, updated_at=saved.updated_at))
            session.commit()
    finally:
        engine.dispose()


def relocate_mysql(url: str, source: Path, target: Path, *, check_files=False):
    if not check_files and source != target:
        with preserve_revision_baselines(url):
            return _relocate_mysql(url, source, target, check_files=check_files)
    return _relocate_mysql(url, source, target, check_files=check_files)


def _relocate_mysql(url: str, source: Path, target: Path, *, check_files=False):
    mappings = []
    with mysql_connection(url) as connection, connection.cursor() as cursor:
        cursor.execute('SHOW TABLES')
        tables = {r[0] for r in cursor.fetchall()}
        columns = {**JSON_COLUMNS, 'paper_files': ('stored_path',)}
        for table, fields in columns.items():
            if table not in tables:
                continue
            key = {'scientific_upload_drafts': 'task_id', 'paper_revision_drafts': 'paper_id'}.get(table, 'id')
            for field in fields:
                last_id = '' if key == 'task_id' else -1
                while True:
                    cursor.execute(f'SELECT {identifier(key)},{identifier(field)} FROM {identifier(table)} WHERE {identifier(key)}>%s AND {identifier(field)} IS NOT NULL ORDER BY {identifier(key)} LIMIT 500', (last_id,))
                    rows = cursor.fetchall()
                    if not rows:
                        break
                    for row_id, raw in rows:
                        payload = json.loads(raw) if table != 'paper_files' else {'stored_path': raw}
                        result = relocate(payload, source, target, check_files=check_files)
                        if check_files:
                            mappings.extend({'store': table + '.' + field, 'record_id': row_id, **item}
                                            for item in references(payload, source))
                        if not check_files and result != payload:
                            encoded = json.dumps(result, ensure_ascii=False) if table != 'paper_files' else result['stored_path']
                            cursor.execute(f'UPDATE {identifier(table)} SET {identifier(field)}=%s WHERE {identifier(key)}=%s', (encoded, row_id))
                    last_id = rows[-1][0]
    return mappings


def check_file_layout(source: Path):
    # 历史 SQL 备份可能含旧凭据，测试临时文件也不属于当前业务快照。
    excluded = {'mysql', 'neo4j', 'redis', 'qdrant', 'runtime', 'backups', 'tmp', '.deployment-owner.json'}
    unknown = {p.name for p in source.iterdir()} - set(FILE_DIRS) - set(FILE_NAMES) - excluded
    if unknown:
        raise ValueError('发现未登记的数据目录：' + ', '.join(sorted(unknown)))


def copy_files(source: Path, target: Path):
    check_file_layout(source)
    target.mkdir(parents=True, exist_ok=True)
    for name in (*FILE_DIRS, *FILE_NAMES):
        path = source / name
        if not path.exists():
            continue
        candidates = [path, *path.rglob('*')] if path.is_dir() else [path]
        if any(p.is_symlink() for p in candidates):
            raise ValueError('应用数据包含符号链接，拒绝打包')
        if path.is_dir():
            shutil.copytree(path, target / name)
        else:
            shutil.copy2(path, target / name)


def relocate_files(directory: Path, source: Path, target: Path, *, check_files=False):
    mappings = []
    for name in ('review_artifacts', 'parsed_markdown', 'upload_PDFs'):
        for path in (directory / name).rglob('*.json'):
            value = json.loads(path.read_text())
            changed = relocate(value, source, target, check_files=check_files)
            if check_files:
                mappings.extend({'store': 'file', 'record_id': path.relative_to(directory).as_posix(), **item}
                                for item in references(value, source))
            if not check_files and changed != value:
                write_json(path, changed)
    return mappings


def qdrant_client(values):
    import httpx
    return httpx.Client(base_url=f"http://{values['QDRANT_HOST']}:{values.get('QDRANT_PORT', '6333')}",
                        timeout=300, trust_env=False)


def qrequest(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if not response.is_success:
        raise ValueError(f'Qdrant {method} 请求失败（{response.status_code}）')
    return response.json()['result']


def qdrant_inventory(client):
    result = {'collections': {}, 'aliases': qrequest(client, 'GET', '/aliases')['aliases']}
    for item in qrequest(client, 'GET', '/collections')['collections']:
        name = item['name']
        path = '/collections/' + quote(name, safe='')
        info = qrequest(client, 'GET', path)
        count = qrequest(client, 'POST', path + '/points/count', json={'exact': True})['count']
        result['collections'][name] = {'points': count, 'config': info['config']}
    result['aliases'] = sorted(result['aliases'], key=lambda a: a['alias_name'])
    return result


def export_qdrant(values, destination: Path):
    destination.mkdir(parents=True)
    with qdrant_client(values) as client:
        result = qdrant_inventory(client)
        for index, name in enumerate(sorted(result['collections'])):
            base = '/collections/' + quote(name, safe='') + '/snapshots'
            snapshot = qrequest(client, 'POST', base)['name']
            path = destination / f'{index}.snapshot'
            try:
                with client.stream('GET', base + '/' + quote(snapshot, safe='')) as response:
                    response.raise_for_status()
                    with path.open('wb') as stream:
                        for chunk in response.iter_bytes():
                            stream.write(chunk)
            finally:
                qrequest(client, 'DELETE', base + '/' + quote(snapshot, safe=''))
            result['collections'][name]['snapshot'] = path.name
        write_json(destination / 'inventory.json', result)
        return result


def restore_qdrant(values, source: Path, expected: dict):
    with qdrant_client(values) as client:
        if qrequest(client, 'GET', '/collections')['collections']:
            raise ValueError('Qdrant 恢复目标必须为空')
        for name, data in expected['collections'].items():
            with (source / data['snapshot']).open('rb') as stream:
                qrequest(client, 'POST', '/collections/' + quote(name, safe='') + '/snapshots/upload',
                         params={'priority': 'snapshot', 'wait': 'true'}, files={'snapshot': stream})
        if expected['aliases']:
            qrequest(client, 'POST', '/collections/aliases', json={'actions': [{'create_alias': a} for a in expected['aliases']]})
        actual = qdrant_inventory(client)
        clean = {'collections': {n: {k: v for k, v in d.items() if k != 'snapshot'} for n, d in expected['collections'].items()},
                 'aliases': expected['aliases']}
        if actual != clean:
            raise ValueError('Qdrant 恢复数量或配置不一致')


def neo4j_inventory(values):
    from neo4j import GraphDatabase
    with GraphDatabase.driver(values['NEO4J_URI'], auth=(values.get('NEO4J_USER', 'neo4j'), values['NEO4J_PASSWORD'])) as driver:
        with driver.session(database='system') as session:
            names = {r['name'] for r in session.run('SHOW DATABASES YIELD name RETURN name')}
            if names - {'system', 'neo4j'}:
                raise ValueError('Neo4j 存在额外业务数据库，不能遗漏打包')
        with driver.session(database='neo4j') as session:
            nodes = session.run('MATCH (n) RETURN count(n) AS n').single()['n']
            edges = session.run('MATCH ()-[r]->() RETURN count(r) AS n').single()['n']
            indexes = [dict(row) for row in session.run('SHOW INDEXES YIELD name,type,entityType,labelsOrTypes,properties RETURN name,type,entityType,labelsOrTypes,properties ORDER BY name')]
            constraints = [dict(row) for row in session.run('SHOW CONSTRAINTS YIELD name,type,entityType,labelsOrTypes,properties RETURN name,type,entityType,labelsOrTypes,properties ORDER BY name')]
            return {'nodes': nodes, 'relationships': edges, 'indexes': indexes, 'constraints': constraints}


def initialize_neo4j_password(values):
    """新实例通过本机 Bolt 设置密码，避免将密码放入命令行参数。"""
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError
    uri = values['NEO4J_URI']
    user = values.get('NEO4J_USER', 'neo4j')
    password = values['NEO4J_PASSWORD']
    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            driver.verify_connectivity()
        return
    except AuthError:
        pass
    if user != 'neo4j':
        raise ValueError('新 Neo4j 实例必须使用 neo4j 管理账号初始化')
    with GraphDatabase.driver(uri, auth=('neo4j', 'neo4j')) as driver:
        with driver.session(database='system') as session:
            session.run('ALTER CURRENT USER SET PASSWORD FROM $old TO $new', old='neo4j', new=password).consume()
