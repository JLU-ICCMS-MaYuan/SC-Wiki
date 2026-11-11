"""正式持久化交接只使用当前字段选定引用，原记录背景保留历史。"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from backend import models
from backend.database import Base
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.fixed_form_contract import payload_schema
from backend.ingest.reviewed_sources import apply_property_sources,source_reference,SourceReferenceError
from backend.ingest.submission_sources import reviewed_legacy_targets
from backend.ingest.scientific_drafts import ScientificEvidenceTarget,persist_scientific_draft,add_scientific_evidence_link

ROOT="material_states[0].property_modules[0].records[0]"
BACKGROUND={"file_id":"main","block_id":"retired-background","quote":"Old unselected candidate context."}
SELECTED={"file_id":"main","chunk_index":0,"block_id":"selected","quote":"The reviewed DOS was approximately 0.012."}
CHUNKS=[{"file_id":"main","chunk_index":0,"block_id":"selected","content":SELECTED["quote"],"page_start":4,"page_end":4}]

def checks():
    return [{"item_key":"reviewed-"+field,"record_key":"r","module_key":"m","state_key":"s","state_index":0,
      "kind":"field","field":ROOT+"."+field,"record_field":field,"status":"supported","evidences":[deepcopy(SELECTED)]}
      for field in ["name_raw","value_raw","value_number","unit_raw"]]

def test_unselected_record_background_is_historical_and_missing_current_source_still_blocks():
    rows=checks()
    selected=ScientificEvidenceTarget(ROOT+".value_number",deepcopy(SELECTED),"property_record",SimpleNamespace(record_key="r"))
    old=ScientificEvidenceTarget(ROOT,deepcopy(BACKGROUND),"property_record",SimpleNamespace(record_key="r"))
    effective=reviewed_legacy_targets([old,selected],rows,{},CHUNKS)
    assert effective==[selected]
    assert rows[0]["legacy_source_history"][0]["evidence"]==BACKGROUND
    assert all(r["evidences"]==[SELECTED]for r in rows)
    bad=deepcopy(selected);bad.evidence["chunk_index"]=99
    effective=reviewed_legacy_targets([old,bad],rows,{},CHUNKS)
    with pytest.raises(SourceReferenceError):source_reference(effective[-1].evidence,CHUNKS)

def test_no_owned_field_review_cannot_discard_record_background():
    old=ScientificEvidenceTarget(ROOT,deepcopy(BACKGROUND),"property_record",SimpleNamespace(record_key="other-record"))
    assert reviewed_legacy_targets([old],checks(),{},CHUNKS)==[old]


def test_dos_candidate_archive_is_preserved_without_becoming_current_selected_source():
    from backend.ingest.reviewed_sources import rebind_references
    archive = {"version": 1, "records": [{"evidences": [deepcopy(BACKGROUND)],
        "value_number": .03, "payload": {}}]}
    value = {"evidences": [deepcopy(SELECTED)],
        "claim": {"context": {"record": {"payload": {"dos_fermi_sources": archive}},
            "direct_inputs": {"payload.parameters.lambda_ep": {"value_number": 1.2, "evidences": [deepcopy(BACKGROUND)]}},
            "method_observations": [{"method_raw": "Eliashberg", "evidences": [deepcopy(BACKGROUND)]}]}}}
    formal = [{**c, "file_id": "42"} for c in CHUNKS]
    moved = rebind_references(value, formal, {"main": 42})
    assert moved["evidences"][0]["file_id"] == "42"
    assert moved["claim"]["context"]["record"]["payload"]["dos_fermi_sources"] == archive
    assert moved["claim"]["context"]["method_observations"] == value["claim"]["context"]["method_observations"]
    assert moved["claim"] == value["claim"]
    invalid = deepcopy(value); invalid["evidences"] = [deepcopy(BACKGROUND)]
    with pytest.raises(SourceReferenceError): rebind_references(invalid, formal, {"main": 42})

def test_real_persistence_source_selection_save_and_reread_preserve_every_field():
    async def run():
        engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        factory=async_sessionmaker(engine,expire_on_commit=False)
        try:
            async with engine.begin()as c:await c.run_sync(Base.metadata.create_all)
            seeds=json.loads((Path(__file__).parents[1]/"data/form_definitions.v1.json").read_text())
            seeds.append({"definition_key":"record.electronic_properties.dos_fermi","version":2,"target_kind":"property_record",
              "module_code":"electronic_properties","record_type":"property","property_code":"dos_fermi","core_schema":{},
              "json_schema":payload_schema(),"ui_schema":{},"status":"published"})
            record={"record_key":"r","module_code":"electronic_properties","record_type":"property","property_code":"dos_fermi",
              "definition_key":"record.electronic_properties.dos_fermi","definition_version":2,"name_raw":"DOS at EF",
              "value_kind":"number","value_raw":"~0.012","value_number":.012,"unit_raw":"states/(eV Å^3)","payload":{},"evidences":[deepcopy(BACKGROUND)]}
            draft={"material_states":[{"state_key":"s","material":"H","state_kind":"theoretical","pressure_value_gpa":10,
              "property_modules":[{"module_key":"m","module_code":"electronic_properties","definition_key":"module.electronic_properties",
               "definition_version":1,"records":[record]}]}]}
            rows=checks();apply_property_sources(draft,rows)
            async with factory()as db,db.begin():
                for seed in seeds:db.add(models.FormDefinition(**seed,checksum=definition_checksum(seed)))
                paper=models.Paper(id=1,title="Isolated source handoff",year=2026,content_revision=1,review_status="pending")
                db.add(paper);await db.flush()
                targets=await persist_scientific_draft(db,paper,draft)
                effective=reviewed_legacy_targets(targets,rows,draft,CHUNKS)
                assert len(effective)==4
                assert {t.field_path for t in effective}=={r["field"]for r in rows}
                file=models.PaperFile(paper_id=1,paper_revision=1,role="main",original_filename="source.pdf",
                  stored_path="isolated/source.pdf",sha256="a"*64,size=0,sort_order=0)
                db.add(file);await db.flush()
                chunk=models.PaperChunk(paper_id=1,paper_revision=1,paper_file_id=file.id,chunk_index=0,
                  content=CHUNKS[0]["content"],page_start=4,page_end=4)
                db.add(chunk);await db.flush()
                for target in effective:
                    selected=source_reference(target.evidence,CHUNKS)
                    e=models.PaperEvidence(paper_id=1,paper_revision=1,paper_chunk_id=chunk.id,field_path=target.field_path,
                      quote=selected["quote"],page_start=4,page_end=4)
                    db.add(e);await db.flush();add_scientific_evidence_link(db,target,e)
            async with factory()as db:
                rec=(await db.scalars(select(models.PropertyRecord))).one()
                evidences=(await db.scalars(select(models.PaperEvidence))).all()
                links=(await db.scalars(select(models.PropertyRecordEvidence))).all()
                assert float(rec.value_number)==.012 and rec.value_raw=="~0.012"
                assert len(links)==4 and {e.field_path for e in evidences}=={r["field"]for r in rows}
                assert all(e.quote==SELECTED["quote"]for e in evidences)
        finally:await engine.dispose()
    asyncio.run(run())


def test_selected_method_sources_do_not_change_scientific_content_during_handoff():
    from backend.ingest.property_evidence import complete_snapshot, draft_records
    from backend.ingest import scientific_evidence as science
    record = {"record_key": "point", "module_code": "superconductive_properties",
        "record_type": "predicted_tc", "property_code": "tc", "definition_key": "record.superconductive_properties.predicted_tc.other",
        "definition_version": 2, "method_code": "other", "method_raw": "Eliashberg equation",
        "value_kind": "number", "value_number": 0, "unit_raw": "K",
        "payload": {"tc_group": {"group_key": "g", "method_key": "method"}, "parameters": {"mu_star": .1}}}
    draft = {"material_states": [{"state_key": "s", "material": "H", "state_kind": "theoretical", "pressure_value_gpa": 100,
        "property_modules": [{"module_key": "m", "module_code": "superconductive_properties", "records": [record]}]}]}
    def snapshot(value, chunks):
        return complete_snapshot("upload", "task", draft_records(value, {}), chunks, value)
    original = next(r for r in snapshot(draft, CHUNKS)["records"] if r.get("record_field") == "method_code")
    checked = {**original, "status": "supported", "evidences": [deepcopy(SELECTED)]}
    checked["field_decision"] = {"contract": "field-review-v2", "action": "approve", "actor_user_id": 2,
        "content_hash": original["content_hash"], "source_hash": original["source_hash"]}
    changed = deepcopy(draft)
    apply_property_sources(changed, [checked])
    formal_chunks = [{**c, "file_id": "42"} for c in CHUNKS]
    formal = next(r for r in snapshot(changed, formal_chunks)["records"] if r.get("record_field") == "method_code")
    moved = science.transfer_result(formal, checked, formal_chunks, {"main": 42}, source_transfer_verified=True)
    assert moved["status"] == "supported"
    from backend.ingest.field_review import valid_field_decision
    assert valid_field_decision(formal, moved, "approve")
    assert moved["evidences"][0]["file_id"] == "42"
    assert science.transfer_result(formal, checked, formal_chunks, {"main": 42})["status"] == "unchecked"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.ingest import manual_evidence as manual
    from backend.manual_evidence_models import ScientificManualEvidence
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    before = {"target": "upload", "target_id": "task", "records": [original], "chunks": CHUNKS}
    after = {"target": "paper", "target_id": "1", "records": [formal], "chunks": formal_chunks}
    try:
        with Session(engine) as db:
            saved = manual.save_explanation(db, before, before, original["item_key"], 2,
                reason="原文只写 Eliashberg equation，保留其他方法及具体名称", no_evidence_reason="",
                text_items=[{"text": "Original method statement", "source_description": "原文"}])
            with pytest.raises(manual.ManualEvidenceError, match="正式字段已变化"):
                manual.transfer_to_paper(db, before, before, 1, 1, after)
            manual.transfer_to_paper(db, before, before, 1, 1, after, source_transfer_verified=True)
            db.commit()
        with Session(engine) as db:
            row = db.get(ScientificManualEvidence, saved["id"])
            assert (row.target, row.paper_id, row.value_hash) == ("paper", 1, formal["content_hash"])
            assert row.reason == saved["reason"] and row.items[0]["text"] == "Original method statement"
    finally:
        engine.dispose()
    for field, value in [("method_raw", "Allen-Dynes"), ("method_code", "allen_dynes")]:
        different = deepcopy(changed)
        different["material_states"][0]["property_modules"][0]["records"][0][field] = value
        row = next(r for r in snapshot(different, formal_chunks)["records"] if r.get("record_field") == "method_code")
        assert science.transfer_result(row, checked, formal_chunks, {"main": 42}, source_transfer_verified=True)["status"] == "unchecked"
