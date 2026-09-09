"""#98：显式授权后在当前 MySQL 上重放真实草稿，所有测试写入最终回滚。"""
import asyncio
from copy import deepcopy
import hashlib
import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.api import rag


def test_cleaned_submitted_task_resolves_paper_for_owner_only(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from backend.api import upload_tasks as api
    from backend.ingest import upload_tasks
    from backend import database

    monkeypatch.setattr(upload_tasks, "get_state", lambda _: None)
    session = MagicMock()
    session.__enter__.return_value = session
    session.scalar.return_value = SimpleNamespace(id=29, uploaded_by_user_id=7)
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    for user, expected in [(SimpleNamespace(id=7, role="user", is_approved=True), 409),
                           (SimpleNamespace(id=8, role="user", is_approved=True), 404)]:
        with pytest.raises(HTTPException) as error:
            api.get_upload_task("a" * 32, touch=False, current_user=user)
        assert error.value.status_code == expected
        if expected == 409:
            assert error.value.detail["code"] == "UPLOAD_TASK_SUBMITTED"
            assert error.value.detail["paper_id"] == 29
        else:
            assert "paper_id" not in error.value.detail


def test_source_conflict_is_a_system_error_not_a_record_key_error():
    draft = {"material_states": [
        {"property_modules": [{"records": [{"record_key": "legacy-tc-0"}]}]},
        {"property_modules": [{"records": [{"record_key": "legacy-tc-0"}]}]},
    ]}
    error = rag._scientific_integrity_error(
        IntegrityError("INSERT secret", {}, RuntimeError("uq_property_records_source")), draft,
    )
    assert error.status_code == 409
    issue = error.detail["issues"][0]
    assert issue["code"] == "source_identity_conflict"
    assert issue["field"] == "material_states"
    assert "无需修改" in issue["message"]
    assert "uq_property_records_source" not in str(error.detail)
    assert "record_key" not in str(error.detail)
    assert "secret" not in str(error.detail)


def test_record_key_conflict_is_scoped_to_state_and_module():
    draft = {"material_states": [
        {"property_modules": [{"records": [{"record_key": "same"}]}]},
        {"property_modules": [{"records": [{"record_key": "same"}, {"record_key": "same"}]}]},
    ]}
    error = rag._scientific_integrity_error(
        IntegrityError(None, None, RuntimeError("uq_property_records_module_key")), draft,
    )
    assert error.detail["issues"][0]["field"] == "material_states[1].property_modules[0].records[1].record_key"


@pytest.mark.skipif(not os.getenv("SCWIKI_SUBMIT_TEST_TASK"), reason="须指定已授权的当前 MySQL 未提交任务")
def test_current_mysql_submit_edit_and_shared_evidence_roll_back(monkeypatch):
    from backend.ingest.property_modules import persist_property_modules
    from backend.ingest.form_definitions import definition_checksum, definition_payload, validate_definition_payload
    from backend.ingest.upload_contracts import convert_legacy_scientific_draft
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.ingest.upload_tasks import get_draft, get_state, upload_task_lock
    from backend.rag import database

    task_id = os.environ["SCWIKI_SUBMIT_TEST_TASK"]

    async def scenario():
        assert database.database_url.startswith("mysql+"), "仅使用当前 MySQL，不建立临时库"
        engine = create_async_engine(database.database_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    state, raw = get_state(task_id), get_draft(task_id)
                    assert state and raw, "需要仍存在的未提交草稿"
                    assert not await connection.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id))
                    factory = async_sessionmaker(
                        connection, expire_on_commit=False, join_transaction_mode="create_savepoint",
                    )
                    monkeypatch.setattr(database, "async_session_factory", factory)
                    paper_id = await rag._create_pending_paper(task_id, state, deepcopy(raw))
                    draft = _normalize_draft(convert_legacy_scientific_draft(raw))
                    async with factory() as session:
                        states = list((await session.scalars(select(models.MaterialState).where(
                            models.MaterialState.paper_id == paper_id,
                        ).order_by(models.MaterialState.id))).all())
                        records = list((await session.scalars(select(models.PropertyRecord).where(
                            models.PropertyRecord.paper_id == paper_id,
                        ))).all())
                        expected_count = sum(len(m.get("records", [])) for s in draft["material_states"] for m in s.get("property_modules", []))
                        assert len(records) == expected_count
                        assert len({r.source_fingerprint for r in records}) == expected_count
                        assert len(states) == len(draft["material_states"])
                        for db_state, source_state in zip(states, draft["material_states"]):
                            values = [r.value_raw for r in records if r.material_state_id == db_state.id]
                            assert sorted(values) == sorted(r["value_raw"] for m in source_state["property_modules"] for r in m["records"])

                        # 使用同一真实证据更新两个状态的记录，验证可共享证据和身份稳定。
                        evidence_id = await session.scalar(select(models.PaperEvidence.id).where(models.PaperEvidence.paper_id == paper_id))
                        assert evidence_id is not None
                        shared_record_ids = []
                        for db_state, source_state in list(zip(states, draft["material_states"]))[:2]:
                            modules = deepcopy(source_state["property_modules"])
                            original = next(r for r in records if r.material_state_id == db_state.id and r.record_key == modules[0]["records"][0]["record_key"])
                            fingerprint = original.source_fingerprint
                            modules[0]["records"][0]["evidences"] = [{"paper_evidence_id": evidence_id}]
                            result = await persist_property_modules(session, paper_id=paper_id, paper_revision=1, material_state_id=db_state.id, modules=modules)
                            assert result[0].id == original.id
                            assert result[0].source_fingerprint == fingerprint
                            shared_record_ids.append(original.id)
                        await session.flush()
                        assert await session.scalar(select(func.count()).select_from(models.PropertyRecordEvidence).where(
                            models.PropertyRecordEvidence.paper_evidence_id == evidence_id,
                            models.PropertyRecordEvidence.record_id.in_(shared_record_ids),
                        )) == 2

                        # 旧指纹保持不变；导出载荷不带指纹也不能重算身份。
                        legacy_record = next(r for r in records if r.id == shared_record_ids[0])
                        legacy_fingerprint = hashlib.sha256(legacy_record.record_key.encode()).hexdigest()
                        legacy_record.source_fingerprint = legacy_fingerprint
                        await session.flush()
                        edited = deepcopy(draft["material_states"][0]["property_modules"])
                        edited[0]["records"][0]["value_raw"] += " (edited)"
                        result = await persist_property_modules(session, paper_id=paper_id, paper_revision=1, material_state_id=states[0].id, modules=edited)
                        assert result[0].source_fingerprint == legacy_fingerprint
                        assert await session.scalar(select(func.count()).select_from(models.PropertyRecord).where(models.PropertyRecord.paper_id == paper_id)) == expected_count

                        # 同状态另一个模块也可以使用相同的局部记录键。
                        # 当前库只发布了超导模块自定义记录定义；测试定义也在外层事务内回滚。
                        source_definition = await session.scalar(select(models.FormDefinition).where(
                            models.FormDefinition.definition_key == "record.superconductive_properties.custom",
                            models.FormDefinition.version == 1,
                        ))
                        payload = definition_payload(source_definition)
                        payload.update(definition_key="record.electronic_properties.issue98_probe", module_code="electronic_properties")
                        validate_definition_payload(payload)
                        definition = models.FormDefinition(**payload, status="published", checksum=definition_checksum(payload))
                        session.add(definition)
                        await session.flush()
                        custom = {
                            "record_key": legacy_record.record_key, "record_type": "property",
                            "property_code": "custom", "custom_property_key": "issue98-probe",
                            "definition_key": definition.definition_key, "definition_version": definition.version,
                            "name_raw": "probe", "value_kind": "number", "value_raw": "1",
                            "value_number": 1, "payload": {},
                        }
                        module = {"module_key": "issue98-electronic", "module_code": "electronic_properties", "records": [custom]}
                        added = await persist_property_modules(session, paper_id=paper_id, paper_revision=1, material_state_id=states[0].id, modules=[module])
                        assert added[0].source_fingerprint not in {r.source_fingerprint for r in records}
                        custom["record_key"] = "issue98-explicit"
                        custom["source_fingerprint"] = "f" * 64
                        explicit = await persist_property_modules(session, paper_id=paper_id, paper_revision=1, material_state_id=states[0].id, modules=[module])
                        assert explicit[0].source_fingerprint == "f" * 64
                finally:
                    await transaction.rollback()
                assert not await connection.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id))
                assert get_draft(task_id) == raw
        finally:
            await engine.dispose()

    with upload_task_lock(task_id):
        asyncio.run(scenario())
