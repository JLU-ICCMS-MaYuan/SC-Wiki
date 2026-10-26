"""启动专用本机进程；不启停正式网站或占用其他任务的端口。"""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[5]
DEMO = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".local/tc-model-demo"


def main():
    for port in (8192, 5189):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"端口 {port} 已使用；请核对已有进程，不自动抢占或停止。")
    python = CACHE / "venv/bin/python"
    if not python.exists():
        raise SystemExit("请先按 quickstart.md 准备独立推理环境")
    commands = [
        ("api", [str(python), "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8192", "--reload", "--reload-dir", str(DEMO)]),
        ("web", [shutil.which("node"), str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5189", "--strictPort"]),
    ]
    processes = {}
    for name, command in commands:
        with (CACHE / f"{name}.log").open("ab") as log:
            p = subprocess.Popen(command, cwd=DEMO, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes[name] = {"pid": p.pid, "command": command, "cwd": str(DEMO)}
    (CACHE / "processes.json").write_text(json.dumps(processes, indent=2))
    for url in ("http://127.0.0.1:8192/demo-api/health", "http://127.0.0.1:5189/"):
        for attempt in range(30):
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, TimeoutError):
                time.sleep(.4)
        else:
            raise SystemExit(f"启动未就绪，请检查 {CACHE} 中日志：{url}")
    print("Demo 已启动：http://127.0.0.1:5189/")


if __name__ == "__main__":
    main()
