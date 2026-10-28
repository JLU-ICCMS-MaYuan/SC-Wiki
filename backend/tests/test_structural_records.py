"""#49：无状态／无Tc结构资料的实际持久化、检索、权限和导出。"""

import asyncio
import copy
import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "structural-tests-only")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from backend import models
from backend.api import structural_records as api
from backend.database import get_db
from backend.security import get_current_user_optional, get_current_user
from backend.structural_models import PaperStructuralRecord as Record
from backend.services import structural_records as service
from backend.ingest.structure_extractor import extract_structure_candidates
from backend.ingest.structural_observations import extract_lattice_observations


def geometry():
    text = """<!-- page: 8 -->
Table S1. Structural parameters at 300 GPa.
Atomic coordinates (fractional)
LaSc2 Fddd a=4.248 La (8b) 0 0 0.500
b=6.845 Sc (16f) 0 0.843 0
c=7.682 alpha=90 beta=90 gamma=90
"""
    result = extract_structure_candidates(
        text, source={"file_id": "source", "filename": "supp.pdf", "sha256": "a" * 64}
    )[0]
    result["retention"] = "retained"
    return result


def observation(material="LaSc2H24", pressure=300, key="observation"):
    return dict(
        record_key=key,
        material=material,
        pressure_value_gpa=pressure,
        space_group_symbol="P6/mmm",
        cell_parameters={"a": 4.735, "c": 3.216},
        cell_constraints={"b": "a"},
        derived_cell_parameters={"b": 4.735, "alpha": 90, "beta": 90, "gamma": 120},
        calculation_label="Harmonic",
        retention="retained",
        coordinate_status="not_reported",
        bond_lengths=[dict(pair="H-H", min=1.076, max=1.204, unit="angstrom")],
        sources=[
            dict(
                file_id="source",
                filename="supp.pdf",
                page=9,
                table="Table S2",
                row=2,
                quote="300 4.735 3.216 1.076-1.204",
            )
        ],
    )


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    models.Base.metadata.create_all(
        engine, tables=[models.User.__table__, models.Paper.__table__, Record.__table__]
    )
    with Session(engine, expire_on_commit=False) as session:
        paper = models.Paper(
            title="Structural data without Tc",
            year=2024,
            doi="10.1000/structural",
            content_revision=1,
            approved_revision=1,
            review_status="approved",
            uploaded_by_user_id=1,
            paper_type="theoretical",
            superconductor_kind="unknown",
        )
        session.add(paper)
        session.commit()
        yield session, paper
    engine.dispose()


class AsyncBridge:
    """同步测试驱动的异步调用适配；读写全部落在真实数据库上。"""

    def __init__(self, session):
        self.session = session

    async def run_sync(self, fn):
        return fn(self.session)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self):
        self.session.flush()

    def add(self, row):
        self.session.add(row)


def save(session, paper, *, candidates=None, observations=None):
    draft = dict(
        material_states=[],
        structure_candidates=[geometry()] if candidates is None else candidates,
        structural_observations=[observation()] if observations is None else observations,
    )
    asyncio.run(service.persist(AsyncBridge(session), paper, draft))
    session.commit()
    return draft


@pytest.fixture
def client(database):
    session, paper = database
    save(session, paper)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="user", is_approved=True)
    with TestClient(app) as client:
        yield client, session, paper, app


def test_unassigned_model_survives_and_partial_parameters_are_not_collected(database):
    session, paper = database
    draft = save(session, paper)
    rows = service.current_items(session, paper)
    assert len(rows) == 1 and {r.kind for r in rows} == {"model"}
    assert all(r.state_key is None for r in rows)
    restored = service.supplement_draft(session, paper, dict(material_states=[], structure_candidates=[]))
    assert restored["structure_candidates"][0]["retention"] == "retained"
    assert restored["structural_observations"] == []
    save(
        session,
        paper,
        candidates=restored["structure_candidates"],
        observations=restored["structural_observations"],
    )
    assert len(service.current_items(session, paper)) == 1


def test_removing_independent_structure_is_persisted_and_not_restored(database):
    session, paper = database
    save(session, paper)
    assert len(service.current_items(session, paper)) == 1
    save(session, paper, candidates=[], observations=[])
    assert service.current_items(session, paper) == []
    restored = service.supplement_draft(session, paper, dict(material_states=[], structure_candidates=[]))
    assert restored["structure_candidates"] == []


