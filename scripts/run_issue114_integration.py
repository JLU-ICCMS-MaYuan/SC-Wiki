"""启动隔离 MySQL 运行 #114 工作流验收；不读取或连接现有业务数据库。"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pymysql


def main():
    binary = shutil.which("mysqld") or str(Path(sys.executable).parent / "mysqld")
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="issue114-workflow-") as directory:
        temporary = Path(directory)
        socket = temporary / "mysql.sock"
        data = temporary / "data"
        with (temporary / "mysql.log").open("w+") as log:
            initialized = subprocess.run([binary, "--no-defaults", "--initialize-insecure", f"--datadir={data}"], stdout=log, stderr=log)
            if initialized.returncode:
                log.seek(0)
                raise RuntimeError("隔离 MySQL 初始化失败：" + log.read()[-3000:])
            process = subprocess.Popen([binary, "--no-defaults", f"--datadir={data}", f"--socket={socket}",
                f"--pid-file={temporary / 'mysql.pid'}", "--skip-networking", "--mysqlx=0"], stdout=log, stderr=log)
            try:
                connection = None
                for _ in range(200):
                    try:
                        connection = pymysql.connect(user="root", unix_socket=str(socket))
                        break
                    except pymysql.Error:
                        time.sleep(.1)
                if connection is None:
                    raise RuntimeError("隔离 MySQL 未能启动")
                with connection.cursor() as cursor:
                    cursor.execute("CREATE DATABASE test_issue114_workflow")
                connection.close()
                env = os.environ.copy()
                env.pop("DEBUG", None)
                env.update(DATABASE_URL="sqlite:///:memory:", JWT_SECRET_KEY="issue114-test-only",
                    ISSUE114_WORKFLOW_MYSQL_URL=f"mysql+pymysql://root@localhost/test_issue114_workflow?unix_socket={socket}")
                migration_env = dict(env, DATABASE_URL=env["ISSUE114_WORKFLOW_MYSQL_URL"],
                    RAG_DATABASE_URL=env["ISSUE114_WORKFLOW_MYSQL_URL"], ISSUE90_CONTRACT_CONFIRMED="1")
                # 全新空库也必须经过旧 #90 的实际迁移阶段门，不伪造 checkpoint。
                commands = [["alembic", "upgrade", "issue90_copy_v1"]]
                commands += [["backend.scripts.migrate_issue90_properties", action]
                             for action in ("final-sync", "read-switch", "write-switch", "observe")]
                commands += [["alembic", "upgrade", "heads"]]
                for command in commands:
                    migration = subprocess.run([sys.executable, "-m", *command], cwd=root, env=migration_env)
                    if migration.returncode:
                        return migration.returncode
                result = subprocess.run([sys.executable, "-m", "pytest", "-q",
                    "tests/01_decentralized_uploading/test_issue114_end_to_end.py", "--tb=short", *sys.argv[1:]], cwd=root, env=env)
                return result.returncode
            finally:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
