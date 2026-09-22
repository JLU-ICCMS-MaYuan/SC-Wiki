"""部署与打包编排。预检不写入，失败绝不报告完整部署。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

from . import bundle, config, environment
from .state import DeploymentState, operation_lock

ROOT = Path(__file__).resolve().parents[2]


def report(root, operation, result, *, persist=True, **details):
    value = {'operation': operation, 'result': result, **details}
    if persist:
        bundle.write_json(root / '.local/deployment-report.json', value)
    print(json.dumps(value, ensure_ascii=False, indent=2))


def source_identity(root):
    paths = ['scripts/local-deploy-versions.json', 'scripts/local-deploy-schema.json', 'docker/requirements.txt',
             'frontend/package-lock.json', 'goserver/go.mod', 'goserver/go.sum']
    paths += [p.relative_to(root).as_posix() for p in sorted((root / 'alembic/versions').glob('*.py'))]
    return hashlib.sha256(''.join(bundle.digest(root / p) for p in paths).encode()).hexdigest()


def reexec(prefix: Path):
    python = prefix / 'bin/python'
    if Path(sys.executable).resolve() != python.resolve():
        os.environ['PYTHONNOUSERSITE'] = '1'
        os.execv(str(python), [str(python), str(ROOT / 'scripts/local-deploy.py'), *sys.argv[1:]])


def prepare_bundle(root, path, *, check_only=False):
    discovered = bundle.discover_archive(root)
    path = path or discovered
    destination = root / '.deployment'
    if destination.is_symlink():
        raise ValueError('已解压数据目录不能是符号链接')
    if not path:
        if destination.exists():
            return root, bundle.verify(root)
        return None, None
    archive = Path(path).expanduser().absolute()
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('数据库压缩包必须是存在的普通文件，不能是符号链接')
    if not archive.name.lower().endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz', '.tbz2', '.tar.xz', '.txz')):
        raise ValueError('不支持的数据库压缩包格式；请使用 make frozen 生成的 tar 迁移包，不支持 ZIP 或裸 SQL 压缩文件')
    # 自动发现与显式压缩包共用临时校验；CHECK_ONLY 不创建目标运行文件。
    with tempfile.TemporaryDirectory(prefix='scwiki-bundle-check-') as temp:
        try:
            unpacked = bundle.extract_archive(archive, Path(temp) / 'unpacked')
        except (tarfile.TarError, EOFError):
            raise ValueError('数据库压缩包损坏或不是受支持的 tar 迁移包') from None
        manifest = bundle.verify(unpacked)
        for name, info in manifest['files'].items():
            if not name.startswith('.deployment/'):
                file = root / name
                if not file.is_file() or bundle.digest(file) != info['sha256']:
                    raise ValueError('当前源码与包不一致，请在包的解压目录执行部署')
        if destination.exists():
            current = bundle.verify(root)
            if current != manifest:
                raise ValueError('压缩包与已解压数据的清单不一致，拒绝覆盖；请使用同一包或新的空部署目录')
        if check_only:
            return None, manifest
        if not destination.exists():
            shutil.copytree(unpacked / '.deployment', destination)
        return root, manifest


def capabilities(values):
    return {
        'AI': '已配置，尚未实际调用验收' if values.get('LLM_API_KEY') or values.get('DEEPSEEK_API_KEY') else '未配置',
        'Embedding': '已配置，尚未实际调用验收' if values.get('EMBEDDING_API_KEY') or values.get('OPENAI_API_KEY') else '未配置',
        'SMTP': '已配置，尚未发送验收邮件' if values.get('SMTP_PASSWORD') else '未配置',
    }


def health(runtime):
    from . import schema, storage
    import httpx
    schema.verify_schema(runtime.root, runtime.values['DATABASE_URL'])
    storage.mysql_inventory(runtime.values['DATABASE_URL'])
    storage.redis_connection(runtime.values).ping()
    storage.neo4j_inventory(runtime.values)
    with storage.qdrant_client(runtime.values) as client:
        storage.qdrant_inventory(client)
    with httpx.Client(trust_env=False, timeout=15) as client:
        for url in ('http://127.0.0.1:8000/health', 'http://127.0.0.1:8080/health',
                    'http://127.0.0.1:5173/', 'http://127.0.0.1:8070/api/isalive',
                    'http://127.0.0.1:5173/api/form-definitions'):
            if not client.get(url).is_success:
                raise ValueError('服务健康检查失败')
    for name in ('worker', 'news-worker', 'news-scheduler'):
        if not runtime.owned_pid(name):
            raise ValueError(f'{name} 未运行')
    from rq import Worker
    if not Worker.all(connection=storage.redis_connection(runtime.values)):
        raise ValueError('RQ Worker 未注册')


def deploy(root: Path, args):
    # 在检查已有目标之前不得复制包或创建配置。
    manifest = None
    selected = None
    try:
        selected = args.bundle or bundle.discover_archive(root)
        _, manifest = prepare_bundle(root, selected, check_only=True)
        if manifest:
            if manifest.get('services') != environment.versions(root):
                raise ValueError('包的服务版本与源码不一致，不支持跨版本恢复')
            state = DeploymentState.inspect(root, manifest['bundle_id'])
            if ('source_identity' in state.record
                    and state.record['source_identity'] != source_identity(root)):
                raise ValueError('源码依赖或迁移发生变化，首版不支持原地升级')
    except (ValueError, OSError, KeyError) as exc:
        # 包选择/校验失败属于预检；普通部署也不能覆盖旧实例的状态和报告。
        report(root, 'deploy', 'blocked', persist=False,
               problems=[str(exc)], conda=None, environment='未检查（包或目标预检未通过）',
               mode='restore' if selected or manifest else 'undetermined',
               bundle=str(selected) if selected else None,
               next_steps=['请检查 dist 唯一迁移包、源码兼容性及目标归属；已有实例不能直接覆盖恢复'],
               error_code='preflight_failed', phase='preflight')
        return 2
    existing = root / '.local/deployment-state.json'
    problems = environment.preflight(root, occupied_ok=existing.is_file())
    if (root / '.data').exists() and any((root / '.data').iterdir()) and not existing.is_file():
        problems.append('目标已有数据，必须使用新的空部署目录')
    if (root / '.env').exists():
        config.validate_local(config.read_config(root), root, target=True)
    conda, prefix = None, None
    environment_status = '未检查（系统或目标预检未通过）'
    if not problems:
        environment_status = '未就绪（Conda 预检未通过）'
        try:
            conda, prefix = environment.find_environment(root)
            if conda is None:
                problems.append('缺少用户准备的 Conda')
            else:
                environment_status = str(prefix) if prefix else '将创建 sc-wiki'
        except ValueError as exc:
            problems.append(f'Conda 环境检查失败：{exc}')
        except (OSError, subprocess.SubprocessError, KeyError, TypeError):
            problems.append('Conda 环境查询失败，请检查 Conda 是否可用')
    if manifest and shutil.disk_usage(root).free < manifest['capacity'] * 2.4 + 8 * 1024**3:
        problems.append('空间不足以同时保存依赖、包和临时恢复数据')
    if args.check_only or problems:
        report(root, 'deploy', 'blocked' if problems else 'check-passed', persist=False,
               problems=problems, conda=str(conda) if conda else None,
               environment=environment_status,
               bundle=str(selected) if selected else None,
               mode='restore' if manifest else 'empty', next_steps=environment.preflight_guidance(problems),
               **({'error_code': 'preflight_failed', 'phase': 'preflight'} if problems else {}))
        return 2 if problems else 0
    with operation_lock(root):
        identity = manifest['bundle_id'] if manifest else source_identity(root)
        state = DeploymentState.open(root, identity)
        if state.record.get('source_identity', source_identity(root)) != source_identity(root):
            raise ValueError('源码依赖或迁移发生变化，首版不支持原地升级')
        state.save(source_identity=source_identity(root))
        env_record = root / '.local/deployment-environment.json'
        if env_record.exists():
            prefix = environment.runtime_prefix(root)
            if json.loads(env_record.read_text())['versions_digest'] != bundle.digest(root / 'scripts/local-deploy-versions.json'):
                raise ValueError('依赖版本清单发生变化，拒绝隐式升级')
        else:
            state.save('environment')
            prefix = environment.install(root)
        state.save('environment' if not state.promoted else state.record['phase'])
    # 数据库客户端只在已经准备好的 sc-wiki 解释器下导入。
    reexec(prefix)
    from . import schema, storage
    from .runtime import Runtime
    with operation_lock(root):
        state = DeploymentState.open(root, identity)
        _, manifest = prepare_bundle(root, selected)
        if manifest and manifest['bundle_id'] != identity:
            raise ValueError('预检后迁移包发生变化，请重新执行部署')
        database = manifest['components']['mysql']['database'] if manifest else 'scwiki'
        values = config.ensure_config(root, database)
        config.validate_local(values, root, target=True)
        if values['MYSQL_DATABASE'] != database:
            raise ValueError('本机配置数据库名与迁移包不一致')
        runtime = Runtime(root, prefix, values, root / '.data' if state.promoted else state.staging)
        runtime.check_ports()
        try:
            if args.setup_only:
                state.save('configured')
                report(root, 'setup', '依赖与配置已就绪', next_step='make deploy')
                return 0
            if not state.promoted:
                state.save('configured')
                if state.staging.exists():
                    marker = state.staging / '.restore-owner.json'
                    if not marker.is_file() or json.loads(marker.read_text()) != {'operation_id': state.record['operation_id']}:
                        raise ValueError('临时目录归属不明，拒绝清理')
                    for service in ('mysql', 'redis', 'neo4j', 'qdrant'):
                        runtime.stop_gracefully(service)
                    shutil.rmtree(state.staging)
                state.staging.mkdir(parents=True)
                bundle.write_json(state.staging / '.restore-owner.json', {'operation_id': state.record['operation_id']})
                runtime.prepare()
                runtime.initialize_mysql()
                state.save('restoring' if manifest else 'initializing')
                if manifest:
                    payload = root / '.deployment'
                    expected = manifest['components']
                    storage.restore_mysql(values['DATABASE_URL'], prefix / 'bin/mysql', payload / 'mysql/business.sql')
                    if storage.mysql_inventory(values['DATABASE_URL']) != expected['mysql']:
                        raise ValueError('MySQL 恢复结构或数量不一致')
                    schema.verify_schema(root, values['DATABASE_URL'])
                    shutil.copytree(payload / 'files', state.staging, dirs_exist_ok=True)
                    source = Path(manifest['source_data_root'])
                    from .paths import FILE_DIRS
                    for mapping in json.loads((payload / 'paths.json').read_text()):
                        relative = bundle.safe_relative(mapping['relative_path'])
                        if relative.parts[0] not in FILE_DIRS or not (state.staging / relative).is_file():
                            raise ValueError('恢复文件与登记的路径映射不一致')
                    storage.relocate_mysql(values['DATABASE_URL'], source, root / '.data')
                    storage.relocate_files(state.staging, source, root / '.data')
                    runtime.neo_admin(['database', 'load', 'neo4j', f'--from-path={payload / "neo4j"}'])
                else:
                    schema.initialize(root, values['DATABASE_URL'])
                runtime.dev('start', 'redis', 'neo4j', 'qdrant')
                if manifest:
                    storage.restore_qdrant(values, payload / 'qdrant', expected['qdrant'])
                    if storage.neo4j_inventory(values) != expected['neo4j']:
                        raise ValueError('Neo4j 恢复数据或结构不一致')
                    with storage.mysql_connection(values['DATABASE_URL']) as connection, connection.cursor() as cursor:
                        cursor.execute('SELECT id FROM users')
                        users = {row[0] for row in cursor.fetchall()}
                    restored = storage.restore_redis(storage.redis_connection(values),
                                                    json.loads((payload / 'redis/upload-drafts.json').read_text()),
                                                    users, source, root / '.data')
                else:
                    restored = {'restored': 0, 'expired': 0}
                state.save('verified', draft_counts=restored)
                runtime.dev('stop', 'qdrant', 'neo4j', 'redis', 'mysql')
                (state.staging / '.restore-owner.json').unlink()
                state.promote()
                runtime = Runtime(root, prefix, values)
            runtime.prepare()
            runtime.dev('start')
            state.save('started')
            health(runtime)
            state.save('complete', failed_stage=None)
            report(root, 'deploy', '基础部署成功', address='http://127.0.0.1:5173',
                   identity=identity, external=capabilities(values),
                   draft_counts=state.record.get('draft_counts'),
                   administrator='保留原账号' if manifest else
                   '''bash -c 'source scripts/lib-local.sh; load_env; "$PY_BIN/python" -m backend.scripts.create_superadmin' ''')
            return 0
        except BaseException:
            state.save(failed_stage=state.record['phase'])
            for service in ('news-scheduler', 'frontend', 'goserver', 'worker', 'news-worker', 'python', 'qdrant', 'neo4j', 'redis', 'mysql'):
                try:
                    runtime.stop_gracefully(service)
                except (ValueError, OSError):
                    pass
            raise


def check_secrets(root: Path, values: dict):
    needles = [v.encode() for k, v in values.items() if len(v) >= 8 and any(t in k for t in ('PASSWORD', 'SECRET', 'API_KEY'))]
    if not needles:
        return
    overlap = max(map(len, needles))
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        previous = b''
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                block = previous + chunk
                if any(value in block for value in needles):
                    raise ValueError('打包内容发现源配置凭据，拒绝发布')
                previous = block[-overlap:]


def pack(root: Path, args):
    from . import schema, storage
    from .runtime import Runtime
    if environment.run(['git', 'status', '--porcelain'], cwd=root, capture=True).strip():
        raise ValueError('源码有未提交改动；请完成提交后再执行 make frozen')
    commit = environment.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture=True).strip()
    values = config.read_config(root)
    config.validate_local(values, root)
    prefix = environment.runtime_prefix(root)
    reexec(prefix)
    schema.verify_schema(root, values['DATABASE_URL'])
    runtime = Runtime(root, prefix, values, Path(values['SC_WIKI_DATA_DIR']).resolve())
    # 打包不启停或导出 GROBID；旧实例的解析容器名称不影响业务数据快照。
    runtime.check_ports(check_grobid=False)
    if any(runtime.owned_pid(name) is None for name in ('mysql', 'redis', 'neo4j', 'qdrant')):
        raise ValueError('打包需要确认四个基础服务均由当前项目运行')
    storage.check_mysql_export(values['DATABASE_URL'], inspection_connection=runtime.mysql_inspection_connection)
    storage.check_file_layout(Path(values['SC_WIKI_DATA_DIR']).resolve())
    destination = Path(args.output).expanduser().resolve() if args.output else root / 'dist' / f'sc-wiki-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{commit[:8]}.tar.gz'
    if destination.exists():
        raise ValueError('输出已存在，拒绝覆盖')
    with operation_lock(root), tempfile.TemporaryDirectory(prefix='pack-', dir=root / '.local') as tmp:
        temporary = Path(tmp)
        archive = temporary / 'source.tar'
        environment.run(['git', 'archive', '--format=tar', '--prefix=sc-wiki/', '-o', archive, commit], cwd=root)
        stage = bundle.extract_archive(archive, temporary / 'source')
        payload = stage / '.deployment'
        payload.mkdir()
        components = {}
        with runtime.quiesce():
            source = Path(values['SC_WIKI_DATA_DIR']).resolve()
            mappings = storage.relocate_mysql(values['DATABASE_URL'], source, source, check_files=True)
            mappings += storage.relocate_files(source, source, source, check_files=True)
            components['mysql'] = storage.export_mysql(values['DATABASE_URL'], prefix / 'bin/mysqldump', payload / 'mysql/business.sql',
                                                      inspection_connection=runtime.mysql_inspection_connection)
            components['redis'] = storage.export_redis(storage.redis_connection(values))
            # 校验草稿引用，不更改源数据。
            from .paths import relocate, references
            relocate(components['redis'], source, source, check_files=True)
            mappings += [{'store': 'redis', 'record_id': 'upload-drafts', **item}
                         for item in references(components['redis'], source)]
            bundle.write_json(payload / 'paths.json', mappings)
            bundle.write_json(payload / 'redis/upload-drafts.json', components['redis'])
            components['redis'] = {'tasks': len(components['redis']['tasks'])}
            components['neo4j'] = storage.neo4j_inventory(values)
            (payload / 'neo4j').mkdir()
            if not runtime.owned_pid('neo4j'):
                raise ValueError('无法确认 Neo4j 属于本项目，不执行停库')
            runtime.stop_gracefully('neo4j')
            try:
                runtime.neo_admin(['database', 'dump', 'neo4j', f'--to-path={payload / "neo4j"}'])
            finally:
                runtime.dev('start', 'neo4j')
            components['qdrant'] = storage.export_qdrant(values, payload / 'qdrant')
            storage.copy_files(source, payload / 'files')
            check_secrets(stage, values)
            manifest = bundle.seal(stage, {'source_commit': commit, 'source_data_root': str(source),
                                          'services': environment.versions(root), 'components': components})
            bundle.verify(stage)
            storage.check_mysql_export(values['DATABASE_URL'], inspection_connection=runtime.mysql_inspection_connection)
            bundle.publish(stage, destination)
        report(root, 'pack', '打包成功，源服务已恢复', path=str(destination), bundle_id=manifest['bundle_id'], source_commit=commit)
    return 0


def main():
    parser = argparse.ArgumentParser(description='SC-Wiki 本地部署与打包')
    parser.add_argument('operation', choices=('deploy', 'pack'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check-only', action='store_true', default=os.environ.get('CHECK_ONLY') == '1')
    parser.add_argument('--setup-only', action='store_true')
    parser.add_argument('--bundle', default=os.environ.get('BUNDLE') or None)
    parser.add_argument('--output', default=os.environ.get('OUTPUT') or None)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.operation == 'pack':
            # 打包也先切换环境，再导入 SQL/Redis 客户端。
            reexec(environment.runtime_prefix(root))
            return pack(root, args)
        return deploy(root, args)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as exc:
        print(f'✗ {exc}', file=sys.stderr)
        failure_report(root, args, exc)
        return 2 if args.check_only else 5
    except Exception as exc:
        # 第三方数据库异常可能包含凭据或 SQL 业务内容，不直接输出。
        print(f'✗ 操作失败（{type(exc).__name__}），未报告部署成功', file=sys.stderr)
        failure_report(root, args, exc)
        return 5


def failure_report(root, args, exc):
    # 不持久化第三方异常文本，避免把连接串、SQL 或配置带入报告。
    state = {}
    try:
        path = root / '.local/deployment-state.json'
        if path.is_file():
            state = json.loads(path.read_text())
        report(root, args.operation, 'failed', persist=not args.check_only and (root / '.local').is_dir(),
               error_code='preflight_failed' if args.check_only else 'operation_failed',
               exception_type=type(exc).__name__, phase=state.get('phase'), identity=state.get('identity'))
    except (ValueError, OSError):
        pass


if __name__ == '__main__':
    raise SystemExit(main())
