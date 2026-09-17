"""Run real community migrations, Go integration and optional Chromium acceptance in disposable services."""
from __future__ import annotations
import argparse
import functools
import http.client
import http.server
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix="scwiki-community-acceptance-"))
    password = secrets.token_hex(24)
    env_file = directory / "mysql.env"
    env_file.write_text(f"MYSQL_ROOT_PASSWORD={password}\nMYSQL_ROOT_HOST=%\nMYSQL_DATABASE=scwiki_community_test\n")
    env_file.chmod(0o600)
    names = [f"scwiki-community-mysql-{secrets.token_hex(4)}", f"scwiki-community-redis-{secrets.token_hex(4)}"]
    processes = []
    services = []
    server = None
    try:
        mysql_port, redis_port = free_port(), free_port()
        for name, image, port, inside in [(names[0], "mysql:8.4", mysql_port, 3306), (names[1], "redis:7-alpine", redis_port, 6379)]:
            command = ["docker", "run", "--rm", "-d", "--name", name, "-p", f"127.0.0.1:{port}:{inside}"]
            if inside == 3306:
                command += ["--env-file", str(env_file)]
            run(command + [image], stdout=subprocess.DEVNULL)
            services.append(name)
        os.environ["DATABASE_URL"] = f"mysql+pymysql://root:{password}@127.0.0.1:{mysql_port}/scwiki_community_test?charset=utf8mb4"
        from sqlalchemy import create_engine, text
        engine = create_engine(os.environ["DATABASE_URL"])
        print("Waiting for disposable MySQL…", flush=True)
        for attempt in range(60):
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                break
            except Exception:
                if attempt == 59:
                    raise RuntimeError("Disposable MySQL did not start") from None
                time.sleep(1)
        import sys
        sys.path.insert(0, str(ROOT))
        from backend import models  # noqa: F401
        from backend.database import Base
        # Only the existing paper/identity boundary is needed; community tables come from the migration.
        names_needed = {"users", "papers", "chemical_systems", "periodic_table_elements", "material_states", "paper_material_families", "material_families", "superconductors"}
        while True:
            dependencies = {foreign.column.table.name for name in names_needed for foreign in Base.metadata.tables[name].foreign_keys}
            if dependencies <= names_needed:
                break
            names_needed |= dependencies
        Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name in names_needed])
        from backend.scripts.init_db import seed_periodic_table_elements
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            seed_periodic_table_elements(session)
            session.commit()
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        path = ROOT / "alembic/versions/20260917_0107_community_discussion.py"
        spec = importlib.util.spec_from_file_location("community_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.downgrade()
                migration.upgrade()
        print("Migration upgrade / downgrade / upgrade passed.", flush=True)
        go = os.environ.get("SCWIKI_GO_BIN") or shutil.which("go") or str(Path.home() / ".local/go/bin/go")
        env = dict(os.environ, COMMUNITY_TEST_DSN=f"root:{password}@tcp(127.0.0.1:{mysql_port})/scwiki_community_test?charset=utf8mb4&parseTime=true&loc=UTC", COMMUNITY_TEST_REDIS=f"127.0.0.1:{redis_port}")
        run([go, "test", "./handlers", "-run", "^TestCommunityMySQL", "-count=1", "-v"], cwd=ROOT / "goserver", env=env)
        if args.browser:
            api_port = free_port()
            fixture = directory / "fixture.json"
            env.update(COMMUNITY_BROWSER_ADDR=f"127.0.0.1:{api_port}", COMMUNITY_BROWSER_FIXTURE=str(fixture))
            with (directory / "go-browser.log").open("w") as log:
                process = subprocess.Popen([go, "test", "./handlers", "-run", "^TestCommunityBrowserServer$", "-count=1", "-timeout=15m"], cwd=ROOT / "goserver", env=env, stdout=log, stderr=log, start_new_session=True)
            processes.append(process)
            for _ in range(100):
                if fixture.exists():
                    try:
                        with socket.create_connection(("127.0.0.1", api_port), timeout=1):
                            break
                    except OSError:
                        pass
                if process.poll() is not None:
                    raise RuntimeError(f"Fixture server failed; see {directory / 'go-browser.log'}")
                time.sleep(0.2)
            else:
                raise RuntimeError("Fixture server did not become ready")

            class Proxy(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def handle_request(self):
                    if self.path.startswith("/api/"):
                        length = int(self.headers.get("Content-Length", "0"))
                        connection = http.client.HTTPConnection("127.0.0.1", api_port, timeout=30)
                        connection.request(self.command, self.path, body=self.rfile.read(length) if length else None, headers={key: value for key, value in self.headers.items() if key.lower() not in ("host", "connection")})
                        response = connection.getresponse()
                        payload = response.read()
                        self.send_response(response.status)
                        self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        connection.close()
                    else:
                        candidate = Path(self.translate_path(self.path.split("?")[0]))
                        if not candidate.is_file():
                            self.path = "/index.html"
                        super().do_GET()

                do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Proxy, directory=str(ROOT / "frontend/static")))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            env.update(COMMUNITY_BASE_URL=f"http://127.0.0.1:{server.server_port}", COMMUNITY_ARTIFACT_DIR=str(directory))
            run(["node", "tests/07_researcher_community_forum/community-browser.mjs"], cwd=ROOT, env=env)
        print(f"Community acceptance passed. Artifacts: {directory}", flush=True)
    finally:
        if server:
            server.shutdown()
        for process in processes:
            import signal
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
        for name in reversed(services):
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if env_file.exists():
            env_file.unlink()
        # Temporary tokens only belong to the disposable service and are not retained in artifacts.
        (directory / "fixture.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