def test_invalid_client_geometry_cannot_erase_saved_records(database):
    session, paper = database
    save(session, paper)
    old = [r.record_key for r in service.current_items(session, paper)]
    wrong = geometry()
    wrong["reported_structure"]["material"] = "LaSc2H24"
    with pytest.raises(ValueError, match="化学式"):
        asyncio.run(
            service.persist(
                AsyncBridge(session), paper, dict(structure_candidates=[wrong], structural_observations=[])
            )
        )
    assert [r.record_key for r in service.current_items(session, paper)] == old


def test_malformed_issue_keys_and_null_cells_are_rejected_before_save():
    from fastapi import HTTPException

    # 旧客户端的无效非模型资料不进入当前收录流程。
    service.validate_draft(dict(structural_extraction_issues=[dict(record_key=['ignored'], reason='核对')]))
    value = observation()
    value["cell_parameters"]["a"] = None
    with pytest.raises(ValueError, match="空值"):
        service.normalize(value, "lattice")


def test_tc_table_followed_by_structural_prose_is_not_a_lattice_table(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (20, 30),
        "Table 1. Calculated Tc at different pressures.\nCalculation Pressure Tc\nHarmonic 300 310\nThe structural parameters change with pressure.",
        fontsize=9,
    )
    path = tmp_path / "tc.pdf"
    document.save(path)
    document.close()
    assert extract_lattice_observations(path, source={"file_id": "tc"}) == ([], [])


def test_derived_cells_are_recomputed_and_unsupported_units_are_not_relabelled():
    value = observation()
    value["derived_cell_parameters"] = {"b": 999, "gamma": 1}
    assert service.normalize(value, "lattice")["data_json"]["derived_cell_parameters"] == {
        "b": 4.735,
        "alpha": 90,
        "beta": 90,
        "gamma": 120,
    }
    value["unit"] = "nm"
    with pytest.raises(ValueError, match="单位"):
        service.normalize(value, "lattice")


def test_native_structure_attachment_is_its_own_source():
    value = geometry()
    value["source_kind"] = "attachment"
    value["original_text"] = value["representations"]["conventional"]["cif"]["text"]
    value["sources"] = [dict(file_id="native", filename="native.cif")]
    assert service.normalize(value, "model")["retention"] == "retained"


def test_public_data_excludes_private_notes(client):
    client, session, paper, app = client
    row = next(r for r in service.current_items(session, paper) if r.kind == "model")
    row.data_json = {**row.data_json, "user_note": "private review note", "internal_note": "operator-only"}
    session.commit()
    result = client.get("/api/rag/structural-records/" + row.id).json()
    assert "user_note" not in result["data"] and "internal_note" not in result["data"]


def test_public_element_search_has_structure_without_tc_and_own_elements(client):
    client, session, paper, app = client
    response = client.post(
        "/api/rag/structural-records/search", json=dict(elements=["La", "Sc"], mode="elements_exact_search")
    )
    assert response.status_code == 200, response.text
    values = response.json()
    assert values["total"] == 1
    record = values["items"][0]
    assert record["material"] == "LaSc2" and record["pressure_gpa"] == 300 and record["paper_id"] == paper.id
    assert record["doi"] == "10.1000/structural" and "tc" not in record
    contains = client.post(
        "/api/rag/structural-records/search",
        json=dict(elements=["La", "Sc"], mode="elements_contained_search"),
    ).json()
    assert contains["total"] == 1
    assert (
        client.post(
            "/api/rag/structural-records/search", json=dict(elements=["Xx"], mode="elements_exact_search")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/rag/structural-records/search", json=dict(elements=["La", "Sc"], pressure_min=350)
        ).json()["total"]
        == 0
    )


