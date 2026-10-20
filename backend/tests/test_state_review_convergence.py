"""已确认的优化分支、字段直接依赖及完整结构收录合同。"""

import copy
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "isolated-tests-only")
from backend.ingest.state_optimization import assemble_candidates, resolve_candidates
from backend.ingest.review_dependencies import record_inputs, state_inputs
from backend.ingest.property_field_review import review_context
from backend.ingest.scientific_evidence import record_claim
from backend.ingest.association_review import bind_field, snapshot_association
from backend.services.structural_records import draft_items


def state(optimization, tc, approximation="unknown", material="MgH2"):
    return dict(
        material=material,
        scope="current_paper",
        pressure_value_gpa=300,
        reported_space_group_symbol="P6/mmm",
        state_kind="theoretical",
        structure_optimization=optimization,
        evidences=[{"quote": f"{approximation} {tc} K at 300 GPa"}],
        property_modules=[
            dict(
                module_code="superconductive_properties",
                module_key="sc",
                records=[
                    dict(
                        record_key=str(tc),
                        module_code="superconductive_properties",
                        record_type="predicted_tc",
                        property_code="tc",
                        method_code="isotropic_eliashberg",
                        name_raw="Tc",
                        value_kind="number",
                        value_number=tc,
                        value_raw=str(tc),
                        unit_raw="K",
                        payload={
                            "approximation": approximation,
                            "parameters": {"mu_star": 0.1, "lambda_ep": 2, "omega_log": 900},
                            "calculation_conditions": {
                                "calculation_code": "QE",
                                "k_grid": "12 12 12",
                                "extensions": [
                                    {"key": "structural_relaxation.energy_cutoff", "value_number": 500}
                                ],
                            },
                        },
                        evidences=[{"quote": str(tc)}],
                    )
                ],
            )
        ],
    )


def test_distinct_optimization_not_collapsed_for_another_material():
    a, b = state("classical_static", 300, "harmonic"), state("sscha", 320, "anharmonic")
    result = assemble_candidates([{"material_states": [a, b]}])
    assert len(result) == 2
    assert {s["structure_optimization"] for s in result} == {"classical_static", "sscha"}
    assert {s["property_modules"][0]["records"][0]["value_number"] for s in result} == {300, 320}
    assert len(assemble_candidates([{"material_states": [a, copy.deepcopy(a)]}])) == 1


def test_unknown_distinct_table_groups_not_collapsed_or_assumed_sscha():
    result = assemble_candidates(
        [{"material_states": [state("unknown", 300, "harmonic"), state("unknown", 320, "anharmonic")]}]
    )
    assert len(result) == 2 and all(s.get("structure_optimization") == "unknown" for s in result)


def test_anharmonic_phonons_do_not_prove_sscha_structure():
    candidate = {"material_states": [state("unknown", 320, "anharmonic")]}
    source = {"file_id": "source", "content": "MgH2 anharmonic phonons were calculated with SSCHA."}

    def model(*_):
        return {
            "assignments": [
                {
                    "target": "0/0",
                    "optimization": "sscha",
                    "approximation": "anharmonic",
                    "evidences": [{"source_index": 0, "quote": source["content"]}],
                }
            ]
        }

    result, issues = resolve_candidates([candidate], [source], model)
    assert result[0]["material_states"][0]["structure_optimization"] == "unknown"
    assert issues and "只有声子" in issues[0]["message"]


def test_exact_structural_workflow_can_populate_the_state():
    candidate = {"material_states": [state("unknown", 320, "anharmonic")]}
    source = {"file_id": "source", "content": "MgH2 structural relaxation used the SSCHA method."}

    def model(*_):
        return {
            "assignments": [
                {
                    "target": "0/0",
                    "optimization": "sscha",
                    "approximation": "anharmonic",
                    "evidences": [{"source_index": 0, "quote": source["content"]}],
                }
            ]
        }

    result, issues = resolve_candidates([candidate], [source], model)
    assert not issues and result[0]["material_states"][0]["structure_optimization"] == "sscha"
    assert (
        result[0]["material_states"][0]["field_evidence"]["structure_optimization"][0]["quote"]
        == source["content"]
    )


