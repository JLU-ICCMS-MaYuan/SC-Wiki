"""宿主进程检查与独立会话启动，不依赖 Linux 专有命令。"""
from __future__ import annotations

from pathlib import Path
import platform
import subprocess
import sys


def process_info(pid: int):
    """返回非僵尸进程的命令和工作目录；不存在时返回 None。"""
    if pid <= 1:
        raise ValueError('无效的服务 PID')
    if platform.system() != 'Darwin':
        try:
            if Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].startswith('Z'):
                return None
            command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
            return command, Path(f'/proc/{pid}/cwd').resolve()
        except (OSError, ValueError):
            return None
    result = subprocess.run(['ps', '-ww', '-p', str(pid), '-o', 'stat=', '-o', 'command='],
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 1 and not result.stdout.strip():
        return None
    if result.returncode:
        raise ValueError('无法核对本机进程状态')
    status, command = result.stdout.strip().split(None, 1)
    if status.startswith('Z'):
        return None
    result = subprocess.run(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
                            capture_output=True, text=True, timeout=10)
    cwd = next((Path(line[1:]).resolve() for line in result.stdout.splitlines()
                if line.startswith('n')), None)
    if cwd is None:
        # 进程可能在 ps 和 lsof 之间退出；重新确认，不能误报归属失败。
        state = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='],
                               capture_output=True, text=True, timeout=10)
        if (state.returncode == 1 and not state.stdout.strip()) or state.stdout.strip().startswith('Z'):
            return None
        raise ValueError('无法核对本机进程工作目录')
    return command, cwd


def listening_pids(port: int) -> set[int]:
    result = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'],
                            capture_output=True, text=True, timeout=10)
    if result.returncode not in (0, 1):
        raise ValueError('无法核对本机端口归属')
    return {int(line) for line in result.stdout.splitlines() if line.strip()}


def java_home(prefix: Path) -> Path:
    # Conda 的 macOS JDK 位于 lib/jvm 目录，Linux JDK 直接位于环境前缀。
    for candidate in (prefix / 'lib/jvm', prefix):
        if (candidate / 'bin/java').is_file():
            return (candidate / 'bin/java').resolve().parent.parent
    return prefix


def spawn(pidfile: Path, logfile: Path, command: list[str]):
    with logfile.open('ab') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=output, start_new_session=True)
    pidfile.write_text(str(process.pid) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == 'spawn':
        spawn(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
    elif sys.argv[1] == 'java-home':
        print(java_home(Path(sys.argv[2])))
    elif sys.argv[1] == 'port-busy':
        import socket
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', int(sys.argv[2])))
            except OSError:
                raise SystemExit(0)
        raise SystemExit(1)
