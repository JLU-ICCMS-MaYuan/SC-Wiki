"""主站模型 API 的失败隔离、白名单和真实进程生命周期边界。"""
import asyncio
import hashlib
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api import tc_models
from backend.prediction import artifacts, runner


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tc_models.router)
    with TestClient(app) as client:
        yield client


def test_catalog_removes_deferred_model_and_downloads(client):
    response = client.get("/api/tc-models/catalog")
    assert response.status_code == 200
    data = response.json()
    assert {m["id"] for m in data["models"]} == {"bete-cso", "sisso-2019", "sisso-2022", "legacy"}
    assert all("81" not in m["id"] for m in data["datasets"])
    assert client.get("/api/tc-models/datasets/sisso-81").status_code == 404
    assert client.post("/api/tc-models/predict", json={"model_id": "sisso-81-model"}).status_code == 400


def test_real_parameter_formula_and_invalid_values(client):
    response = client.post("/api/tc-models/predict", json={"model_id": "sisso-2022", "parameters": {"lambda": 2, "omega_log": 1000, "omega_2": 1500, "mu_star": .1}})
    assert response.status_code == 200
    assert response.json()["tc"] == pytest.approx(209.3154165353737)
    for request in [[], {"model_id": "sisso-2019", "parameters": []}, {"model_id": "bete-cso", "structure": ""}, {"model_id": "sisso-2019", "parameters": {"lambda": "nan", "omega_log": 100, "mu_star": .1}}]:
        assert client.post("/api/tc-models/predict", json=request).status_code == 400
    assert client.post("/api/tc-models/predict", content=b"x" * (301 * 1024)).status_code == 413


def test_download_verifies_content_and_refuses_tampering(client, tmp_path, monkeypatch):
    data = b"original data\n"
    path = tmp_path / "datasets" / "source.csv"
    path.parent.mkdir()
    path.write_bytes(data)
    item = {"id": "source", "filename": "source.csv", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    monkeypatch.setattr(artifacts, "CACHE", tmp_path)
    monkeypatch.setattr(tc_models, "CACHE", tmp_path)
    monkeypatch.setattr(artifacts, "source_catalog", lambda: {"models": [], "datasets": [item]})
    response = client.get("/api/tc-models/datasets/source")
    assert response.content == data
    assert "attachment" in response.headers["content-disposition"]
    path.write_bytes(b"modified data\n")  # 同长度，必须比较摘要。
    assert client.get("/api/tc-models/datasets/source").status_code == 503
    path.unlink()
    assert client.get("/api/tc-models/datasets/source").status_code == 503


def test_missing_runtime_is_503_without_breaking_parameter_models(client, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "runtime_python", lambda: tmp_path / "absent")
    response = client.post("/api/tc-models/predict", json={"model_id": "bete-cso", "structure": "test"})
    assert response.status_code == 503
    assert client.get("/api/tc-models/catalog").status_code == 200


def test_worker_rejects_missing_artifacts_before_importing_model(tmp_path):
    import os
    import subprocess
    import json
    result = subprocess.run(
        [sys.executable, "-m", "backend.prediction.worker"],
        input='{"model_id":"bete-cso","structure":"test"}', text=True, capture_output=True,
        env={**os.environ, "TC_MODEL_CACHE": str(tmp_path)}, timeout=10,
    )
    response = json.loads(result.stdout)
    assert response["status"] == 503
    assert "校验失败" in response["error"]


def _runtime(tmp_path, monkeypatch, worker_code):
    # 真正启动独立解释器及进程，只将模型计算替换为可控慢进程来测超时/清理。
    package = tmp_path / "backend" / "prediction"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "worker.py").write_text(worker_code)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "runtime_python", lambda: Path(sys.executable))


def test_real_process_timeout_and_busy_cleanup(tmp_path, monkeypatch):
    _runtime(tmp_path, monkeypatch, "import time\ntime.sleep(30)\n")
    monkeypatch.setattr(runner, "TIMEOUT_SECONDS", .2)

    async def scenario():
        monkeypatch.setattr(runner, "_lock", asyncio.Lock())
        task = asyncio.create_task(runner.run_structure({"model_id": "bete-cso"}))
        await asyncio.sleep(.05)
        with pytest.raises(runner.PredictionError) as busy:
            await runner.run_structure({"model_id": "bete-cso"})
        assert busy.value.status == 429
        with pytest.raises(runner.PredictionError) as timeout:
            await task
        assert timeout.value.status == 504
        assert not runner._lock.locked()
        worker = tmp_path / "backend/prediction/worker.py"
        worker.write_text('print(\' {"result":{"tc":12}} \')\n')
        assert (await runner.run_structure({"model_id": "bete-cso"}))["tc"] == 12
    asyncio.run(scenario())


def test_real_process_cancel_releases_slot(tmp_path, monkeypatch):
    _runtime(tmp_path, monkeypatch, "import time\ntime.sleep(30)\n")

    async def scenario():
        monkeypatch.setattr(runner, "_lock", asyncio.Lock())
        task = asyncio.create_task(runner.run_structure({"model_id": "bete-cso"}))
        await asyncio.sleep(.08)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not runner._lock.locked()
    asyncio.run(scenario())
