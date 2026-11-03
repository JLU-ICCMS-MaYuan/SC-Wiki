"""#209：真实MySQL回滚验证原样退回的来源版本与人工决定。"""
import hashlib
import os
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from fastapi import HTTPException

from backend import models
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.model_review import bind_result
from backend.services import manuscript_handoffs as handoffs, paper_revisions
from test_scientific_evidence_mysql import current_mysql

pytestmark = pytest.mark.skipif(os.environ.get("SCWIKI_CURRENT_MYSQL") != "1", reason="显式本机MySQL外层回滚")


@pytest.mark.parametrize("role", ["admin", "superadmin"])
def test_return_keeps_reviewed_condition_sources_and_decisions(current_mysql, tmp_path, monkeypatch, role):
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    with current_mysql.begin() as db:
        author = db.scalar(select(models.User).where(models.User.role == "user"))
        reviewer = db.scalar(select(models.User).where(models.User.role == role))
        paper = models.Paper(title="Isolated return source versions", year=2026, paper_type="theoretical",
                             theoretical_subtype="calculation",keywords_tags='["CaH6"]',
                             uploaded_by_user_id=author.id, review_status="pending", content_revision=1)
        db.add(paper); db.flush()
        state = models.MaterialState(paper_id=paper.id, paper_revision=1, state_key="source-state",
                                     material_name="CaH6", state_kind="theoretical", pressure_value_gpa=150,
                                     structure_optimization="classical_static")
        db.add(state); db.flush()
        module = models.PropertyModule(paper_id=paper.id, paper_revision=1, material_state_id=state.id,
                                       module_key="source-module", module_code="superconductive_properties")
        db.add(module); db.flush()
        definition = db.scalar(select(models.FormDefinition).where(
            models.FormDefinition.definition_key == "record.superconductive_properties.predicted_tc.isotropic_eliashberg"))
        record = models.PropertyRecord(paper_id=paper.id, paper_revision=1, material_state_id=state.id,
            module_id=module.id, record_key="source-record", record_type="predicted_tc", property_code="tc",
            definition_id=definition.id, definition_key=definition.definition_key, definition_version=definition.version,
            method_code="isotropic_eliashberg", name_raw="Tc", value_kind="number", value_number=235,
            value_raw="235 K", unit_raw="K", canonical_unit="K", source_fingerprint="a"*64, record_checksum="b"*64,
            payload_json={"parameters":{"mu_star":.1}, "calculation_conditions":{"calculation_code":"QUANTUM ESPRESSO",
                "qe":{"energy_cutoff":{"value_kind":"number","value_number":90,"value_raw":"90 Ry","unit_raw":"Ry"}}}})
        db.add(record)
        source = tmp_path / "source.txt"
        source.write_text("QE electron-phonon calculations use a kinetic energy cutoff of 90 Ry.")
        file = models.PaperFile(paper_id=paper.id, paper_revision=1, role="main", original_filename="source.txt",
            stored_path=str(source), size=source.stat().st_size, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        db.add(file); db.flush()
        chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=file.id,
                                  chunk_index=0, content=source.read_text())
        db.add(chunk); db.flush()
        quote = {"file_id":str(file.id),"chunk_id":chunk.id,"chunk_index":0,"quote":source.read_text()}
        provenance = {
            "paper.theoretical_subtype":{"assessment":{"value":"calculation","status":"completed","evidences":[quote]}},
            "paper.keywords_tags":{"assessment":{"values":["CaH6"],"status":"completed","kind":"author_list","evidences":[quote]}}}
        formal = ev.paper_snapshot(db, paper.id, reviewer.id, reviewer.role, review_provenance=provenance)
        cutoff = next(r for r in formal["records"] if r.get("record_field") == "payload.calculation_conditions.qe.energy_cutoff")
        quote = {"file_id":str(file.id),"chunk_id":chunk.id,"chunk_index":0,"quote":source.read_text()}
        quote["source_name"] = file.original_filename
        evidence=models.PaperEvidence(paper_id=paper.id,paper_revision=1,paper_chunk_id=chunk.id,
            field_path=cutoff["field"],quote=quote["quote"])
        db.add(evidence);db.flush()
        db.add(models.PropertyRecordEvidence(record_id=record.id,paper_evidence_id=evidence.id,
            paper_id=paper.id,paper_revision=1,field_path="payload.calculation_conditions.qe.energy_cutoff"))
        db.flush()
        formal=ev.paper_snapshot(db,paper.id,reviewer.id,reviewer.role,review_provenance=provenance)
        cutoff=next(r for r in formal["records"] if r.get("record_field")=="payload.calculation_conditions.qe.energy_cutoff")
        result = bind_result(cutoff, {"status":"supported","reason":"已核对当前QE阶段的90 Ry","evidences":[quote]}, formal["chunks"])
        transferred=science.transfer_result(cutoff,result,formal["chunks"],source_transfer_verified=True)
        assert transferred["evidences"][0].get("source_name")==file.original_filename
        result["field_decision"] = {"contract":"field-review-v2","action":"approve","actor_user_id":author.id,
            "content_hash":cutoff["content_hash"],"source_hash":cutoff["source_hash"]}
        seeded={cutoff["key"]:result}
        for row in formal["records"]:
            if row["field"] in provenance:
                seeded[row["key"]] = bind_result(row,{**row,"status":"supported","reason":"已核对归纳来源"},formal["chunks"])
        science.save_results(db, formal, seeded, author.id); db.flush()
        handoffs.record_handoff(db,paper,author,action="submit",holder="review",operation_id=uuid4().hex,
            initial=True,draft=paper_revisions.current_draft(db,paper),records=[{**cutoff,**result}])
        returned = handoffs.current_review_content(db,paper,reviewer)
        checked = next(r for r in returned["records"] if r["item_key"] == cutoff["item_key"])
        assert checked["status"] == "supported" and not checked.get("stale"), checked
        assert checked["source_hash"] == cutoff["source_hash"]
        assert checked["evidences"]
        handoffs.record_handoff(db,paper,reviewer,action="return",holder="author",
                               operation_id=uuid4().hex,**returned)
        paper.review_status = "rejected"; db.flush()
        saved = handoffs.author_working_copy(db,paper,author.id,returned["draft"],returned["records"])
        current = paper_revisions.revision_snapshot(db,saved.revision_id,author.id)
        loaded = science.load_results(db,current,author.id,include_stale=True)
        leaf = next(r for r in current["records"] if r["item_key"] == cutoff["item_key"])
        actual = loaded[leaf["key"]]
        assert actual["status"] == "supported" and not actual.get("stale")
        assert actual.get("field_decision",{}).get("action") == "approve"
        assert actual["evidences"][0]["quote"] == quote["quote"]
        for field in provenance:
            row=next(r for r in current["records"] if r["field"]==field)
            assert loaded[row["key"]]["status"]=="supported" and not loaded[row["key"]].get("stale"), field
        # 完整返修页先读轻量摘要；不能只在打开详情后才恢复人工通过。
        from backend.api import evidence as api
        monkeypatch.setattr(api, "SessionLocal", current_mysql)
        summary = api.field_summary(api.Target(target="revision", target_id=saved.revision_id), author)
        shown = next(r for r in summary["records"] if r["item_key"] == leaf["item_key"])
        assert shown["status"] == "supported" and not shown["pending_review"]
        assert shown["human_confirmed"]
        # 真实来源摘要变化仍使旧结果失效。
        file.sha256 = "c"*64; db.flush()
        with pytest.raises(HTTPException) as conflict:
            paper_revisions.revision_snapshot(db,saved.revision_id,author.id)
        assert conflict.value.detail["code"] == "revision_conflict"
        assert saved.draft is not None



