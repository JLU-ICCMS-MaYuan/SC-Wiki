import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.database import Base
from backend.ingest.fermi_dos import ARCHIVE_KEY, has_conflict, normalize_records
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.property_modules import PropertyValidationError, normalize_module, persist_property_modules, validate_record
from backend.ingest.upload_contracts import convert_legacy_state


def record(key="dos", raw="18.76", **patch):
    return dict(record_key=key, module_code="electronic_properties", record_type="property",
                property_code="dos_fermi", definition_key="record.electronic_properties.dos_fermi",
                definition_version=1, name_raw="N(Ef)", value_kind="text", value_raw=raw,
                value_text=raw, unit_raw="states/spin/Ry/f.u.", payload={},
                evidences=[{"file_id": "main", "chunk_index": 0, "page_start": 4, "quote": "DOS test fixture"}],
                **patch)


def module(records):
    return dict(module_key="electronic", module_code="electronic_properties",
                definition_key="module.electronic_properties", definition_version=1, records=records)


def test_identical_copies_keep_one_identity_and_all_original_records_without_mutation():
    original = [record(), record("copy-1"), record("copy-2")]
    original[1]["evidences"][0]["page_start"] = 5
    before = deepcopy(original)
    result = normalize_records(original)
    assert len(result) == 1 and result[0]["record_key"] == "dos" and result[0]["value_raw"] == "18.76"
    assert result[0]["payload"][ARCHIVE_KEY]["records"] == original
    assert len(result[0]["evidences"]) == 2
    assert not has_conflict(result[0]) and original == before
    assert normalize_records(result) == result


def test_conflicting_reports_do_not_choose_first_and_manual_value_survives_normalization():
    result = normalize_records([record(), record("second", "19.10")])
    assert result[0]["value_raw"] == result[0]["value_text"] == "" and has_conflict(result[0])
    validate_record(result[0])  # 未决定的当前值可以留在草稿，正式持久化另行拒绝。
    result[0].update(value_raw="18.80", value_text="18.80")
    assert normalize_records(result)[0]["value_raw"] == "18.80"
    assert has_conflict(result[0])


@pytest.mark.parametrize("patch", [
    {"unit_raw": "states/eV/f.u."},
    {"payload": {"calculation_conditions": {"k_grid": "24 24 24"}}},
])
def test_different_units_and_conditions_are_not_silently_equated(patch):
    second = record("second")
    second.update(patch)
    assert has_conflict(normalize_records([record(), second])[0])


def test_invalid_archive_cannot_bypass_empty_value_validation():
    bad = record()
    bad.update(value_raw="", value_text="")
    bad["payload"][ARCHIVE_KEY] = {"version": 99, "records": []}
    with pytest.raises(PropertyValidationError) as error:
        validate_record(bad)
    assert any(issue.code == "invalid_dos_sources" for issue in error.value.issues)


def test_database_defaults_and_ids_do_not_create_a_false_conflict():
    source = record("copy")
    source.update(id=17, paper_id=2, value_number=None, canonical_unit=None,
                  is_representative=False, method_code=None, uncertainty=None)
    assert not has_conflict(normalize_records([record(), source])[0])


def test_evidence_snapshot_marks_conflict_and_model_cannot_approve_it_alone():
    from backend.ingest import property_evidence as evidence
    from backend.ingest.scientific_evidence import record_claim
    dos = normalize_records([record(), record("second", "19.10")])[0]
    row = dict(key="dos", field="material_states[0].property_modules[0].records[0]",
               kind="property", module_code="electronic_properties",
               claim=record_claim(dos, {"material": "LaSc2H24", "pressure_value_gpa": 167}))
    chunks = [dict(file_id="main", chunk_index=0, content="DOS test fixture", page_start=4)]
    snapshot = evidence.complete_snapshot("upload", "fixture", [row], chunks, {})
    item = snapshot["records"][0]
    assert item["dos_fermi_conflict"]
    checked = evidence.checked_result(item, {"status": "supported", "reason": "测试支持",
        "evidences": [{"file_id": "main", "quote": "DOS test fixture"}]}, chunks)
    assert checked["status"] == "uncertain" and "不同 DOS 数值" in checked["reason"]
    changed = deepcopy(dos)
    changed["payload"][ARCHIVE_KEY]["records"][0]["evidences"][0]["quote"] = "Changed source fixture"
    next_row = dict(key="dos", field=row["field"], kind="property", module_code="electronic_properties",
                    claim=record_claim(changed, {"material": "LaSc2H24", "pressure_value_gpa": 167}))
    next_snapshot = evidence.complete_snapshot("upload", "fixture", [next_row], chunks, {})
    assert next_snapshot["records"][0]["content_hash"] == item["content_hash"]
    assert next_snapshot["records"][0]["source_hash"] != item["source_hash"]
    assert next_snapshot["version"] != snapshot["version"]


def test_each_material_state_is_normalized_independently_and_raw_sources_round_trip():
    a = convert_legacy_state({"material": "LaSc2H24", "property_modules": [module([record(), record("copy")])]})
    b = convert_legacy_state({"material": "LaSc2H24", "property_modules": [module([record(raw="18.44")])]})
    assert len(a["property_modules"][0]["records"]) == 1
    assert b["property_modules"][0]["records"][0]["value_raw"] == "18.44"
    assert normalize_module(a["property_modules"][0], paper_id=1, paper_revision=1)["records"][0]["payload"] == a["property_modules"][0]["records"][0]["payload"]


def test_real_sqlite_persistence_keeps_sources_and_rejects_second_current_value():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            for target, key in [("property_module", "module.electronic_properties"),
                                ("property_record", "record.electronic_properties.dos_fermi")]:
                data = dict(definition_key=key, version=1, target_kind=target, module_code="electronic_properties",
                            record_type="property" if target == "property_record" else None,
                            property_code="dos_fermi" if target == "property_record" else None, method_code=None,
                            core_schema={}, json_schema={"type": "object", "additionalProperties": True}, ui_schema={})
                session.add(models.FormDefinition(**data, checksum=definition_checksum(data), status="published"))
            await session.flush()
            async def save(records):
                return await persist_property_modules(session, paper_id=1, paper_revision=1,
                                                      material_state_id=10, modules=[module(records)])
            saved = await save([record(), record("copy")])
            await session.flush()
            session.expire_all()
            rows = list((await session.execute(select(models.PropertyRecord))).scalars())
            assert len(rows) == 1
            assert len(rows[0].payload_json[ARCHIVE_KEY]["records"]) == 2
            with pytest.raises(PropertyValidationError) as error:
                await save([record("another")])
            assert error.value.issues[0].code == "duplicate_dos_fermi"
            conflict = normalize_records([record(), record("second", "19.10")])
            with pytest.raises(PropertyValidationError) as error:
                await save(conflict)
            assert error.value.issues[0].code == "dos_value_required"
            conflict[0].update(value_raw="19.10", value_text="19.10")
            await save(conflict)
            await session.flush()
            stored = (await session.execute(select(models.PropertyRecord))).scalar_one()
            assert stored.value_raw == "19.10"
            assert has_conflict({**conflict[0], "payload": stored.payload_json})
            assert len((await session.execute(select(models.PropertyRecord))).scalars().all()) == 1
        await engine.dispose()
    asyncio.run(scenario())
