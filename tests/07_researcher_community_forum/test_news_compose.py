from pathlib import Path
import re


COMPOSE_PATH = Path(__file__).parents[2] / "docker" / "compose.app.yaml"
COMPUTE_PATH = Path(__file__).parents[2] / "docker" / "compose.compute.yaml"
RUNTIME_PATH = Path(__file__).parents[2] / "docker" / "compose.runtime.yaml"
DEV_SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "dev.sh"


def service_block(compose: str, name: str) -> str:
    marker = f"  {name}:\n"
    start = compose.index(marker)
    next_service = re.search(r"^  [a-z][a-z0-9-]*:\n", compose[start + len(marker):], re.MULTILINE)
    return compose[start:] if next_service is None else compose[start:start + len(marker) + next_service.start()]


def test_news_services_are_started_separately_from_upload_worker():
    compose = COMPOSE_PATH.read_text()
    scheduler = service_block(compose, "news-scheduler")
    worker = service_block(compose, "news-worker")
    upload_worker = service_block(COMPUTE_PATH.read_text(), "worker")

    assert 'extends: {file: compose.runtime.yaml, service: python-base}' in scheduler
    assert 'command: ["python", "-m", "backend.news", "schedule"]' in scheduler
    assert 'command: ["python", "-m", "backend.news", "worker"]' in worker
    assert 'command: ["python", "-m", "backend.scripts.run_upload_workers"]' in upload_worker

    assert 'env_file: ["${SCWIKI_ROOT:?}/private/app.env"]' in RUNTIME_PATH.read_text()
    assert 'restart: unless-stopped' in RUNTIME_PATH.read_text()
    for block in (scheduler, worker):
        assert 'depends_on' not in block


def test_local_dev_starts_news_processes_by_default():
    dev_script = DEV_SCRIPT_PATH.read_text()

    assert "APP_SERVICES=(python worker community-worker news-worker news-scheduler goserver frontend)" in dev_script
    assert 'spawn worker env UPLOAD_LLM_CONCURRENCY=1' in dev_script
    assert '"$PY_BIN/python" -m backend.scripts.run_upload_workers' in dev_script
    assert 'spawn news-worker "$PY_BIN/python" -m backend.news worker' in dev_script
    assert 'spawn news-scheduler "$PY_BIN/python" -m backend.news schedule' in dev_script
