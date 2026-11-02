"""#203/#204本机迁移：先私有备份并恢复到隔离库，再验证新版迁移。"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()



PROTECTED = ('paper_history_events', 'paper_files', 'paper_chunks', 'property_records',
             'spectrum_collections', 'spectrum_curves', 'spectrum_runs')


def implementation_fingerprint():
    paths = [
        'backend/data/scientific_form_contract.v1.json', 'backend/data/scientific_form_contract.lock.json',
        'backend/ingest/fixed_form_contract.py', 'backend/ingest/canonical_structure.py',
        'backend/services/form_contract_migration.py', 'scripts/migrate_fixed_form_contract.py',
        'alembic/versions/20261102_0203_merge_contract_heads.py',
        'alembic/versions/20261102_0203_fixed_form_contract.py',
        'alembic/versions/20261102_0204_canonical_structure.py',
    ]
    values = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    resolution = os.environ.get('SCWIKI_FORM_CONTRACT_RESOLUTIONS')
    values['resolutions'] = hashlib.sha256(Path(resolution).read_bytes()).hexdigest() if resolution else None
    return values


def assert_preserved(before, after):
    for table in PROTECTED:
        if table in before and before[table] != after.get(table):
            raise RuntimeError('迁移改变了受保护的科学值或历史：' + table)
    for table in ('material_states', 'structure_models', 'scientific_work_drafts'):
        if before.get(table, {}).get('count') != after.get(table, {}).get('count'):
            raise RuntimeError('迁移前后记录数量不一致：' + table)
    if before.get('material_state_values') != after.get('material_state_values'):
        raise RuntimeError('材料状态身份或科学值发生变化')
    if before.get('structure_values') != after.get('structure_values'):
        raise RuntimeError('原始结构内容发生变化')
    unrelated_heads = set(before['heads']) - {'20261020_0049', '20261101_0198'}
    if not unrelated_heads.issubset(after['heads']) or '20261102_0204' not in after['heads']:
        raise RuntimeError('迁移头不符合目标，或覆盖了其他任务的迁移头')


def verify_contract(url):
    from sqlalchemy import create_engine, inspect, text
    from backend.ingest.fixed_form_contract import RETIRED_PRESSURE, validate_conditions
    from backend.ingest.tc_contexts import map_draft
    with create_engine(url).connect() as connection:
        columns = {c['name'] for c in inspect(connection).get_columns('material_states')}
        if set(RETIRED_PRESSURE) & columns:
            raise RuntimeError('退役压力列未全部删除')
        count = 0
        for raw in connection.execute(text('SELECT body FROM scientific_work_drafts')).scalars():
            draft = json.loads(raw) if isinstance(raw, str) else raw
            draft = map_draft(draft)
            if 'structure_candidates' in draft or 'structural_observations' in draft:
                raise RuntimeError('当前工作稿仍含旧结构容器')
            for state in draft.get('material_states') or []:
                if set(RETIRED_PRESSURE) & set(state):
                    raise RuntimeError('工作稿仍含退役压力键')
                for module in state.get('property_modules') or []:
                    for record in module.get('records') or []:
                        if record.get('property_code') == 'band_gap' or record.get('record_type') == 'measured_tc':
                            continue
                        validate_conditions((record.get('payload') or {}).get('calculation_conditions') or {})
                        count += 1
        records = connection.execute(text(
            "SELECT r.payload_json,r.definition_version FROM property_records r JOIN papers p "
            "ON p.id=r.paper_id AND p.content_revision=r.paper_revision "
            "WHERE r.property_code<>'band_gap' AND r.record_type<>'measured_tc'")).all()
        for raw, version in records:
            payload = json.loads(raw) if isinstance(raw, str) else raw
            validate_conditions((payload or {}).get('calculation_conditions') or {})
            if version < 2:
                raise RuntimeError('当前正式记录未采用新定义')
        return {'draft_records_checked': count, 'formal_records_checked': len(records),
                'retired_columns_absent': True, 'canonical_structures_only': True}

def inventory(url):
    from sqlalchemy import create_engine, inspect, text
    result = {}
    with create_engine(url).connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text('START TRANSACTION'))
        tables = set(inspect(connection).get_table_names())
        for name in ('paper_history_events', 'paper_files', 'paper_chunks', 'property_records', 'material_states',
                     'structure_models', 'scientific_work_drafts', 'spectrum_collections', 'spectrum_curves', 'spectrum_runs'):
            if name not in tables:
                continue
            rows = [dict(row) for row in connection.execute(text('SELECT * FROM ' + name)).mappings()]
            rows.sort(key=lambda row: str(row.get('id', row.get('task_id', ''))))
            if name == 'material_states':
                result['material_state_values'] = fingerprint([{k: v for k, v in row.items()
                    if k not in {'pressure_min_gpa', 'pressure_max_gpa', 'pressure_raw', 'pressure_unit_raw'}} for row in rows])
            if name == 'structure_models':
                result['structure_values'] = fingerprint([{k: v for k, v in row.items() if k != 'metadata_json'} for row in rows])
            if name == 'property_records':
                rows = [{key: row.get(key) for key in ('id', 'record_key', 'property_code', 'value_kind', 'value_number',
                    'value_min', 'value_max', 'value_text', 'value_boolean', 'method_code', 'unit_raw', 'canonical_unit')} for row in rows]
            result[name] = {'count': len(rows), 'sha256': fingerprint(rows)}
        result['heads'] = sorted(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
        connection.rollback()
    return result


def upgrade(url, log):
    environment = {**os.environ, 'DATABASE_URL': url, 'RAG_DATABASE_URL': url.replace('mysql+pymysql:', 'mysql+asyncmy:'), 'SCWIKI_APPROVED_CONTRACT_MIGRATION': '203,204'}
    with log.open('w') as output:
        completed = subprocess.run([sys.executable, '-m', 'alembic', '-c', str(ROOT / 'alembic.ini'), 'upgrade', '20261102_0204'],
            cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError('迁移失败；详情保存在私有迁移日志，原库未用于隔离验证')


def exact_json_backup(url, path):
    """MySQL的JSON文本重解析可能改变一个ULP，另存受影响原始文档。"""
    from sqlalchemy import create_engine, inspect, text
    documents = []
    quote = lambda name: chr(96) + name.replace(chr(96), chr(96) * 2) + chr(96)
    with create_engine(url).connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text('START TRANSACTION'))
        inspector = inspect(connection)
        for table in inspector.get_table_names():
            keys = inspector.get_pk_constraint(table).get('constrained_columns') or []
            for column in inspector.get_columns(table):
                if str(column['type']).upper() != 'JSON' or not keys:
                    continue
                name = quote(column['name'])
                sql = ('SELECT ' + ','.join(quote(key) for key in keys) + ',CAST(' + name + ' AS CHAR) AS original_json FROM '
                       + quote(table) + ' WHERE NOT (' + name + ' <=> CAST(CAST(' + name + ' AS CHAR) AS JSON))')
                for row in connection.execute(text(sql)).mappings():
                    documents.append({'table': table, 'column': column['name'],
                                      'keys': {key: row[key] for key in keys}, 'json': row['original_json']})
        connection.rollback()
    path.write_text(json.dumps(documents, ensure_ascii=False, default=str))
    os.chmod(path, 0o600)
    return len(documents)


def restore_exact_json(url, path):
    """用DOUBLE类型值恢复JSON数字，避开JSON文本解析的末位漂移。"""
    from sqlalchemy import create_engine, text
    quote = lambda name: chr(96) + name.replace(chr(96), chr(96) * 2) + chr(96)
    corrections = 0
    with create_engine(url).begin() as connection:
        for document in json.loads(path.read_text()):
            identity = ' AND '.join(quote(key) + '=:key' + str(i) for i, key in enumerate(document['keys']))
            parameters = {'key' + str(i): value for i, value in enumerate(document['keys'].values())}
            table, column = quote(document['table']), quote(document['column'])
            raw = connection.execute(text('SELECT ' + column + ' FROM ' + table + ' WHERE ' + identity), parameters).scalar_one()
            original, actual = json.loads(document['json']), json.loads(raw) if isinstance(raw, str) else raw
            changes = []
            def walk(expected, current, location='$'):
                if isinstance(expected, dict) and isinstance(current, dict) and expected.keys() == current.keys():
                    for key in expected:
                        walk(expected[key], current[key], location + '.' + json.dumps(key, ensure_ascii=False))
                elif isinstance(expected, list) and isinstance(current, list) and len(expected) == len(current):
                    for i, (a, b) in enumerate(zip(expected, current)):
                        walk(a, b, location + '[' + str(i) + ']')
                elif expected != current:
                    if isinstance(expected, (float, int)) and not isinstance(expected, bool) and isinstance(current, (float, int)):
                        changes.append((location, expected))
                    else:
                        raise RuntimeError('JSON恢复存在非数值差异：' + document['table'] + '.' + document['column'])
            walk(original, actual)
            for location, value in changes:
                sql = 'UPDATE ' + table + ' SET ' + column + '=JSON_SET(' + column + ',:location,CAST(:value AS DOUBLE)) WHERE ' + identity
                connection.execute(text(sql), {**parameters, 'location': location, 'value': repr(value)})
                corrections += 1
            reread = connection.execute(text('SELECT ' + column + ' FROM ' + table + ' WHERE ' + identity), parameters).scalar_one()
            if json.loads(reread) != original:
                raise RuntimeError('JSON精确恢复未通过校验')
    return corrections


def main():
    from scripts.local_deploy.config import read_config
    from scripts.local_deploy.storage import export_mysql, restore_mysql, mysql_connection
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from redis import Redis
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--apply-local', action='store_true')
    parser.add_argument('--preflight-report')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out, 0o700)
    values = read_config(ROOT)
    source_url = values['DATABASE_URL']
    parsed = make_url(source_url)
    if parsed.host != '127.0.0.1' or parsed.port != 3307 or parsed.database != 'scwiki':
        raise RuntimeError('本工具只允许明确授权的127.0.0.1:3307/scwiki')
    os.environ['DATABASE_URL'] = source_url
    source_fingerprint = implementation_fingerprint()
    if args.apply_local:
        if not args.preflight_report:
            raise RuntimeError('先完成隔离恢复和迁移演练')
        preflight = json.loads(Path(args.preflight_report).read_text())
        if not preflight.get('passed') or preflight.get('implementation') != source_fingerprint:
            raise RuntimeError('隔离报告未通过或代码/冲突依据已变化，必须重新演练')
    before = inventory(source_url)
    dump = out / 'business.sql'
    prefix = Path(sys.executable).resolve().parent
    # 凭据仅由现有私有defaults文件传给客户端，不放进命令行或报告。
    def inspection():
        import pymysql
        return pymysql.connect(read_default_file=str(ROOT / '.local/my.cnf'), user='root',
                               connect_timeout=10, read_timeout=30, autocommit=True)
    export_mysql(source_url, prefix / 'mysqldump', dump, inspection_connection=inspection)
    os.chmod(dump, 0o600)
    exact_path = out / 'exact-json.json'
    exact_count = exact_json_backup(source_url, exact_path)
    cache = Redis.from_url(values['REDIS_URL'])
    redis_backup = []
    for key in sorted(cache.scan_iter('upload:*')):
        name = key.decode()
        if not name.endswith((':state', ':draft')):
            continue
        data = cache.get(key)
        if data is not None:
            redis_backup.append({'key': name, 'value': data.decode(), 'ttl_ms': cache.pttl(key)})
    backup_path = out / 'upload-cache.json'
    backup_path.write_text(json.dumps(redis_backup, ensure_ascii=False))
    os.chmod(backup_path, 0o600)
    if args.apply_local:
        if not args.preflight_report or not json.loads(Path(args.preflight_report).read_text()).get('passed'):
            raise RuntimeError('先完成隔离恢复和迁移演练')
        upgrade(source_url, out / 'migration.log')
        with create_engine(source_url).connect() as connection:
            rows = connection.execute(text("SELECT target_id,body FROM scientific_work_drafts WHERE target='upload'")).all()
            with cache.pipeline(transaction=True) as transaction:
                for task_id, body in rows:
                    name = 'upload:' + task_id + ':draft'
                    if cache.exists(name):
                        ttl = cache.pttl(name)
                        value = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                        transaction.set(name, value, px=ttl if ttl > 0 else None)
                transaction.execute()
        after = inventory(source_url)
        assert_preserved(before, after)
        checks = verify_contract(source_url)
        report = {'target': '127.0.0.1:3307/scwiki', 'before': before, 'after': after,
                  'backup_sha256': hashlib.sha256(dump.read_bytes()).hexdigest(), 'passed': '20261102_0204' in after['heads']}
    else:
        suffix = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
        database = 'scwiki_contract_203_204_' + suffix
        clone_url = parsed.set(database=database, username='root', password=values['MYSQL_ROOT_PASSWORD']).render_as_string(hide_password=False)
        with inspection() as connection, connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            connection.commit()
        restore_mysql(clone_url, prefix / 'mysql', dump)
        corrected = restore_exact_json(clone_url, exact_path)
        restored = inventory(clone_url)
        if before != restored:
            raise RuntimeError('隔离恢复后的数据与备份前不一致')
        upgrade(clone_url, out / 'migration.log')
        after = inventory(clone_url)
        assert_preserved(before, after)
        checks = verify_contract(clone_url)
        report = {'target': '127.0.0.1:3307/scwiki', 'isolated_database': database,
                  'before': before, 'restored': restored, 'after': after,
                  'backup_sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
                  'exact_json_documents': exact_count, 'exact_json_numbers_restored': corrected,
                  'passed': '20261102_0204' in after['heads'], 'business_database_unchanged': inventory(source_url) == before}
    report['implementation'] = source_fingerprint
    report['contract_checks'] = checks
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': report['passed'], 'report': str(out / 'report.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
