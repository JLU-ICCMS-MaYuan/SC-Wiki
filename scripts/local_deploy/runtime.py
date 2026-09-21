"""复用 dev.sh 启停本项目服务，验证 PID 的真实归属。"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from .environment import run

APPS = ('news-scheduler', 'frontend', 'goserver', 'worker', 'news-worker', 'python')


def port_occupied(number):
    # 绑定检查不会受防火墙丢弃连接或监听队列拥塞影响。
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', number))
        except OSError:
            return True
    return False


class Runtime:
    def __init__(self, root: Path, prefix: Path, values: dict, data: Path | None = None):
        self.root, self.prefix, self.values = root, prefix, values
        self.data = data or root / '.data'
        self.local = root / '.local'
        self.env = {**os.environ, **values, 'JAVA_HOME': str(prefix), 'PYTHONNOUSERSITE': '1',
                    'PATH': f'{prefix}/bin:{self.local}/go/bin:' + os.environ.get('PATH', ''),
                    'SCWIKI_DEPLOY_DATA_DIR': str(self.data)}

    def dev(self, action, *services):
        run(['bash', self.root / 'scripts/dev.sh', action, *services], cwd=self.root, env=self.env, timeout=900)

    def check_ports(self):
        ports = {'mysql': (3307,), 'redis': (6379,), 'neo4j': (17687, 7474), 'qdrant': (6333, 6334),
                 'python': (8000,), 'goserver': (8080,), 'frontend': (5173,)}
        import re
        listeners = run(['ss', '-ltnp'], capture=True)
        for service, numbers in ports.items():
            for number in numbers:
                if not port_occupied(number):
                    continue
                pid = self.owned_pid(service)
                lines = [line for line in listeners.splitlines() if re.search(rf':{number}\s', line)]
                listening_pids = {int(p) for line in lines for p in re.findall(r'pid=(\d+)', line)}
                if pid is None or not listening_pids:
                    raise ValueError(f'端口 {number} 归属不明，拒绝复用')
                group = os.getpgid(pid)
                if any(os.getpgid(p) != group for p in listening_pids):
                    raise ValueError(f'端口 {number} 属于其他进程')
        if port_occupied(8070):
            import hashlib
            name = 'scwiki-grobid-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
            label = run(['docker', 'inspect', '--format', '{{index .Config.Labels "scwiki.root"}}', name], capture=True).strip()
            if label != str(self.root):
                raise ValueError('GROBID 容器不属于当前项目')

    def owned_pid(self, name):
        path = self.local / 'run' / (name + '.pid')
        if not path.is_file():
            return None
        try:
            pid = int(path.read_text().strip())
            if Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].startswith('Z'):
                return None
            cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
            cwd = Path(f'/proc/{pid}/cwd').resolve()
        except (OSError, ValueError):
            return None
        if pid <= 1 or (str(self.root) not in cmd and self.root not in (cwd, *cwd.parents)):
            raise ValueError(f'{name} PID 文件不属于当前项目')
        if os.getpgid(pid) != pid:
            raise ValueError(f'{name} 未使用独立进程组，拒绝操作')
        return pid

    def stop_gracefully(self, name, timeout=300):
        pid = self.owned_pid(name)
        if pid is None:
            return
        # 只向确认归属的组发送 TERM，打包永不强杀任务。
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                stat = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1]
                if stat.startswith('Z'):
                    break
            except OSError:
                break
            time.sleep(0.25)
        else:
            raise ValueError(f'{name} 在 {timeout} 秒内未停止，未强制终止')
        (self.local / 'run' / (name + '.pid')).unlink(missing_ok=True)

    def prepare(self):
        for name in ('run', 'log'):
            (self.local / name).mkdir(parents=True, exist_ok=True)
        for name in ('mysql', 'redis', 'neo4j/data', 'neo4j/logs', 'qdrant/storage', 'qdrant/snapshots', 'avatars'):
            (self.data / name).mkdir(parents=True, exist_ok=True)
        # 客户端密码只放 0600 配置，命令行不带密码。
        password = self.values['MYSQL_ROOT_PASSWORD']
        escape = lambda v: str(v).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        cnf = self.local / 'my.cnf'
        cnf.touch(mode=0o600)
        cnf.chmod(0o600)
        cnf.write_text(f'''[mysqld]
basedir="{escape(self.prefix)}"
datadir="{escape(self.data / 'mysql')}"
socket="{escape(self.local / 'run/mysql.sock')}"
port=3307
bind-address=127.0.0.1
mysqlx=OFF
pid-file="{escape(self.local / 'run/mysql.pid')}"
log-error="{escape(self.local / 'log/mysql.err')}"
character-set-server=utf8mb4
disable-log-bin
event-scheduler=OFF
[client]
host=127.0.0.1
port=3307
socket="{escape(self.local / 'run/mysql.sock')}"
user=root
password="{escape(password)}"
''')
        neo = self.local / 'neo4j'
        baseline = neo / 'conf/neo4j.conf.deployment-original'
        if not baseline.exists():
            baseline.write_bytes((neo / 'conf/neo4j.conf').read_bytes())
        config = baseline.read_text() + f'''
# SC-Wiki 本机部署覆盖
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:17687
server.bolt.advertised_address=127.0.0.1:17687
server.http.listen_address=127.0.0.1:7474
server.directories.data={self.data / 'neo4j/data'}
server.directories.logs={self.data / 'neo4j/logs'}
server.directories.run={self.local / 'run-neo4j'}
'''
        # Neo4j 拒绝重复配置键，只替换同名配置项。
        import re
        lines, seen = [], set()
        for line in reversed(config.splitlines()):
            key = line.split('=', 1)[0].strip()
            if '=' in line and not key.startswith('#'):
                if key in seen:
                    continue
                seen.add(key)
            lines.append(line)
        (neo / 'conf/neo4j.conf').write_text('\n'.join(reversed(lines)) + '\n')

    def initialize_mysql(self):
        import pymysql
        if (self.data / 'mysql/mysql').exists():
            raise ValueError('临时 MySQL 已有数据，需检查上次中断阶段')
        cnf = self.local / 'my.cnf'
        run([self.prefix / 'bin/mysqld', f'--defaults-file={cnf}', '--initialize-insecure'], env=self.env)
        with (self.local / 'log/mysql-bootstrap.log').open('ab') as log:
            process = subprocess.Popen([str(self.prefix / 'bin/mysqld'), f'--defaults-file={cnf}'],
                                       env=self.env, cwd=self.root, start_new_session=True,
                                       stdout=log, stderr=log)
        (self.local / 'run/mysql.pid').write_text(str(process.pid))
        deadline = time.monotonic() + 90
        while True:
            try:
                connection = pymysql.connect(unix_socket=str(self.local / 'run/mysql.sock'), user='root',
                                             password='', autocommit=True, connect_timeout=2)
                break
            except pymysql.Error:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise ValueError('临时 MySQL 初始化启动失败') from None
                time.sleep(1)
        from .storage import identifier
        with connection, connection.cursor() as cursor:
            cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (self.values['MYSQL_ROOT_PASSWORD'],))
            database = self.values['MYSQL_DATABASE']
            cursor.execute(f'CREATE DATABASE {identifier(database)} CHARACTER SET utf8mb4')
            for host in ('localhost', '127.0.0.1'):
                cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s', (self.values['MYSQL_USER'], host, self.values['MYSQL_PASSWORD']))
                cursor.execute(f'GRANT ALL ON {identifier(database)}.* TO %s@%s', (self.values['MYSQL_USER'], host))

    def neo_admin(self, args):
        run([self.local / 'neo4j/bin/neo4j-admin', *args], env=self.env, cwd=self.root)

    @contextmanager
    def quiesce(self):
        from .storage import assert_no_jobs, redis_connection, export_redis
        running = [name for name in APPS if self.owned_pid(name)]
        stopped = []
        try:
            # 先拒绝已知作业，再暂停入口/调度，之后复核，避免等待队列无限增长。
            export_redis(redis_connection(self.values))
            for name in ('news-scheduler', 'frontend', 'goserver', 'python'):
                if name in running:
                    self.stop_gracefully(name)
                    stopped.append(name)
            export_redis(redis_connection(self.values))
            for name in ('worker', 'news-worker'):
                if name in running:
                    self.stop_gracefully(name)
                    stopped.append(name)
            export_redis(redis_connection(self.values))
            yield
        finally:
            errors = []
            # 源实例恢复不执行普通 start_python 的历史迁移。
            self.env['SCWIKI_DEPLOY_SKIP_MIGRATIONS'] = '1'
            for name in reversed(stopped):
                try:
                    self.dev('start', name)
                except Exception:
                    errors.append(name)
            if errors:
                raise ValueError('源服务恢复失败：' + ', '.join(errors))


if __name__ == '__main__':
    import sys
    from .config import read_config
    from .environment import runtime_prefix
    root = Path(sys.argv[1]).resolve()
    try:
        Runtime(root, runtime_prefix(root), read_config(root)).check_ports()
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
