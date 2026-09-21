#!/usr/bin/env python3
"""用已安装依赖验证真实 CLI 搬迁；动态端口、人工数据，不接触开发实例。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.local_deploy import bundle, config, storage
from scripts.local_deploy.runtime import APPS, Runtime


def run(args, root, env):
    subprocess.run([str(x) for x in args], cwd=root, env=env, check=True, timeout=1200)


def dependencies(root, tools, prefix):
    for name in ('go', 'bin', 'neo4j'):
        shutil.copytree(tools / '.local' / name, root / '.local' / name,
                        ignore=shutil.ignore_patterns('data', 'logs', 'run'))
    shutil.copytree(tools / 'frontend/node_modules', root / 'frontend/node_modules', symlinks=True)
    bundle.write_json(root / '.local/deployment-environment.json', {
        'prefix': str(prefix), 'versions_digest': bundle.digest(root / 'scripts/local-deploy-versions.json')})


def seed(root):
    values = config.read_config(root)
    os.environ['DATABASE_URL'] = values['DATABASE_URL']
    import bcrypt
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.models import User, Paper, PaperFile
    from neo4j import GraphDatabase
    file = root / '.data/upload_PDFs/roundtrip.pdf'
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b'%PDF-1.4\nPortable test fixture\n%%EOF')
    engine = create_engine(values['DATABASE_URL'])
    with Session(engine) as session:
        user = User(email='portable@example.test', username='portable', real_name='迁移测试',
                    password_hash=bcrypt.hashpw(b'portable-test-only', bcrypt.gensalt()).decode(),
                    role='superadmin', is_approved=True, is_email_verified=True)
        session.add(user)
        session.flush()
        paper = Paper(title='迁移验证论文', year=2026, review_status='approved',
                      content_revision=1, approved_revision=1, uploaded_by_user_id=user.id)
        session.add(paper)
        session.flush()
        session.add(PaperFile(paper_id=paper.id, paper_revision=1, role='main', original_filename='roundtrip.pdf',
                             stored_path=str(file), sha256=bundle.digest(file), size=file.stat().st_size, sort_order=0))
        user_id, paper_id = user.id, paper.id
        session.commit()
    engine.dispose()
    client = storage.redis_connection(values)
    task = 'd' * 32
    state = {'state_schema_version': 1, 'user_id': user_id, 'task_id': task, 'status': 'ready',
             'updated_at': time.time(), 'cleanup_at': time.time() + 86400, 'file_path': str(file)}
    client.set(f'upload:{task}:state', json.dumps(state), ex=86400)
    client.set(f'upload:{task}:draft', json.dumps({'title': '保留草稿', 'file_path': str(file)}), ex=86400)
    client.set(f'upload:llm:{task}', 'test-secret-must-not-export', ex=86400)
    with GraphDatabase.driver(values['NEO4J_URI'], auth=('neo4j', values['NEO4J_PASSWORD'])) as driver:
        with driver.session() as session:
            session.run('CREATE CONSTRAINT portable_id IF NOT EXISTS FOR (n:Portable) REQUIRE n.id IS UNIQUE').consume()
            session.run('CREATE (:Portable {id:1})-[:RELATES]->(:Portable {id:2})').consume()
    with storage.qdrant_client(values) as client:
        storage.qrequest(client, 'PUT', '/collections/portable', json={'vectors': {'size': 2, 'distance': 'Cosine'}})
        storage.qrequest(client, 'PUT', '/collections/portable/points?wait=true',
                         json={'points': [{'id': 1, 'vector': [1, 0], 'payload': {'title': '迁移向量'}}]})
        storage.qrequest(client, 'POST', '/collections/aliases',
                         json={'actions': [{'create_alias': {'collection_name': 'portable', 'alias_name': 'portable_alias'}}]})
    return paper_id


def verify(root, port, paper_id, source_values):
    import httpx
    values = config.read_config(root)
    with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as client:
        response = client.post('/api/auth/login', json={'email': 'portable@example.test', 'password': 'portable-test-only'})
        response.raise_for_status()
        data = response.json()
        client.headers['Authorization'] = 'Bearer ' + (data.get('token') or data['access_token'])
        for path in ('/api/form-definitions', f'/api/papers/{paper_id}', '/api/account/profile'):
            client.get(path).raise_for_status()
    with storage.mysql_connection(values['DATABASE_URL']) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT stored_path,sha256 FROM paper_files WHERE paper_id=%s', (paper_id,))
        path, expected = cursor.fetchone()
        assert Path(path).is_relative_to(root / '.data') and bundle.digest(Path(path)) == expected
    client = storage.redis_connection(values)
    task = 'd' * 32
    for suffix in ('state', 'draft'):
        assert json.loads(client.get(f'upload:{task}:{suffix}'))['file_path'] == path
        assert 0 < client.ttl(f'upload:{task}:{suffix}') <= 86400
    assert client.get(f'upload:llm:{task}') is None
    graph = storage.neo4j_inventory(values)
    assert (graph['nodes'], graph['relationships']) == (2, 1)
    with storage.qdrant_client(values) as client:
        point = storage.qrequest(client, 'GET', '/collections/portable_alias/points/1')
        assert point['vector'] == [1, 0] and point['payload'] == {'title': '迁移向量'}
    for key in ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'NEO4J_PASSWORD', 'JWT_SECRET_KEY'):
        assert values[key] != source_values[key]


def stop(root, prefix):
    if not (root / '.env').exists():
        return
    runtime = Runtime(root, prefix, config.read_config(root))
    for name in (*APPS, 'qdrant', 'neo4j', 'redis', 'mysql'):
        runtime.stop_gracefully(name)
    name = 'scwiki-grobid-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-from', type=Path, required=True, help='含 .local 工具及 frontend/node_modules 的已准备目录')
    parser.add_argument('--workspace', type=Path, required=True, help='必须不存在的测试目录，保留日志供检查')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    prefix = Path(sys.executable).resolve().parent.parent
    source, target = workspace / 'source', workspace / 'target/sc-wiki'
    source.mkdir()
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths += [str(p.relative_to(ROOT)) for p in (ROOT / 'scripts/local_deploy').glob('*.py')]
    paths += ['scripts/local-deploy.py', 'scripts/local-deploy-versions.json', 'scripts/local-deploy-schema.json',
              'scripts/locallydeploy.sh', 'scripts/pack.sh']
    paths = sorted({p for p in paths if p and (ROOT / p).is_file()})
    sockets = [socket.socket() for _ in range(10)]
    for sock in sockets:
        sock.bind(('127.0.0.1', 0))
    ports = dict(zip((3307, 6379, 17687, 7474, 6333, 6334, 8000, 8080, 5173, 8070),
                     (sock.getsockname()[1] for sock in sockets)))
    for sock in sockets:
        sock.close()
    for name in paths:
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
        if name in ('scripts/lib-local.sh', 'frontend/vite.config.ts') or name.startswith('scripts/local_deploy/'):
            text = destination.read_text()
            import re
            text = re.sub(r'\b(?:' + '|'.join(map(str, ports)) + r')\b', lambda m: str(ports[int(m[0])]), text)
            destination.write_text(text)
    env = {**os.environ, 'PYTHONNOUSERSITE': '1', 'DEBUG': 'false'}
    try:
        dependencies(source, args.tools_from.resolve(), prefix)
        run(['git', 'init', '-q'], source, env)
        subprocess.run(['git', 'add', '-f', '--pathspec-from-file=-', '--pathspec-file-nul'], cwd=source,
                       input='\0'.join(paths).encode(), check=True)
        run(['git', '-c', 'user.name=Portable fixture', '-c', 'user.email=fixture@example.test',
             'commit', '-qm', 'Isolated deployment fixture'], source, env)
        run(['make', 'locallydeploy'], source, env)
        paper_id = seed(source)
        values = config.read_config(source)
        # 新闻进程的首次运行可能尚在收尾；只等待自然结束，绝不清队列。
        for attempt in range(120):
            try:
                storage.assert_no_jobs(storage.redis_connection(values))
                break
            except ValueError:
                time.sleep(1)
        archive = workspace / 'portable.tar.gz'
        run(['make', 'pack', f'OUTPUT={archive}'], source, env)
        stop(source, prefix)
        bundle.extract_archive(archive, workspace / 'target')
        dependencies(target, args.tools_from.resolve(), prefix)
        run(['make', 'locallydeploy'], target, env)
        verify(target, ports[5173], paper_id, values)
        original_config = (target / '.env').read_bytes()
        run(['make', 'locallydeploy'], target, env)
        assert (target / '.env').read_bytes() == original_config
        run(['bash', 'scripts/dev.sh', 'stop'], target, env)
        run(['make', 'locallydeploy'], target, env)
        verify(target, ports[5173], paper_id, values)
        print('PASS: 真实 CLI 打包、异目录恢复、账号/表单/附件/草稿/图/向量、重跑及停止后重启')
    finally:
        for root in (target, source):
            stop(root, prefix)


if __name__ == '__main__':
    main()