def test_pending_excluded_and_wrong_paper_revision_do_not_leak(client):
    client, session, paper, app = client
    row = next(r for r in service.current_items(session, paper) if r.kind == "model")
    identity = row.id
    row.retention = "pending"
    session.commit()
    assert client.get("/api/rag/structural-records/" + identity).status_code == 404
    assert client.get("/api/rag/structural-records/" + identity + "/download?format=cif").status_code == 404
    row.retention = "retained"
    paper.review_status = "pending"
    paper.approved_revision = None
    session.commit()
    assert client.post("/api/rag/structural-records/search", json={}).json()["total"] == 0
    assert client.get("/api/rag/structural-records/paper/" + str(paper.id)).status_code == 404
    paper.review_status = "approved"
    paper.content_revision = 2
    paper.approved_revision = 2
    session.commit()
    assert client.post("/api/rag/structural-records/search", json={}).json()["total"] == 0
    assert client.get("/api/rag/structural-records/" + identity).status_code == 404
    app.dependency_overrides[get_current_user_optional] = lambda: SimpleNamespace(
        id=1, role="user", is_approved=True
    )
    assert client.get("/api/rag/structural-records/" + identity).status_code == 404


def test_export_keeps_sources_and_partial_records_cannot_fake_atomic_file(client):
    client, session, paper, app = client
    rows = service.current_items(session, paper)
    model = next(r for r in rows if r.kind == "model")
    partial = Record(paper_id=paper.id,paper_revision=paper.content_revision,**service.normalize(observation(),"lattice"))
    session.add(partial)
    session.commit()
    response = client.get(f"/api/rag/structural-records/{model.id}/download?format=cif")
    assert response.status_code == 200 and "_atom_site" in response.text
    for format in ('json','csv','cif','poscar'):
        assert client.get(f"/api/rag/structural-records/{partial.id}/download?format={format}").status_code == 404
    assert len(client.get(f"/api/rag/structural-records/paper/{paper.id}").json()['items']) == 1



def test_revision_copy_keeps_prior_revision_and_retention(database):
    session, paper = database
    draft = save(session, paper)
    paper.content_revision = 2
    paper.approved_revision = None
    paper.review_status = "pending"
    save(
        session,
        paper,
        candidates=draft["structure_candidates"],
        observations=draft["structural_observations"],
    )
    assert len(session.scalars(select(Record).where(Record.paper_id == paper.id)).all()) == 2
    assert len(service.current_items(session, paper)) == 1


def test_independent_orthorhombic_table_preserves_rows_and_units(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (40, 30), "Table 2. Lattice parameters of Pnma-MgSiO3 at different pressures.", fontsize=10
    )
    page.insert_text((80, 65), "Pressure (GPa)", fontsize=10)
    page.insert_text((250, 65), "Lattice Parameters (Å)", fontsize=10)
    page.insert_text((220, 85), "a          b          c", fontsize=10)
    for y, text in [(115, "10  4.8  5.1  6.2"), (145, "20  4.7  5.0  6.1")]:
        page.insert_text((90, y), text, fontsize=10)
    path = tmp_path / "independent.pdf"
    document.save(path)
    document.close()
    records, issues = extract_lattice_observations(
        path, source={"file_id": "independent", "filename": "independent.pdf"}
    )
    assert not issues and len(records) == 2
    assert records[0]["material"] == "MgSiO3" and records[0]["cell_parameters"] == {
        "a": 4.8,
        "b": 5.1,
        "c": 6.2,
    }
    assert all(r["coordinate_status"] == "not_reported" and "representations" not in r for r in records)


def grouped_table(tmp_path, *, borders=True):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (20, 30), "Table S2. Structural parameters of P6/mmm-LaSc2H24 at different pressures.", fontsize=9
    )
    page.insert_text((100, 65), "Pressure (GPa)", fontsize=10)
    page.insert_text((240, 65), "Lattice Parameters (Å)", fontsize=10)
    page.insert_text((400, 65), "H-H distance (Å)", fontsize=10)
    page.insert_text((240, 85), "a = b c", fontsize=10)
    rows = [
        (290, 4.751, 3.229, "1.068-1.209"),
        (300, 4.735, 3.216, "1.076-1.204"),
        (350, 4.659, 3.157, "1.053-1.183"),
        (150, 5.084, 3.528, "1.156-1.307"),
        (167, 5.033, 3.490, "1.147-1.293"),
        (200, 4.943, 3.425, "1.133-1.268"),
        (250, 4.831, 3.341, "1.113-1.237"),
        (300, 4.741, 3.271, "1.096-1.212"),
    ]
    for index, row in enumerate(rows):
        page.insert_text((105, 120 + 30 * index), " ".join(map(str, row)), fontsize=10)
    page.insert_text((25, 150), "Harmonic", fontsize=10)
    page.insert_text((25, 270), "Anharmonic", fontsize=10)
    if borders:
        for y in [100, 195, 345]:
            page.draw_line((20, y), (550, y), width=0.8)
    path = tmp_path / "grouped.pdf"
    document.save(path)
    document.close()
    return path


