"""用户指定上传角色的清单边界及真实 Worker 来源流。"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.ingest import upload_contracts, upload_tasks


def declaration(role, filename):
    return {"client_id": filename, "role": role, "filename": filename, "size": 20}


@pytest.mark.parametrize("files", [
    [],
    [declaration("supplementary", "si.pdf")],
    [declaration("main", "one.pdf"), declaration("main", "two.pdf")],
])
def test_exactly_one_main_is_required(files):
    with pytest.raises(ValueError, match="恰好一个正文"):
        upload_contracts.validate_manifest(files)


@pytest.mark.parametrize("role,filename", [
    ("main", "cell.cif"), ("main", "POSCAR"),
    ("supplementary", "cell.vasp"), ("supplementary", "CONTCAR"),
    ("attachment", "si.pdf"), ("attachment", "notes.md"),
])
def test_manifest_rejects_files_in_wrong_area(role, filename):
    files = [declaration("main", "paper.pdf")] if role != "main" else []
    files.append(declaration(role, filename))
    with pytest.raises(ValueError, match="文件|格式"):
        upload_contracts.validate_manifest(files)


@pytest.mark.parametrize("name", ["cell.cif", "cell.poscar", "cell.vasp", "POSCAR", "CONTCAR"])
def test_multiple_supplements_and_structure_sources_keep_declared_roles(name):
    files = [declaration("main", "paper-SI.pdf"), declaration("supplementary", "article.md"),
             declaration("supplementary", "correction.txt"), declaration("attachment", name)]
    result = upload_contracts.validate_manifest(files)
    assert [x["role"] for x in result] == [x["role"] for x in files]
    assert all(x["role"] == x["declared_role"] for x in result)
    assert len({x["file_id"] for x in result}) == 4


def test_api_rejects_wrong_area_before_creating_state(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "scwiki179-isolated-test-key")
    from backend.api import upload_tasks as api
    client = MagicMock()
    client.pipeline.return_value.__enter__.return_value.zrange.return_value = []
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    body = api.CreateUploadTask(files=[declaration("main", "paper.pdf"), declaration("attachment", "si.pdf")])
    with pytest.raises(HTTPException) as error:
        api.create_upload_task(body, SimpleNamespace(id=7))
    assert error.value.status_code == 400
    assert error.value.detail["code"] == "INVALID_MANIFEST"
    client.pipeline.assert_not_called()


def test_create_task_persists_server_owned_role_policy_and_main_filename(monkeypatch):
    client = MagicMock()
    pipe = client.pipeline.return_value.__enter__.return_value
    pipe.zrange.return_value = []
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    state = upload_tasks.create_task(7, files=[
        declaration("supplementary", "correction.pdf"), declaration("main", "paper-SI.pdf"),
    ])
    assert state["file_role_policy"] == "user-specified-v1"
    assert state["filename"] == "paper-SI.pdf"
    persisted = json.loads(pipe.set.call_args.args[1])
    assert persisted["file_role_policy"] == state["file_role_policy"]


def test_source_structure_roundtrip_preserves_file_identity(tmp_path):
    """真实 ASE 解析、多格式导出和隔离 JSON 保存重读，不模拟结构处理。"""
    from backend.services.structure_candidates import build_structure_candidate, read_atoms
    from ase import Atoms
    from ase.io import write
    from hashlib import sha256

    atoms = Atoms("LaH", cell=[3, 3, 3], scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]], pbc=True)
    candidates = []
    for index, fmt in enumerate(["cif", "vasp"]):
        original = tmp_path / ("cell." + fmt)
        write(original, atoms, format=fmt)
        text = original.read_text()
        source = {"file_id": str(index), "role": "attachment", "filename": "cell." + fmt,
                  "sha256": sha256(text.encode()).hexdigest()}
        candidate = build_structure_candidate(structure_format="cif" if fmt == "cif" else "poscar",
            structure_text=text, source=source, material_state_ref="unassigned:" + str(index))
        assert candidate["validation"]["ase_valid"]
        assert candidate["sources"] == [source]
        assert candidate["original_text"] == text
        restored = read_atoms(candidate["original_format"], candidate["original_text"])
        assert sorted(restored.get_chemical_symbols()) == ["H", "La"]
        assert set(candidate["representations"]) == {"primitive", "conventional"}
        candidates.append(candidate)
    target = tmp_path / "candidates.json"
    target.write_text(json.dumps(candidates))
    assert json.loads(target.read_text()) == candidates


def test_formal_chunk_extraction_keeps_supplement_and_correction_values(tmp_path, monkeypatch):
    """固定响应重放穿过正式提取校验、来源绑定、文件保存和科学记录组装。"""
    from copy import deepcopy
    from backend.ingest import upload_jobs
    from backend.ingest.chunker import Chunk
    from backend.ingest.domain_extraction import merge_scientific_candidates
    from backend.storage import paths

    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path)
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: {"status": "reading"})
    monkeypatch.setattr(paths, "object_mode", lambda: False)
    results = []
    for file_id, value in [("supplement", 90), ("correction", 95)]:
        quote = f"LaH10 Tc = {value} K at 150 GPa"
        evidence = {"file_id": file_id, "pdf_page": 1, "block_id": "b1", "quote": quote}
        context = {"file_id": file_id, "pages": [{"geometry": {"pdf_page": 1},
            "blocks": [{"block_id": "b1", "pdf_page": 1, "text": quote}], "tables": []}]}
        raw = {"extraction_version": "1", "material_states": [{
            "scope": "current_paper", "material": "LaH10", "state_kind": "experimental",
            "pressure_value_gpa": 150, "evidences": [evidence],
            "property_modules": [{"module_code": "superconductive_properties", "records": [{
                "module_code": "superconductive_properties", "record_type": "measured_tc", "property_code": "tc",
                "name_raw": "critical temperature", "value_kind": "number", "value_number": value,
                "value_raw": str(value) + " K", "unit_raw": "K", "canonical_unit": "K",
                "method_code": "unknown", "payload": {"experimental_conditions": {"description": ""}},
                "evidences": [evidence],
            }]}],
        }]}
        monkeypatch.setattr(upload_jobs, "complete_json", lambda *_a, _raw=raw, **_kw: deepcopy(_raw))
        chunk = Chunk(0, 0, "Document IR", None, json.dumps(context), 50)
        result = upload_jobs._read_chunk("isolated-179", chunk, file_id,
            {"file_id": file_id, "original_filename": file_id + ".pdf",
             "role": "supplementary", "kind": "pdf", "parser_profile": "complementary"})
        stored = json.loads((tmp_path / "chunks" / file_id / "00000.json").read_text())
        assert stored == result
        assert stored["_source"]["file_id"] == file_id
        assert stored["_source"]["file_role"] == "supplementary"
        results.append(result)
    states = merge_scientific_candidates(results)
    records = [r for s in states for m in s["property_modules"] for r in m["records"]]
    assert {r["value_number"] for r in records} == {90, 95}
    assert {e["file_id"] for r in records for e in r["evidences"]} == {"supplement", "correction"}


@pytest.mark.parametrize("main_text", [
    "Supporting Information\nFig. S1. Main results at 100 GPa.",
    "A short readable primary report.",
    "## Primary research article\nAbstract\nIntroduction\nResults\n",
])
def test_worker_never_reassesses_user_roles_and_reads_all_supplements(tmp_path, monkeypatch, main_text):
    from backend.ingest import document_roles, upload_jobs

    task_id = "1" * 32
    texts = {
        "main": main_text,
        "si": "## Another complete research article\nAbstract\nResults\nThe measured Tc was 90 K.",
        "correction": "Correction: the measured Tc should be 95 K at 100 GPa.",
    }
    files = []
    for key, text in texts.items():
        path = tmp_path / f"{key}.txt"
        path.write_text(text)
        files.append({"file_id": key, "role": "main" if key == "main" else "supplementary",
                      "declared_role": "main" if key == "main" else "supplementary",
                      "original_filename": "paper-SI.txt" if key == "main" else f"{key}.txt",
                      "kind": "txt", "sha256": key, "stored_path": str(path), "upload_status": "completed"})
    state = {"task_id": task_id, "user_id": 7, "status": "queued", "parser_profile": "legacy",
             "file_role_policy": "user-specified-v1", "files": files}
    transitions, seen = [], []
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: state)
    monkeypatch.setattr(upload_jobs, "markdown_path", lambda _: tmp_path / "combined.md")
    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path / "artifacts")
    monkeypatch.setattr(upload_jobs, "data_path", lambda name: tmp_path / name)

    def update(_, **changes):
        state.update(changes)
        transitions.append(changes)
        return dict(state)

    monkeypatch.setattr(upload_jobs, "update_state", update)
    monkeypatch.setattr(document_roles, "assess_roles", lambda *_: pytest.fail("新任务不得判断角色"))

    def read(_task, chunk, file_id=None, source=None):
        seen.append((file_id, source["role"], chunk.content))
        return {"metadata": {}, "material_states": []}

    monkeypatch.setattr(upload_jobs, "_read_chunk", read)
    monkeypatch.setattr(upload_jobs, "complete_json", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("summary-boundary")))
    with pytest.raises(RuntimeError, match="summary-boundary"):
        upload_jobs._process_upload_task(task_id)
    assert {key for key, _, _ in seen} == set(texts)
    assert any(key == "correction" and "95 K" in text for key, _, text in seen)
    assert all(role == ("main" if key == "main" else "supplementary") for key, role, _ in seen)
    assert not any(x.get("status") == "needs_role_review" for x in transitions)
    assert state.get("role_assessment") is None
    assert [x["role"] for x in state["files"]] == ["main", "supplementary", "supplementary"]
