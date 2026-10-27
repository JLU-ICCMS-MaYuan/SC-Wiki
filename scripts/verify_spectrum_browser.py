"""正式谱浏览器回归：每套独立测试存储，绝不请求业务后端。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

SUITES = {
    "relative": "spectrum-relative-production.cjs",
    "insertion_vertical": "spectrum-insert-production.cjs",
    "insertion": "spectrum-insert-production.cjs",
    "preflight": "spectrum-preflight-production.cjs",
    "revalidation": "spectrum-revalidation-production.cjs",
    "version": "spectrum-version-production.cjs",
    "manual": "spectrum-manual-production.cjs",
    "recalculate": "spectrum-recalculate-production.cjs",
    "diagnostics": "spectrum-diagnostics-production.cjs",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=list(SUITES), action="append")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name in args.suite or SUITES:
        # 避免误用已在运行的服务器或测试串到其他环境。
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 8191)) == 0:
                raise RuntimeError("8191端口已占用，不启动或复用未知服务")
        test_root = Path(tempfile.mkdtemp(prefix="scwiki-manual-test-full-"+name+"-", dir="/tmp"))
        dest = output / name
        dest.mkdir(exist_ok=True)
        env = {**os.environ, "SCWIKI_MANUAL_TEST_ROOT": str(test_root),
               "DATABASE_URL": "sqlite:///"+str(test_root/"test.sqlite"),
               "FILE_STORAGE_BACKEND": "local", "FILE_STORAGE_LOCAL_ROOT": str(test_root/"files"),
               "JWT_SECRET_KEY": "isolated-spectrum-browser-tests",
               # 人工编辑旧套件使用像素DOS，积分套件使用绝对密度；不能混用数值范围。
               "SCWIKI_RECALCULATE_TEST_FIXTURES": "0" if name == "manual" else "1",
               "SCWIKI_SPECTRUM_BROWSER_OUT": str(dest),
               "SCWIKI_REVALIDATE_TEST_FIXTURES": "1" if name == "revalidation" else "0",
               "SCWIKI_INSERT_VERTICAL_FIXTURES": "1" if name == "insertion_vertical" else "0",
               "SCWIKI_RELATIVE_TEST_FIXTURES": "1" if name == "relative" else "0"}
        with (test_root/"server.log").open("w") as log:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.tests.manual_editor_server:app",
                                       "--host", "127.0.0.1", "--port", "8191"],
                                      cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("测试服务启动失败，见 "+str(test_root/"server.log"))
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:8191/test-info", timeout=1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError("测试服务未就绪")
                with (dest/"console.log").open("w") as console:
                    result = subprocess.run(["node", str(root/"tests/01_decentralized_uploading"/SUITES[name])],
                                            cwd=root, env=env, stdout=console, stderr=subprocess.STDOUT, timeout=180)
                results.append(dict(suite=name, exit_code=result.returncode, test_root=str(test_root)))
                print(name, result.returncode, (dest/"console.log").read_text()[-2500:], flush=True)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    (output/"browser-suite-summary.json").write_text(json.dumps(results, indent=2)+"\n")
    if any(item["exit_code"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