def test_nuclear_edit_does_not_invalidate_values_conditions_or_stage_associations():
    a = state("classical_static", 300)
    b = {**a, "structure_optimization": "sscha"}
    r = a["property_modules"][0]["records"][0]
    for path in [
        "value_number",
        "method_code",
        "payload.parameters.lambda_ep",
        "payload.calculation_conditions.k_grid",
    ]:
        assert review_context(r, a, path) == review_context(r, b, path)
    assert record_claim(r, a) == record_claim(r, b)
    association = {
        "stage": "electron_phonon",
        "target_path": "/payload/calculation_conditions/k_grid",
        "scope": {"material": "MgH2"},
    }
    bind_field(r, a, association)
    assert not snapshot_association(r, b, association)["stale"]
    r["payload"]["calculation_conditions"]["calculation_code"] = "VASP"
    assert snapshot_association(r, b, association)["stale"]


def test_direct_dependency_matrix_keeps_pairing_and_excludes_unrelated_settings():
    s = state("sscha", 300)
    r = s["property_modules"][0]["records"][0]
    assert "structure_optimization" not in state_inputs(s)
    assert "payload.parameters.mu_star" in record_inputs(r, "value_number")
    assert "value_number" in record_inputs(r, "payload.parameters.mu_star")
    assert "payload.calculation_conditions" not in record_inputs(r, "value_number")
    assert "payload.calculation_conditions.extensions.0" not in record_inputs(
        r, "payload.parameters.lambda_ep"
    )
    assert "payload.calculation_conditions.calculation_code" in record_inputs(
        r, "payload.calculation_conditions.k_grid"
    )


def test_incomplete_geometry_is_not_a_structural_record_even_for_old_clients():
    assert (
        draft_items(
            {
                "structural_observations": [{"record_key": "old-s2", "material": "MgH2"}],
                "structural_extraction_issues": [{"reason": "missing coordinates"}],
                "structure_candidates": [
                    {"candidate_id": "failed", "status": "blocked", "retention": "pending"}
                ],
            }
        )
        == []
    )


def test_legacy_stage_binding_replays_only_when_actual_inputs_match():
    from backend.ingest.association_review import _legacy_field_binding

    a = state("unknown", 300)
    b = {**a, "structure_optimization": "sscha"}
    r = a["property_modules"][0]["records"][0]
    association = {
        "stage": "electron_phonon",
        "target_path": "/payload/calculation_conditions/k_grid",
        "scope": {"material": "MgH2"},
    }
    association["field_binding"] = _legacy_field_binding(r, a, association)
    assert not snapshot_association(r, b, association)["stale"]
    changed = copy.deepcopy(r)
    changed["payload"]["calculation_conditions"]["k_grid"] = "24 24 24"
    assert snapshot_association(changed, b, association)["stale"]


def test_real_mysql_check_cache_and_revision_survive_nuclear_only_edit():
    import pytest, uuid

    if os.environ.get("SCWIKI_CONVERGENCE_MYSQL") != "1":
        pytest.skip("显式本机MySQL外事务回滚验证")
    from scripts.local_deploy.config import read_config
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend import models
    from backend.ingest import scientific_evidence as science, property_evidence as ev

    engine = create_engine(
        read_config(Path(os.environ.get("SCWIKI_CONVERGENCE_ROOT", str(Path.cwd()))))["DATABASE_URL"]
    )
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as db:
                user = models.User(
                    username="test" + uuid.uuid4().hex[:10],
                    email=uuid.uuid4().hex + "@isolated.test",
                    real_name="隔离核验",
                    password_hash="unused",
                    is_approved=True,
                )
                db.add(user)
                db.flush()
                uid = user.id
                task = uuid.uuid4().hex
                s = state("classical_static", 300)
                s["state_key"] = "stable-state"
                draft = {"paper": {}, "material_states": [s]}
                science.persist_upload(db, task, {"user_id": uid}, draft)
                snap = ev.complete_snapshot("upload", task, ev.draft_records(draft, {}), [], draft)
                target = next(
                    r
                    for r in snap["records"]
                    if r.get("record_field") == "payload.calculation_conditions.k_grid"
                )
                science.save_results(
                    db,
                    snap,
                    {target["key"]: {"status": "supported", "reason": "保留的核验", "evidences": []}},
                    uid,
                )
                db.commit()
            with Session(connection, join_transaction_mode="create_savepoint") as db:
                current = db.get(models.ScientificUploadDraft, task).draft
                current["material_states"][0]["structure_optimization"] = "sscha"
                science.persist_upload(db, task, {"user_id": uid}, current)
                after = ev.complete_snapshot("upload", task, ev.draft_records(current, {}), [], current)
                leaf = next(
                    r
                    for r in after["records"]
                    if r.get("record_field") == "payload.calculation_conditions.k_grid"
                )
                assert leaf["content_hash"] == target["content_hash"]
                assert science.load_results(db, after, uid)[leaf["key"]]["status"] == "supported"
                db.commit()
        finally:
            outer.rollback()
            engine.dispose()