def test_working_snapshot_keeps_synthesis_sources_but_not_changed_value_support():
    from backend.ingest.scientific_context import bind_snapshot_source_documents
    quote={"file_id":"main","chunk_index":0,"quote":"The paper predicts superconducting CaH6."}
    draft={"paper":{"theoretical_subtype":"calculation","keywords_tags":["CaH6"]},"material_states":[],
           "theoretical_subtype_assessment":{"value":"calculation","status":"completed","evidences":[quote]},
           "keyword_assessment":{"values":["CaH6"],"status":"completed","kind":"author_list","evidences":[quote]}}
    chunks=[{"file_id":"main","chunk_index":0,"content":quote["quote"]}]
    formal=ev.complete_snapshot("paper","209-test",ev.draft_records(draft,{}),chunks,draft)
    bind_snapshot_source_documents(formal,{"main":{"sha256":"a"*64,"role":"main"}},{"main"})
    working={"paper":deepcopy(draft["paper"]),"material_states":[]}
    current=ev.working_snapshot(formal,"revision","new-revision",working)
    for field in ("paper.theoretical_subtype","paper.keywords_tags"):
        old=next(r for r in formal["records"] if r["field"]==field)
        new=next(r for r in current["records"] if r["field"]==field)
        assert (old["content_hash"],old["source_hash"]) == (new["content_hash"],new["source_hash"])
        assert new["evidences"] == [quote]
    assert "keyword_assessment" not in working
    working["paper"]["keywords_tags"]=["CaH4"]
    changed=ev.working_snapshot(formal,"revision","new-revision",working)
    leaf=next(r for r in changed["records"] if r["field"]=="paper.keywords_tags")
    assert leaf["evidences"] == []
    assert "assessment" not in leaf.get("provenance",{})


def test_initial_handoff_preserves_pending_family_and_author_roles(current_mysql):
    from sqlalchemy import func
    with current_mysql.begin() as db:
        author=db.scalar(select(models.User).where(models.User.role=="user"))
        paper=models.Paper(title="Initial handoff metadata",year=2026,authors=["A","B"],
            uploaded_by_user_id=author.id,review_status="pending",content_revision=1)
        db.add(paper);db.flush()
        state=models.MaterialState(paper_id=paper.id,paper_revision=1,state_key="pending-family-state",
                                   material_name="CaH6",state_kind="theoretical")
        db.add(state);db.flush()
        family={"id":None,"name":"Unregistered source family "+uuid4().hex,"status":"pending","is_primary":False}
        submission={"paper":{"corresponding_authors":["B"],"co_first_authors":["A"],"material_families":[]},
                    "material_states":[{"state_key":state.state_key,"structure_families":[family]}]}
        count=db.scalar(select(func.count()).select_from(models.StructureFamily))
        snapshot=ev.paper_snapshot(db,paper.id,0,"",check_access=False,submission=submission)
        assert next(r for r in snapshot["records"] if r["field"]=="material_states[0].structure_families")["current_value"]==[family["name"]]
        draft=paper_revisions.current_draft(db,paper,submission=submission)
        assert draft["paper"]["corresponding_authors"]==["B"]
        assert draft["paper"]["co_first_authors"]==["A"]
        assert draft["material_states"][0]["structure_families"]==[family]
        handoffs.record_handoff(db,paper,author,action="submit",holder="review",initial=True,
            operation_id=uuid4().hex,draft=draft,records=snapshot["records"])
        restored=paper_revisions.current_draft(db,paper)
        assert restored["material_states"][0]["structure_families"]==[family]
        assert restored["paper"]["corresponding_authors"]==["B"]
        assert db.scalar(select(func.count()).select_from(models.StructureFamily))==count