def test_group_labels_centered_in_merged_rows_are_not_read_as_sequential_scope(tmp_path):
    records, issues = extract_lattice_observations(
        grouped_table(tmp_path), source={"file_id": "source", "filename": "s.pdf"}
    )
    assert not issues and len(records) == 8
    assert [r["calculation_label"] for r in records] == ["Harmonic"] * 3 + ["Anharmonic"] * 5
    assert [r["cell_parameters"]["a"] for r in records if r["pressure_value_gpa"] == 300] == [4.735, 4.741]
    assert all(r["coordinate_status"] == "not_reported" and r["retention"] == "pending" for r in records)
    assert len({r["record_key"] for r in records}) == 8


def test_unknown_group_boundaries_keep_observations_and_explicit_issues(tmp_path):
    records, issues = extract_lattice_observations(
        grouped_table(tmp_path, borders=False), source={"file_id": "source"}
    )
    assert len(records) == 8 and len(issues) == 8
    assert all(r["calculation_label"] is None for r in records)


def test_extraction_issues_survive_paper_roundtrip_but_are_never_public(client):
    client, session, paper, app = client
    candidate = geometry()
    candidate.update(status="blocked", retention="retained", representations={})
    candidate["validation"] = {"message": "缺少可验证坐标"}
    draft = dict(
        material_states=[],
        structure_candidates=[candidate],
        structural_observations=[],
        structural_extraction_issues=[dict(file_id="source", page=9, reason="表格列无法恢复")],
    )
    asyncio.run(service.persist(AsyncBridge(session), paper, draft))
    session.commit()
    rows = service.current_items(session, paper)
    assert rows == []
    assert client.post("/api/rag/structural-records/search", json={}).json()["total"] == 0
    original_keys = {r.record_key for r in rows}
    restored = service.supplement_draft(session, paper, dict(material_states=[], structure_candidates=[]))
    assert not restored.get('structural_extraction_issues')
    assert not restored.get('structure_candidates')
    assert client.post('/api/rag/structural-records/search', json={}).json()['total'] == 0



def test_reextract_is_owner_authorized_hash_verified_preview_only(client, tmp_path, monkeypatch):
    import pymupdf
    import hashlib
    from backend.ingest import upload_tasks

    client, session, paper, app = client
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (20, 30),
        "Table S1. Structural parameters at 50 GPa.\nAtomic coordinates (fractional)\nSi P1 a=3 b=3 c=3 alpha=90 beta=90 gamma=90\nSi (1a) 0 0 0",
        fontsize=9,
    )
    path = tmp_path / "source.pdf"
    document.save(path)
    document.close()
    state = dict(
        status="ready",
        user_id=1,
        files=[
            dict(
                file_id="source",
                role="main",
                original_filename="source.pdf",
                stored_path=str(path),
                size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        ],
    )
    draft = dict(material_states=[], structure_candidates=[])
    monkeypatch.setattr(upload_tasks, "get_state", lambda _: state)
    monkeypatch.setattr(upload_tasks, "get_draft", lambda _: draft)
    monkeypatch.setattr(upload_tasks, "save_draft", lambda *_: pytest.fail("预览不能写草稿"))
    before = len(service.current_items(session, paper))
    first = client.post("/api/rag/structural-records/reextract", json=dict(target="upload", target_id="task"))
    assert first.status_code == 200, first.text
    assert first.json()["model_calls"] == 0 and len(first.json()["structure_candidates"]) == 1
    assert len(service.current_items(session, paper)) == before and not draft["structure_candidates"]
    state["files"][0]["sha256"] = "0" * 64
    assert (
        client.post(
            "/api/rag/structural-records/reextract", json=dict(target="upload", target_id="task")
        ).status_code
        == 409
    )
    state["user_id"] = 99
    assert (
        client.post(
            "/api/rag/structural-records/reextract", json=dict(target="upload", target_id="task")
        ).status_code
        == 404
    )
