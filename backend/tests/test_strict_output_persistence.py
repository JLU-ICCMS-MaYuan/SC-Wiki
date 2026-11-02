"""#205：模型限制不堵住人工扩展，正式存取仍保留数值、空压力及来源。"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.database import Base
from backend.ingest.fixed_form_contract import payload_schema
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.scientific_drafts import persist_scientific_draft, add_scientific_evidence_link
from backend.ingest.upload_jobs import _normalize_draft
from backend.services.paper_revisions import current_draft


def roundtrip(states):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            seeds = json.loads((Path(__file__).parents[1] / "data/form_definitions.v1.json").read_text())
            seeds.append({"definition_key": "record.electronic_properties.dos_fermi", "version": 2,
                          "target_kind": "property_record", "module_code": "electronic_properties",
                          "record_type": "property", "property_code": "dos_fermi", "core_schema": {},
                          "json_schema": payload_schema(), "ui_schema": {}, "status": "published"})
            draft = _normalize_draft({"paper": {"title": "Isolated strict output", "paper_type": "theoretical"},
                                      "material_states": deepcopy(states)})
            async with sessions() as session, session.begin():
                for seed in seeds:
                    session.add(models.FormDefinition(**seed, checksum=definition_checksum(seed)))
                paper = models.Paper(id=1, title="Isolated strict output", year=2026,
                                     paper_type="theoretical", review_status="pending", content_revision=1)
                session.add(paper)
                await session.flush()
                targets = await persist_scientific_draft(session, paper, draft)
                # 与提交入口一样，实体保存后再保存原文块和来源链接；实体函数不负责上传文件。
                files = {}
                for index, target in enumerate(targets):
                    evidence = target.evidence
                    if not evidence.get("quote"):
                        continue
                    source_id = evidence.get("file_id", "source")
                    if source_id not in files:
                        file = models.PaperFile(paper_id=1, paper_revision=1, role="supplementary",
                            original_filename="isolated-source.pdf", stored_path=f"isolated/{len(files)}.pdf",
                            sha256="0" * 64, size=0, sort_order=len(files), media_type="application/pdf")
                        session.add(file)
                        await session.flush()
                        files[source_id] = file.id
                    page = evidence.get("pdf_page", evidence.get("page_start"))
                    chunk = models.PaperChunk(paper_id=1, paper_revision=1, paper_file_id=files[source_id],
                        chunk_index=index, content=evidence["quote"], page_start=page, page_end=page)
                    session.add(chunk)
                    await session.flush()
                    saved_evidence = models.PaperEvidence(paper_id=1, paper_revision=1, paper_chunk_id=chunk.id,
                        field_path=target.field_path, quote=evidence["quote"], page_start=page, page_end=page)
                    session.add(saved_evidence)
                    await session.flush()
                    add_scientific_evidence_link(session, target, saved_evidence)
            async with sessions() as session:
                paper = await session.get(models.Paper, 1)
                return await session.run_sync(lambda sync: current_draft(sync, paper))
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_manual_extension_survives_form_save_and_reopen():
    manual = {"field_key": "human-added", "name_raw": "人工附加参数", "value_kind": "number",
              "value_number": 2, "value_raw": "2", "unit_raw": "1", "origin": "human_input"}
    state = {"state_key": "s", "material": "CaH4", "material_name": "CaH4", "state_kind": "theoretical",
             "pressure_value_gpa": None, "property_modules": [{"module_key": "m", "module_code": "electronic_properties",
                 "definition_key": "module.electronic_properties", "definition_version": 1, "records": [{
                     "record_key": "r", "record_type": "property", "property_code": "dos_fermi",
                     "definition_key": "record.electronic_properties.dos_fermi", "definition_version": 2,
                     "name_raw": "DOS", "value_kind": "number", "value_number": .02234, "value_raw": "0.02234",
                     "unit_raw": "states/eV/f.u.", "canonical_unit": "states/eV/f.u.",
                     "payload": {"calculation_conditions": {"extensions": [manual]}},
                     "evidences": [{"file_id": "test-source", "pdf_page": 10,
                                    "quote": "Test fixture: DOS is 0.02234 states/eV/f.u."}]}]}]}
    restored = roundtrip([state])["material_states"][0]
    assert restored["pressure_value_gpa"] is None
    record = restored["property_modules"][0]["records"][0]
    assert float(record["value_number"]) == .02234
    assert record["payload"]["calculation_conditions"]["extensions"] == [manual]
    assert record["evidences"][0]["page_start"] == 10
    assert record["evidences"][0]["quote"].startswith("Test fixture:")
