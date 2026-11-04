"""真实失败模块经正式 SQL 保存、重读、局部保存与版本混合读取。"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.database import Base
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.property_modules import persist_property_modules
from backend.ingest.tc_contexts import expand_module


def test_failed_paper_module_real_sql_roundtrip_and_partial_write(tmp_path):
    original = json.loads((Path(__file__).parents[1] / 'fixtures/issue189/method-alias-failure.json').read_text())['state']['property_modules'][0]

    async def run():
        engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path / 'isolated.sqlite'))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions.begin() as session:
            definitions = {}
            for record in original['records']:
                data = dict(definition_key=record['definition_key'], version=record['definition_version'],
                    target_kind='property_record', module_code='superconductive_properties',
                    record_type='predicted_tc', property_code='tc', method_code=record['method_code'],
                    core_schema={}, json_schema={}, ui_schema={})
                definitions[data['definition_key']] = data
            data = dict(definition_key=original['definition_key'], version=original['definition_version'],
                target_kind='property_module', module_code='superconductive_properties',
                record_type=None, property_code=None, method_code=None, core_schema={}, json_schema={}, ui_schema={})
            definitions[data['definition_key']] = data
            session.add_all([models.FormDefinition(**d, status='published', checksum=definition_checksum(d)) for d in definitions.values()])
            await session.flush()
            await persist_property_modules(session, paper_id=991, paper_revision=1, material_state_id=991, modules=[deepcopy(original)])
            from backend.ingest.scientific_evidence import persist_upload
            state = json.loads((Path(__file__).parents[1] / 'fixtures/issue189/method-alias-failure.json').read_text())['state']
            draft = {'paper': {}, 'material_states': [state]}
            await session.run_sync(lambda db: persist_upload(db, 'isolated-method-identity',
                {'user_id': 1, 'task_id': 'isolated-method-identity'}, draft))
        async with sessions() as session:
            from backend.ingest.tc_contexts import map_draft
            saved = await session.get(models.ScientificUploadDraft, 'isolated-method-identity')
            assert map_draft(saved.draft) == draft

        async def read():
            async with sessions() as session:
                module = (await session.scalars(select(models.PropertyModule))).one()
                rows = list(await session.scalars(select(models.PropertyRecord).order_by(models.PropertyRecord.id)))
                actual = expand_module({'metadata': module.metadata_json, 'records': [
                    {**deepcopy(original['records'][i]), 'method_code': row.method_code, 'method_raw': row.method_raw,
                     'payload': row.payload_json, 'value_number': row.value_number} for i, row in enumerate(rows)]})
                return actual, rows, module.metadata_json

        actual, rows, directory = await read()
        for before, after in zip(original['records'], actual['records']):
            assert after['method_raw'] == before['method_raw']
            assert after['method_code'] == before['method_code']
            assert after['payload'] == before['payload']
        # 旧 v1 引用与新 v2 写入并存时，未提交结果不能丢方法原文。
        async with sessions.begin() as session:
            module = (await session.scalars(select(models.PropertyModule))).one()
            stored_rows = list(await session.scalars(select(models.PropertyRecord).order_by(models.PropertyRecord.id)))
            metadata = deepcopy(module.metadata_json)
            record = stored_rows[1]
            group = record.payload_json['tc_group']
            metadata['tc_contexts']['methods'][group['group_key']][group['method_key']]['method_raw'] = record.method_raw
            payload = deepcopy(record.payload_json)
            payload['tc_context_ref']['version'] = 1
            payload['tc_context_ref'].pop('method_raw_owner', None)
            record.payload_json, record.method_raw = payload, None
            module.metadata_json = metadata
        async with sessions.begin() as session:
            incoming = deepcopy(original)
            incoming['records'] = incoming['records'][:1]
            incoming['records'][0]['value_number'] = 132
            await persist_property_modules(session, paper_id=991, paper_revision=1, material_state_id=991, modules=[incoming])
        after, _, _ = await read()
        assert after['records'][0]['value_number'] == 132
        assert after['records'][1]['method_raw'] == original['records'][1]['method_raw']
        assert after['records'][1]['payload'] == original['records'][1]['payload']
        await engine.dispose()
    asyncio.run(run())
