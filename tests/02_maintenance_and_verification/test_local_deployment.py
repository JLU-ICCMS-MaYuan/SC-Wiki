"""Portable deployment contracts; all filesystem writes stay in tmp_path."""
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def module(name):
    assert (ROOT / 'scripts/local_deploy' / f'{name}.py').is_file(), f'{name} is not implemented'
    return importlib.import_module(f'scripts.local_deploy.{name}')


def test_configuration_never_executes_shell(tmp_path):
    config = module('config')
    marker = tmp_path / 'executed'
    with pytest.raises(ValueError):
        config.parse_env(f'PASSWORD=$(touch {marker})\n')
    assert not marker.exists()
    result = config.parse_env("PASSWORD='a b$word#x'\nURL=mysql://${PASSWORD}@localhost/db\nEMPTY=\n")
    assert result == {'PASSWORD': 'a b$word#x', 'URL': 'mysql://a b$word#x@localhost/db', 'EMPTY': ''}


def test_generated_config_is_private_and_existing_config_is_unchanged(tmp_path):
    config = module('config')
    path = tmp_path / '.env'
    first = config.ensure_config(tmp_path)
    original = path.read_bytes()
    assert first['DATABASE_URL'].endswith('/scwiki?charset=utf8mb4')
    assert first['JWT_SECRET_KEY'] and first['MYSQL_PASSWORD']
    assert path.stat().st_mode & 0o777 == 0o600
    assert config.ensure_config(tmp_path) == first
    assert path.read_bytes() == original


@pytest.mark.parametrize('text', ['A=${MISSING}', 'A=x\nA=y', 'not an assignment', 'PATH=x', 'A=`id`'])
def test_configuration_rejects_ambiguous_or_process_control_entries(text):
    with pytest.raises(ValueError):
        module('config').parse_env(text)


def test_environment_selects_actual_prefix_and_rejects_ambiguity(tmp_path):
    env = module('environment')
    prefix = tmp_path / 'unusual/envs/sc-wiki'
    assert env.select_prefix([str(prefix)]) == prefix
    assert env.select_prefix([]) is None
    with pytest.raises(ValueError, match='多个'):
        env.select_prefix([str(prefix), '/another/envs/sc-wiki'])


