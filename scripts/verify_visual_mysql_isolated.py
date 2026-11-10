"""在自建的临时MySQL验证谱并发及图片来源；不连接业务MySQL。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(evidence_dir, mysqld):
    import pymysql

    evidence_dir.mkdir(parents=True, exist_ok=False)
    report = {'status': 'failed', 'business_database_used': False}
    with tempfile.TemporaryDirectory(prefix='scwiki-visual-mysql-') as temporary:
        work = Path(temporary)
        data = work / 'data'
        data.mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        assert port != 3307
        base = [str(mysqld), '--no-defaults', '--basedir=' + str(mysqld.parent.parent), '--datadir=' + str(data)]
        with (evidence_dir / 'initialize.log').open('w') as log:
            subprocess.run([*base, '--initialize-insecure'], stdout=log, stderr=subprocess.STDOUT, check=True)
        # macOS Unix socket长度有限；仍位于本次TemporaryDirectory下。
        server_socket = work / 'mysql.sock'
        with (evidence_dir / 'server.log').open('w') as log:
            process = subprocess.Popen([*base, '--port=' + str(port), '--socket=' + str(server_socket),
                '--bind-address=127.0.0.1', '--mysqlx=0', '--skip-log-bin', '--innodb-buffer-pool-size=64M',
                '--pid-file=' + str(work / 'mysql.pid')], stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('临时MySQL启动失败，查看server.log')
                try:
                    connection = pymysql.connect(host='127.0.0.1', port=port, user='root', autocommit=True)
                    break
                except pymysql.MySQLError:
                    time.sleep(.25)
            else:
                raise RuntimeError('临时MySQL未就绪')
            database = 'issue137_test_' + uuid.uuid4().hex[:12]
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT @@port, @@datadir, @@version')
                    actual_port, actual_data, version = cursor.fetchone()
                    assert actual_port == port and Path(actual_data).resolve() == data.resolve()
                    cursor.execute('CREATE DATABASE ' + database + ' CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            url = f'mysql+pymysql://root@127.0.0.1:{port}/{database}'
            environment = {**os.environ, 'DATABASE_URL': url, 'RAG_DATABASE_URL': url,
                'SCWIKI_SPECTRA_MYSQL_TEST': '1', 'SCWIKI_MYSQL_TEST_DATADIR': str(data),
                'SCWIKI_MANUAL_TEST_DATABASE_URL': url, 'SCWIKI_VISUAL_TEST_DATABASE_URL': url,
                'SC_WIKI_DATA_DIR': str(work / 'runtime'), 'PYTHONDONTWRITEBYTECODE': '1',
                'JWT_SECRET_KEY': 'isolated-visual-source-verification-key-2026'}
            setup = '''from pathlib import Path
from scripts.local_deploy.schema import initialize
initialize(Path.cwd(),__import__('os').environ['DATABASE_URL'])
from backend.database import SessionLocal
from backend import models
with SessionLocal.begin() as db:
    db.add(models.User(id=1,username='isolated-owner',email='owner@isolation.invalid',
        password_hash='test-only',real_name='隔离测试',role='admin',is_approved=True))
'''
            with (evidence_dir / 'schema.log').open('w') as log:
                subprocess.run([sys.executable, '-c', setup], cwd=ROOT, env=environment,
                    stdout=log, stderr=subprocess.STDOUT, check=True)
            tests = ['backend/tests/test_spectra_mysql.py', 'backend/tests/test_spectra_manual.py',
                'backend/tests/test_spectra_recalculate.py', 'backend/tests/test_spectra_revalidation.py',
                'backend/tests/test_visual_source_reuse.py']
            with (evidence_dir / 'pytest.log').open('w') as log:
                result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rs', *tests],
                    cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report.update(status='passed' if result.returncode == 0 else 'failed',
                mysql_version=version, port=port, database=database, data_directory=str(data),
                test_paths=tests, exit_code=result.returncode)
            return result.returncode
        finally:
            # 只停止本脚本创建且仍持有的Popen进程，不按端口或进程名杀其他实例。
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            report['server_stopped'] = process.poll() is not None
            (evidence_dir / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True, help='新证据目录，不覆盖既有运行')
    default = shutil.which('mysqld') or str(Path(sys.executable).parent / 'mysqld')
    parser.add_argument('--mysqld', type=Path, default=Path(default))
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.evidence_dir.resolve(), arguments.mysqld.resolve()))