# 正式返修API合同使用专用隔离库；不把浏览器路由适配当作服务端返修保存。
from backend.tests.test_paper_revisions import workflow


def test_formal_revision_api_preserves_direct_dependency_checks(workflow):
    from backend.tests.test_paper_revisions import begin
    from backend.ingest import scientific_evidence as science
    from backend.services.paper_revisions import revision_snapshot

    w = workflow
    opened = begin(w)
    draft = copy.deepcopy(opened["data"])
    item = state("classical_static", 300)
    item["state_key"] = "revision-scientific-state"
    item["property_modules"][0].update(
        definition_key="module.superconductive_properties", definition_version=1
    )
    item["property_modules"][0]["records"][0].update(
        definition_key="record.superconductive_properties.predicted_tc.isotropic_eliashberg",
        definition_version=1,
    )
    draft["material_states"] = [item]
    result = w.client.put(
        w.base,
        json={"revision_id": opened["revision_id"], "draft_version": opened["draft_version"], "draft": draft},
    )
    assert result.status_code == 200, result.text
    saved = result.json()
    with w.factory.begin() as db:
        snapshot = revision_snapshot(db, saved["revision_id"], w.owner.id)
        record = next(
            r for r in snapshot["records"] if r.get("record_field") == "payload.calculation_conditions.k_grid"
        )
        science.save_results(
            db,
            snapshot,
            {record["key"]: {"status": "supported", "reason": "隔离缓存核验", "evidences": []}},
            w.owner.id,
        )
    modified = copy.deepcopy(saved["data"])
    modified["material_states"][0]["structure_optimization"] = "sscha"
    response = w.client.put(
        w.base,
        json={
            "revision_id": saved["revision_id"],
            "draft_version": saved["draft_version"],
            "draft": modified,
        },
    )
    assert response.status_code == 200, response.text
    assert w.client.get(w.base).json()["data"]["material_states"][0]["structure_optimization"] == "sscha"
    with w.factory() as db:
        current = revision_snapshot(db, saved["revision_id"], w.owner.id)
        leaf = next(
            r for r in current["records"] if r.get("record_field") == "payload.calculation_conditions.k_grid"
        )
        assert leaf["content_hash"] == record["content_hash"]
        assert science.load_results(db, current, w.owner.id)[leaf["key"]]["status"] == "supported"
        assert db.get(w.models.Paper, w.paper.id).content_revision == 1


def test_missing_pressure_is_still_a_declared_input_when_later_filled():
    from backend.ingest.review_dependencies import state_paths

    assert "pressure_value_gpa" in state_paths()
    s = state("sscha", 300)
    r = s["property_modules"][0]["records"][0]
    assert record_inputs(r, "payload.calculation_conditions.calculation_code") == []


def test_software_source_binding_does_not_read_a_different_setting():
    s = state("sscha", 300)
    record = s["property_modules"][0]["records"][0]
    a = {
        "stage": "electron_phonon",
        "target_path": "/payload/calculation_conditions/calculation_code",
        "scope": {"material": "MgH2"},
    }
    bind_field(record, s, a)
    record["payload"]["calculation_conditions"]["exchange_correlation_functional"] = "PBE"
    assert not snapshot_association(record, s, a)["stale"]