@pytest.fixture
def preflight_root(tmp_path, monkeypatch):
    env = module('environment')
    root = tmp_path / 'source with spaces'
    (root / 'scripts').mkdir(parents=True)
    shutil.copy2(ROOT / 'scripts/local-deploy-versions.json', root / 'scripts')
    monkeypatch.setattr(env.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(env.platform, 'machine', lambda: 'x86_64')
    monkeypatch.setattr(env.shutil, 'disk_usage', lambda _: shutil._ntuple_diskusage(32 * 1024**3, 0, 32 * 1024**3))
    monkeypatch.setattr(env.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(env, 'run', lambda *args, **kwargs: '28.0.0\n')
    return root


@pytest.mark.parametrize('failure', [None, ValueError('private daemon output'), subprocess.TimeoutExpired('docker', 15)])
def test_preflight_docker_available_failed_or_timed_out(preflight_root, monkeypatch, failure):
    env = module('environment')

    def docker_info(args, **kwargs):
        assert args == ['docker', 'info', '--format', '{{.ServerVersion}}']
        assert kwargs == {'capture': True, 'timeout': 15}
        if failure:
            raise failure
        return '28.0.0\n'

    monkeypatch.setattr(env, 'run', docker_info)
    problems = env.preflight(preflight_root, occupied_ok=True)
    assert problems == (['Docker 未运行或当前用户无访问权限'] if failure else [])
    guidance = env.preflight_guidance(problems)
    assert ('docker info' in ' '.join(guidance)) == bool(failure)
    assert 'private daemon output' not in ' '.join(problems + guidance)


@pytest.mark.parametrize('check_only', [False, True])
@pytest.mark.parametrize('docker_present', [False, True])
def test_real_cli_docker_block_is_read_only(tmp_path, check_only, docker_present):
    root = tmp_path / 'source with spaces'
    (root / 'scripts').mkdir(parents=True)
    shutil.copy2(ROOT / 'scripts/local-deploy-versions.json', root / 'scripts')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    for tool in ('bash', 'make', 'curl', 'tar', 'setsid', 'ss', 'dirname'):
        executable = shutil.which(tool)
        if not executable:
            pytest.skip(f'真实入口测试需要 {tool}')
        (bindir / tool).symlink_to(executable)
    (bindir / 'python3').symlink_to(sys.executable)
    if docker_present:
        docker = bindir / 'docker'
        docker.write_text('#!/bin/bash\necho private-daemon-output >&2\nexit 1\n')
        docker.chmod(0o755)
    args = ['bash', str(ROOT / 'scripts/locallydeploy.sh'), '--root', str(root)]
    if check_only:
        args.append('--check-only')
    process_env = {key: value for key, value in os.environ.items() if key not in ('BUNDLE', 'CHECK_ONLY')}
    result = subprocess.run(args, env={**process_env, 'PATH': str(bindir)}, capture_output=True, text=True, timeout=30)
    assert result.returncode == 2, result.stderr
    assert result.stdout, result.stderr
    report = json.loads(result.stdout)
    assert report['result'] == 'blocked'
    assert report['error_code'] == 'preflight_failed'
    assert report['phase'] == 'preflight'
    assert ('Docker 未运行或当前用户无访问权限' if docker_present else '缺少系统前置工具 docker') in report['problems']
    assert report['environment'].startswith('未检查')
    assert report['conda'] is None
    assert 'docker info' in ' '.join(report['next_steps'])
    assert 'private-daemon-output' not in result.stdout + result.stderr
    assert sorted(str(p.relative_to(root)) for p in root.rglob('*')) == ['scripts', 'scripts/local-deploy-versions.json']


def test_preflight_rejects_real_port_conflict_and_low_space(preflight_root, monkeypatch):
    env = module('environment')
    monkeypatch.setattr(env.shutil, 'disk_usage', lambda _: shutil._ntuple_diskusage(8 * 1024**3, 1, 8 * 1024**3 - 1))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        monkeypatch.setattr(env, 'PORTS', (port,))
        problems = env.preflight(preflight_root)
        assert problems == [f'端口 {port} 已被占用，不能复用未知服务', '可用磁盘不足 8 GiB，无法准备依赖与临时数据']
        assert len(env.preflight_guidance(problems)) == 2


@pytest.mark.parametrize('failure', [None, ValueError('offline'), subprocess.TimeoutExpired('curl', 1200)])
def test_failed_download_preserves_cache_and_removes_partial(tmp_path, monkeypatch, failure):
    env = module('environment')
    target = tmp_path / 'installer'
    target.write_bytes(b'existing cache')

    def failed_download(args, **kwargs):
        Path(args[args.index('--output') + 1]).write_bytes(b'corrupt or partial download')
        if failure:
            raise failure

    monkeypatch.setattr(env, 'run', failed_download)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        env.download({'sha256': '0' * 64, 'url': 'https://example.invalid/installer'}, target)
    assert target.read_bytes() == b'existing cache'
    assert not target.with_name('installer.partial').exists()


def test_port_check_handles_listener_without_connecting():
    import socket
    runtime = module('runtime')
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(0)
        assert runtime.port_occupied(port)
        with socket.create_connection(('127.0.0.1', port), timeout=1) as client:
            accepted, _ = listener.accept()
            accepted.close()
            assert client.recv(1) == b''
    assert not runtime.port_occupied(port)


def test_pack_port_check_does_not_require_grobid_container(monkeypatch, tmp_path):
    runtime = module('runtime')
    monkeypatch.setattr(runtime, 'port_occupied', lambda port: port == 8070)

    def run(args, **kwargs):
        assert args == ['ss', '-ltnp'], '打包不应查询或操作无业务数据的 GROBID 容器'
        return ''

    monkeypatch.setattr(runtime, 'run', run)
    runtime.Runtime(tmp_path, tmp_path, {}).check_ports(check_grobid=False)


def test_pack_port_check_still_rejects_unknown_database(monkeypatch, tmp_path):
    runtime = module('runtime')
    monkeypatch.setattr(runtime, 'port_occupied', lambda port: port == 3307)
    monkeypatch.setattr(runtime, 'run', lambda *args, **kwargs: '')
    with pytest.raises(ValueError, match='3307 归属不明'):
        runtime.Runtime(tmp_path, tmp_path, {}).check_ports(check_grobid=False)


def test_deploy_port_check_still_rejects_foreign_grobid(monkeypatch, tmp_path):
    runtime = module('runtime')
    monkeypatch.setattr(runtime, 'port_occupied', lambda port: port == 8070)
    monkeypatch.setattr(runtime, 'run', lambda args, **kwargs: '' if args[0] == 'ss' else '/another/project')
    with pytest.raises(ValueError, match='GROBID 容器不属于当前项目'):
        runtime.Runtime(tmp_path, tmp_path, {}).check_ports()


def test_archive_rejects_escape_links_and_duplicates_before_writing(tmp_path):
    bundle = module('bundle')
    for names in [['../escape'], ['/absolute'], ['sc-wiki/a', 'sc-wiki/a']]:
        archive = tmp_path / 'bad.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name in names:
                item = tarfile.TarInfo(name)
                item.size = 1
                tar.addfile(item, io.BytesIO(b'x'))
        with pytest.raises(ValueError):
            bundle.extract_archive(archive, tmp_path / 'out')
        assert not (tmp_path / 'out').exists()
    with tarfile.open(archive, 'w:gz') as tar:
        item = tarfile.TarInfo('sc-wiki/link')
        item.type = tarfile.SYMTYPE
        item.linkname = '/etc'
        tar.addfile(item)
    with pytest.raises(ValueError):
        bundle.extract_archive(archive, tmp_path / 'out')


def test_bundle_roundtrip_detects_tampering_and_unlisted_payload(tmp_path):
    bundle = module('bundle')
    root = tmp_path / 'sc-wiki'
    (root / '.deployment/mysql').mkdir(parents=True)
    (root / 'Makefile').write_text('all:\n\ttrue\n')
    data = root / '.deployment/mysql/business.sql'
    data.write_text('select 1;')
    manifest = bundle.seal(root, {'source_commit': 'a' * 40, 'components': {}})
    assert bundle.verify(root)['bundle_id'] == manifest['bundle_id']
    archive = tmp_path / 'portable.tar.gz'
    bundle.publish(root, archive)
    assert archive.stat().st_mode & 0o777 == 0o600
    extracted = bundle.extract_archive(archive, tmp_path / 'extracted')
    assert bundle.verify(extracted)['bundle_id'] == manifest['bundle_id']
    with pytest.raises(ValueError, match='覆盖'):
        bundle.publish(root, archive)
    data.write_text('select 2;')
    with pytest.raises(ValueError, match='校验'):
        bundle.verify(root)
    data.write_text('select 1;')
    (root / '.deployment/extra').write_text('secret')
    with pytest.raises(ValueError, match='清单'):
        bundle.verify(root)


def test_state_rejects_existing_data_and_preserves_completed_data(tmp_path):
    state = module('state')
    data = tmp_path / '.data'
    data.mkdir()
    (data / 'precious').write_text('keep')
    with pytest.raises(ValueError, match='已有'):
        state.DeploymentState.open(tmp_path, 'bundle-1')
    assert (data / 'precious').read_text() == 'keep'
    root = tmp_path / 'fresh'
    root.mkdir()
    record = state.DeploymentState.open(root, 'bundle-1')
    staging = record.staging
    staging.mkdir()
    (staging / 'rows').write_text('one')
    record.promote()
    (root / '.data/rows').write_text('two')
    resumed = state.DeploymentState.open(root, 'bundle-1')
    assert resumed.promoted
    assert (root / '.data/rows').read_text() == 'two'
    with pytest.raises(ValueError):
        state.DeploymentState.open(root, 'bundle-2')


def test_operation_lock_rejects_concurrency_and_symlink(tmp_path):
    state = module('state')
    root = tmp_path / 'root'
    root.mkdir()
    with state.operation_lock(root):
        with pytest.raises(ValueError, match='另一'):
            with state.operation_lock(root):
                pass
    external = tmp_path / 'external'
    external.mkdir()
    other = tmp_path / 'other'
    other.mkdir()
    (other / '.local').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='符号链接'):
        with state.operation_lock(other):
            pass
    assert not list(external.iterdir())


def test_path_relocation_only_changes_registered_fields(tmp_path):
    paths = module('paths')
    source = tmp_path / 'source'
    (source / 'upload_PDFs').mkdir(parents=True)
    (source / 'upload_PDFs/a.pdf').write_bytes(b'pdf')
    value = {'files': [{'stored_path': str(source / 'upload_PDFs/a.pdf')}],
             'paper_quote': str(source / 'upload_PDFs/a.pdf'), 'fingerprint': 'keep'}
    relocated = paths.relocate(value, source, tmp_path / 'target', check_files=True)
    assert relocated['files'][0]['stored_path'] == str(tmp_path / 'target/upload_PDFs/a.pdf')
    assert relocated['paper_quote'] == value['paper_quote']
    assert relocated['fingerprint'] == 'keep'
    with pytest.raises(ValueError):
        paths.relocate({'file_path': '/elsewhere/missing'}, source, tmp_path / 'target', check_files=True)


def test_cli_check_only_does_not_create_runtime_files(tmp_path):
    cli = ROOT / 'scripts/locallydeploy.sh'
    assert cli.exists(), 'deployment entrypoint missing'
    result = subprocess.run(['bash', str(cli), '--root', str(tmp_path), '--check-only'],
                            capture_output=True, text=True)
    assert result.returncode != 0  # no source checkout
    assert list(tmp_path.iterdir()) == []
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize(('target', 'parameter'), [('pack', 'OUTPUT'), ('deploy', 'BUNDLE')])
def test_make_entrypoints_do_not_interpolate_shell_arguments(tmp_path, target, parameter):
    marker = tmp_path / 'injected'
    result = subprocess.run(['make', '-n', target, f'{parameter}=x; touch {marker}'],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, f'make {target} missing'
    assert str(marker) not in result.stdout
    assert not marker.exists()


def test_fresh_mysql_bootstrap_and_read_only_schema_validation(monkeypatch, tmp_path):
    url = os.environ.get('LOCAL_DEPLOY_TEST_MYSQL_URL')
    if not url:
        pytest.skip('需要显式隔离 MySQL 测试库')
    assert 'test' in url
    schema = module('schema')
    monkeypatch.setenv('DATABASE_URL', url)
    from sqlalchemy import create_engine, inspect, text
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), '测试库必须为空'
    schema.initialize(ROOT, url)
    schema.verify_schema(ROOT, url)
    with engine.begin() as connection:
        heads = set(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
        assert heads == {'20260914_0052', '20260918_0108'}
        assert connection.execute(text('SELECT COUNT(*) FROM periodic_table_elements')).scalar_one() == 118
        assert connection.execute(text('SELECT COUNT(*) FROM form_definitions')).scalar_one() > 0
    with pytest.raises(ValueError, match='空'):
        schema.initialize(ROOT, url)
    # 两种持久草稿的主键分别为 task_id、paper_id，不能假设所有表都使用 id。
    from sqlalchemy.orm import Session
    from backend.models import User, Paper, PaperFile, ScientificUploadDraft, PaperRevisionDraft
    from backend.services.paper_revisions import fingerprint, assert_current
    source = tmp_path / 'source'
    file = source / 'upload_PDFs/paper.pdf'
    file.parent.mkdir(parents=True)
    file.write_bytes(b'fixture')
    payload = {'file_path': str(file), 'paper_quote': str(file), 'fingerprint': 'unchanged'}
    with Session(engine) as session:
        user = User(email='portable@example.test', username='portable', password_hash='fixture', real_name='测试')
        session.add(user)
        session.flush()
        paper = Paper(year=2026, uploaded_by_user_id=user.id, review_status='rejected')
        session.add(paper)
        session.flush()
        session.add(PaperFile(paper_id=paper.id, paper_revision=1, role='main', original_filename='paper.pdf',
                              stored_path=str(file), sha256='a' * 64, size=7))
        session.flush()
        session.add(ScientificUploadDraft(task_id='a' * 32, owner_id=user.id, draft=payload, state=payload))
        session.add(PaperRevisionDraft(paper_id=paper.id, owner_id=user.id, base_revision=1, revision_id='b' * 32,
                                      base_fingerprint=fingerprint(session, paper), draft=payload))
        stale = Paper(year=2026, uploaded_by_user_id=user.id, review_status='rejected')
        session.add(stale)
        session.flush()
        stale_id = stale.id
        session.add(PaperRevisionDraft(paper_id=stale.id, owner_id=user.id, base_revision=1, revision_id='c' * 32,
                                      base_fingerprint='already-stale', draft={}))
        session.commit()
    storage = module('storage')
    assert len(storage.relocate_mysql(url, source, source, check_files=True)) == 4
    target = tmp_path / 'target'
    storage.relocate_mysql(url, source, target)
    with Session(engine) as session:
        for model in (ScientificUploadDraft, PaperRevisionDraft):
            saved = session.query(model).order_by(model.task_id if model is ScientificUploadDraft else model.paper_id).first().draft
            assert saved['file_path'] == str(target / 'upload_PDFs/paper.pdf')
            assert saved['paper_quote'] == payload['paper_quote']
            assert saved['fingerprint'] == 'unchanged'
        valid = session.query(PaperRevisionDraft).filter(PaperRevisionDraft.paper_id != stale_id).one()
        assert_current(session, session.get(Paper, valid.paper_id), valid)
        stale = session.get(PaperRevisionDraft, stale_id)
        assert stale.base_fingerprint == 'already-stale'
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as conflict:
            assert_current(session, session.get(Paper, stale_id), stale)
        assert conflict.value.status_code == 409
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE papers DROP COLUMN issue_number')
    with pytest.raises(ValueError, match='papers'):
        schema.verify_schema(ROOT, url)
    engine.dispose()


def test_redis_roundtrip_preserves_drafts_and_expiry_not_credentials(tmp_path):
    url = os.environ.get('LOCAL_DEPLOY_TEST_REDIS_URL')
    if not url:
        pytest.skip('需要显式隔离 Redis 测试库')
    import redis
    import time
    storage = module('storage')
    client = redis.Redis.from_url(url, decode_responses=True)
    assert client.dbsize() == 0, '隔离 Redis 必须为空'
    # 过期 RQ registry 元数据也要阻断，检查不能触发 RQ 自动 cleanup。
    client.zadd('rq:wip:scwiki-upload', {'old-job': 1})
    client.sadd('rq:queues', 'rq:queue:scwiki-upload')
    with pytest.raises(ValueError, match='任务'):
        storage.export_redis(client)
    assert client.zcard('rq:wip:scwiki-upload') == 1
    client.delete('rq:wip:scwiki-upload', 'rq:queues')
    task = 'a' * 32
    state = {'task_id': task, 'user_id': 7, 'status': 'ready', 'updated_at': 123,
             'state_schema_version': 1, 'cleanup_at': time.time() + 60}
    client.set(f'upload:{task}:state', json.dumps(state), ex=60)
    client.set(f'upload:{task}:draft', json.dumps({'paper_quote': 'unchanged'}), ex=60)
    client.set(f'upload:llm:{task}', 'fake-secret')
    client.set('session', 'fake-session')
    result = storage.export_redis(client)
    assert 'fake-secret' not in json.dumps(result)
    assert 'fake-session' not in json.dumps(result)
    destination = redis.Redis.from_url(url.rsplit('/', 1)[0] + '/1', decode_responses=True)
    assert destination.dbsize() == 0
    counts = storage.restore_redis(destination, result, {7}, tmp_path, tmp_path)
    assert counts == {'restored': 1, 'expired': 0}
    assert destination.ttl(f'upload:{task}:draft') <= 60
    assert destination.zrange('upload:user:7:tasks', 0, -1) == [task]
    assert destination.get(f'upload:llm:{task}') is None
    assert destination.get('session') is None
    state['status'] = 'queued'
    client.set(f'upload:{task}:state', json.dumps(state))
    with pytest.raises(ValueError, match='任务'):
        storage.export_redis(client)


def test_mysql_native_dump_roundtrip_including_constraints_and_binary(tmp_path):
    source = os.environ.get('LOCAL_DEPLOY_TEST_MYSQL_SOURCE')
    target = os.environ.get('LOCAL_DEPLOY_TEST_MYSQL_TARGET')
    if not source or not target:
        pytest.skip('需要两个显式隔离 MySQL 测试库')
    assert 'test' in source and 'test' in target and source != target
    storage = module('storage')
    with storage.mysql_connection(source) as conn, conn.cursor() as cursor:
        cursor.execute('SHOW TABLES')
        assert not cursor.fetchall()
        cursor.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)')
        cursor.execute("INSERT INTO alembic_version VALUES ('test-revision')")
        cursor.execute('CREATE TABLE parent (id INT PRIMARY KEY, text LONGTEXT, bytes BLOB)')
        cursor.execute('CREATE TABLE child (id INT PRIMARY KEY, parent_id INT, CONSTRAINT fk_child FOREIGN KEY (parent_id) REFERENCES parent(id))')
        cursor.execute('INSERT INTO parent VALUES (1,%s,%s)', ('中文正文 DEFINER=`x`@`y`', b'\x00\xff'))
        cursor.execute('INSERT INTO child VALUES (1,1)')
        cursor.execute('CREATE TRIGGER before_child BEFORE INSERT ON child FOR EACH ROW SET NEW.parent_id=1')
        cursor.execute('CREATE PROCEDURE read_parent() SELECT id FROM parent')
        cursor.execute('CREATE VIEW parent_view AS SELECT id FROM parent')
        cursor.execute('CREATE EVENT test_event ON SCHEDULE EVERY 1 DAY DISABLE DO SELECT 1')
    binary = Path(sys.executable).parent
    output = tmp_path / 'dump.sql'
    with storage.mysql_connection(source) as conn, conn.cursor() as cursor:
        cursor.execute('SET GLOBAL event_scheduler=ON')
        with pytest.raises(ValueError, match='事件调度器'):
            storage.export_mysql(source, binary / 'mysqldump', output)
        cursor.execute('SET GLOBAL event_scheduler=OFF')
    expected = storage.export_mysql(source, binary / 'mysqldump', output)
    storage.restore_mysql(target, binary / 'mysql', output)
    actual = storage.mysql_inventory(target)
    actual['database'] = expected['database']
    assert actual == expected
    with storage.mysql_connection(target) as conn, conn.cursor() as cursor:
        cursor.execute('SELECT text,bytes FROM parent WHERE id=1')
        assert cursor.fetchone() == ('中文正文 DEFINER=`x`@`y`', b'\x00\xff')
    with pytest.raises(ValueError, match='空'):
        storage.restore_mysql(target, binary / 'mysql', output)


def test_qdrant_real_snapshot_restores_vectors_payload_and_alias(tmp_path):
    port = os.environ.get('LOCAL_DEPLOY_TEST_QDRANT_PORT')
    target_port = os.environ.get('LOCAL_DEPLOY_TEST_QDRANT_TARGET_PORT')
    if not port or not target_port:
        pytest.skip('需要两个显式隔离 Qdrant 实例')
    storage = module('storage')
    source = {'QDRANT_HOST': '127.0.0.1', 'QDRANT_PORT': port}
    target = {**source, 'QDRANT_PORT': target_port}
    with storage.qdrant_client(source) as client:
        assert not storage.qdrant_inventory(client)['collections']
        storage.qrequest(client, 'PUT', '/collections/papers', json={'vectors': {'size': 2, 'distance': 'Cosine'}})
        storage.qrequest(client, 'PUT', '/collections/papers/points?wait=true', json={'points': [{'id': 1, 'vector': [1.0, 0.0], 'payload': {'quote': '保留证据'}}]})
        storage.qrequest(client, 'POST', '/collections/aliases', json={'actions': [{'create_alias': {'collection_name': 'papers', 'alias_name': 'published'}}]})
    expected = storage.export_qdrant(source, tmp_path / 'qdrant')
    storage.restore_qdrant(target, tmp_path / 'qdrant', expected)
    with storage.qdrant_client(target) as client:
        point = storage.qrequest(client, 'GET', '/collections/published/points/1')
        assert point['payload'] == {'quote': '保留证据'}
        assert point['vector'] == [1.0, 0.0]


def test_corrupt_configuration_has_no_shell_side_effects_in_real_loader(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    import shutil
    shutil.copy2(ROOT / 'scripts/lib-local.sh', scripts / 'lib-local.sh')
    shutil.copytree(ROOT / 'scripts/local_deploy', scripts / 'local_deploy', ignore=shutil.ignore_patterns('__pycache__'))
    local = tmp_path / '.local'
    local.mkdir()
    (local / 'deployment-environment.json').write_text(json.dumps({'prefix': str(Path(sys.executable).parent.parent)}))
    (tmp_path / '.env').write_text("SAFE='spaces $literal'\n")
    script = 'source "$1"; load_env; [[ "$SAFE" == \'spaces $literal\' ]]'
    result = subprocess.run(['bash', '-c', script, 'bash', str(scripts / 'lib-local.sh')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    marker = tmp_path / 'executed'
    (tmp_path / '.env').write_text(f'EVIL=$(touch {marker})\n')
    result = subprocess.run(['bash', '-c', script, 'bash', str(scripts / 'lib-local.sh')], capture_output=True, text=True)
    assert result.returncode != 0
    assert not marker.exists()
