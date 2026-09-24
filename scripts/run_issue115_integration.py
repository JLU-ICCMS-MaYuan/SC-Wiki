"""使用隔离 MySQL 验证 #115，不读取业务配置或连接业务数据库。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pymysql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="自动测试后启动最长 15 分钟的浏览器夹具")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    mysqld = shutil.which("mysqld") or str(Path(sys.executable).parent / "mysqld")
    go = shutil.which("go") or str(root / ".local/go/bin/go")
    with tempfile.TemporaryDirectory(prefix="scwiki-115-mysql-") as directory:
        temporary = Path(directory)
        socket = temporary / "mysql.sock"
        with (temporary / "mysql.log").open("w+") as log:
            initialized = subprocess.run(
                [mysqld, "--no-defaults", "--initialize-insecure", f"--datadir={temporary / 'data'}"],
                stdout=log, stderr=log,
            )
            if initialized.returncode:
                log.seek(0)
                raise RuntimeError("隔离 MySQL 初始化失败：" + log.read()[-3000:])
            server = subprocess.Popen([
                mysqld, "--no-defaults", f"--datadir={temporary / 'data'}", f"--socket={socket}",
                f"--pid-file={temporary / 'mysql.pid'}", "--skip-networking", "--mysqlx=0",
            ], stdout=log, stderr=log)
            try:
                connection = None
                for _ in range(200):
                    try:
                        connection = pymysql.connect(user="root", unix_socket=str(socket))
                        break
                    except pymysql.Error:
                        if server.poll() is not None:
                            break
                        time.sleep(0.1)
                if connection is None:
                    log.seek(0)
                    raise RuntimeError("隔离 MySQL 未就绪：" + log.read()[-3000:])
                with connection.cursor() as cursor:
                    cursor.execute("CREATE DATABASE scwiki_publication_stats_test CHARACTER SET utf8mb4")
                connection.close()
                env = dict(os.environ)
                env.setdefault("GOPATH", str(Path.home() / ".local/gopath"))
                env.setdefault("GOCACHE", str(Path.home() / ".cache/go-build"))
                env["PUBLICATION_STATS_TEST_DSN"] = f"root@unix({socket})/scwiki_publication_stats_test?parseTime=true&charset=utf8mb4"
                env.pop("PUBLICATION_BROWSER_FIXTURE", None)
                subprocess.run([
                    go, "test", "./handlers", "-run",
                    "TestPublication|TestCommunityContributions|TestRankContribution|TestTopContribution",
                    "-count=1", "-v",
                ], cwd=root / "goserver", env=env, check=True)
                if args.browser:
                    stop_file = temporary / "stop-browser"
                    env.update(PUBLICATION_BROWSER_FIXTURE="1", PUBLICATION_BROWSER_STOP_FILE=str(stop_file))
                    print(f"浏览器夹具：http://127.0.0.1:19115/share/rankings\n创建此文件可结束：{stop_file}", flush=True)
                    subprocess.run([
                        go, "test", "./handlers", "-run", "^TestPublicationBrowserFixture$",
                        "-count=1", "-v", "-timeout=16m",
                    ], cwd=root / "goserver", env=env, check=True)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
