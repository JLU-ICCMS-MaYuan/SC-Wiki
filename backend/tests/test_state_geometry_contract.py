"""#94：真实持久化/返修/导出及契约约束；只连接显式指定的隔离测试库。"""
import asyncio
import copy
import os
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.engine import make_url
from backend import models
from backend.ingest.material_state_contract import state_metadata, validate_single_geometries
from backend.ingest.upload_contracts import convert_legacy_scientific_draft, UploadContractError
from backend.ingest.scientific_drafts import persist_scientific_draft, material_state_values
from backend.services.paper_revisions import current_draft
from backend.api.material_state_export import build_material_state_export
from backend.tests.test_structure_candidates import POSCAR
from backend.services.structure_candidates import build_structure_candidate


@pytest.mark.parametrize('state', [
    {'state_kind': 'mixed'}, {'state_kind': 'other'},
    {'state_kind': 'experimental', 'structure_optimization': 'sscha'},
    {'state_kind': 'theoretical', 'structure_optimization': 'harmonic'},
])
def test_invalid_state_rejected_in_read_write_and_comparison(state):
    with pytest.raises(UploadContractError):
        convert_legacy_scientific_draft({'material_states': [state]})
    with pytest.raises(ValueError):
        material_state_values(state)


def test_single_geometry_counts_candidates_and_direct_structures():
    candidate = dict(material_state_ref='material_states[0]', status='confirmed', confirmation='confirmed')
    draft = {'material_states': [{}], 'structure_candidates': [candidate]}
    validate_single_geometries(draft)
    draft['structure_candidates'].append(copy.deepcopy(candidate))
    with pytest.raises(ValueError, match='分别建卡'):
        convert_legacy_scientific_draft(draft)
    draft['structure_candidates'].pop()
    draft['material_states'][0]['structure'] = {'structure_text': POSCAR}
    with pytest.raises(ValueError, match='分别建卡'):
        validate_single_geometries(draft)


def test_real_mysql_persistence_revision_export_and_constraints():
    url = os.environ.get('STATE_GEOMETRY_TEST_URL')
    if not url:
        pytest.skip('需显式隔离 MySQL 测试库')
    assert 'test' in make_url(url).database.lower()

    async def run():
        engine = create_async_engine(url.replace('mysql+pymysql:', 'mysql+asyncmy:'))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session:
                paper = models.Paper(title='State geometry contract', year=2026, review_status='pending', content_revision=1)
                session.add(paper)
                await session.flush()
                paper_id = paper.id
                candidate = build_structure_candidate(structure_format='poscar', structure_text=POSCAR, source={'filename': 'Si.POSCAR'}, material_state_ref='material_states[0]')
                candidate.update(status='confirmed', confirmation='confirmed')
                state = dict(state_key='si', material='Si', state_kind='theoretical', structure_optimization='sscha', property_modules=[])
                draft = convert_legacy_scientific_draft({'material_states': [state], 'structure_candidates': [candidate]})
                await persist_scientific_draft(session, paper, draft)
                await session.commit()
            async with sessions() as session:
                state = (await session.scalars(select(models.MaterialState).where(models.MaterialState.paper_id == paper_id))).one()
                structure = (await session.scalars(select(models.StructureModel).where(models.StructureModel.material_state_id == state.id))).one()
                assert state.structure_optimization == 'sscha'
                assert structure.nuclear_treatment == 'anharmonic_quantum'
                assert structure.structure_format == 'cif'
                paper = await session.get(models.Paper, paper_id)
                loaded = await session.run_sync(lambda db: current_draft(db, paper))
                assert loaded['material_states'][0]['structure_optimization'] == 'sscha'
                assert len(loaded['structure_candidates']) == 1
                validate_single_geometries(loaded)
                exported = await session.run_sync(lambda db: build_material_state_export(db, paper_id=paper_id, state_key='si', user=models.User(role='admin')))
                assert exported['material_state']['structure_optimization'] == 'sscha'
                assert len(exported['material_state']['structures']) == 1
                from backend.spectra.contracts import state_signature
                before = state_signature(loaded['material_states'][0])
                changed = {**loaded['material_states'][0], 'structure_optimization': 'classical_static'}
                assert state_signature(changed) != before
                assert material_state_values(changed) != material_state_values(loaded['material_states'][0])
                # 重建结构后恢复来源时，旧元数据不能覆盖人工更改的核处理。
                from backend.services.scientific_graph_preservation import snapshot_structures, preserve_structure_metadata
                originals = await snapshot_structures(session, paper_id)
                structure.nuclear_treatment = 'classical_static'
                state.structure_optimization = 'classical_static'
                loaded['material_states'][0]['structure_optimization'] = 'classical_static'
                await preserve_structure_metadata(session, paper, loaded, originals, [])
                assert structure.nuclear_treatment == 'classical_static'
                await session.commit()
            # 使用数据库直接写绕过 Python，确认 CHECK / 唯一约束生效。
            async with sessions() as session:
                for sql in (
                    "UPDATE material_states SET state_kind='mixed' WHERE id=:id",
                    "UPDATE material_states SET state_kind='experimental',structure_optimization='sscha' WHERE id=:id",
                    "INSERT INTO structure_models (paper_id,paper_revision,material_state_id,structure_format,structure_text,structure_hash,nuclear_treatment) SELECT paper_id,paper_revision,material_state_id,structure_format,structure_text,structure_hash,nuclear_treatment FROM structure_models WHERE material_state_id=:id",
                ):
                    with pytest.raises(DBAPIError) as rejected:
                        await session.execute(text(sql), {'id': state.id})
                    assert rejected.value.orig.args[0] in {3819, 1062}
                    await session.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_draft_contract_errors_reach_http_client_as_field_validation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.main import upload_contract_error_handler
    api = FastAPI(exception_handlers={UploadContractError: upload_contract_error_handler})

    @api.post('/draft')
    def save(draft: dict):
        return convert_legacy_scientific_draft(draft)

    response = TestClient(api).post('/draft', json={'material_states': [{'state_kind': 'mixed'}]})
    assert response.status_code == 400
    assert response.json()['issues'][0]['field'] == 'material_states[0].state_kind'
    assert response.json()['detail']['code'] == 'invalid_material_state'
