"""#110：隔离 MySQL、真实 JWT/HTTP 下验证管理员科学图重建。"""
import copy
import uuid

import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select

from backend import models
from backend.tests.test_paper_revisions import workflow, seed_scientific_graph
from backend.services.paper_revisions import current_draft
from backend.services.property_record_upgrade_service import apply_upgrade, preview_upgrade, record_snapshot
from backend.ingest.property_modules import record_checksum


@pytest.fixture
def editing(workflow):
    w = workflow
    w.structure_ids, w.evidence_id = seed_scientific_graph(w)
    from backend.api.form_definitions import promotion_router
    from backend.ingest.form_definitions import definition_checksum, definition_payload
    w.client.app.include_router(promotion_router)
    with w.factory.begin() as session:
        session.get(models.Paper, w.paper.id).review_status = 'pending'
        session.get(models.User, w.other.id).role = 'superadmin'
        # 无变化保存须保留相同家族；临时新增家族本身就是科学数据变更。
        family_key = uuid.uuid4().hex
        family = models.MaterialFamily(code=family_key, name_zh=f'隔离保存测试家族{family_key}',
            normalized_name=f'隔离保存测试家族{family_key}')
        session.add(family)
        session.flush()
        session.add(models.PaperMaterialFamily(paper_id=w.paper.id, paper_revision=1, material_family_id=family.id))
        session.execute(delete(models.PropertyRecordDefinitionEvent).where(models.PropertyRecordDefinitionEvent.paper_id == w.paper.id))
        record = session.scalar(select(models.PropertyRecord).where(models.PropertyRecord.paper_id == w.paper.id, models.PropertyRecord.record_key == 'tc-1'))
        record.record_checksum = record_checksum(record_snapshot(record))
        target = session.scalar(select(models.FormDefinition).where(models.FormDefinition.definition_key == record.definition_key, models.FormDefinition.version == 2))
        if target is None:
            source = record.definition
            target = models.FormDefinition(**{c.name: copy.deepcopy(getattr(source, c.name)) for c in source.__table__.columns if c.name not in {'id', 'created_at', 'updated_at'}})
            target.version = 2
            target.checksum = definition_checksum(definition_payload(target))
            session.add(target)
            session.flush()
        preview = preview_upgrade(record, target)
        event = apply_upgrade(session, record, target, w.other.id, record.record_checksum, preview['preview_checksum'])
        w.event_id = event.id
        w.original_event = jsonable_encoder({c.name: getattr(event, c.name) for c in event.__table__.columns})
    w.client.headers['Authorization'] = 'Bearer ' + w.other_token
    w.save_url = f'/api/rag/papers/{w.paper.id}/scientific-draft'
    return w


def payload(w, *, native=True):
    with w.factory() as session:
        draft = current_draft(session, session.get(models.Paper, w.paper.id))
    if native:
        # 与共享前端转换一致：POSCAR 原文放在 poscar 槽位。
        for candidate in draft['structure_candidates']:
            candidate['representations'] = {'conventional': {candidate['original_format']: {'text': candidate['original_text'], 'available': True}}}
    return dict(paper_type=draft['paper']['paper_type'], superconductor_kind=draft['paper']['superconductor_kind'],
        material_families=draft['paper']['material_families'],
        material_states=draft['material_states'], structure_candidates=draft['structure_candidates'])


def graph(w):
    with w.factory() as session:
        result = {}
        for model in (models.MaterialState, models.StructureModel, models.StructureModelEvidence,
                      models.PropertyRecord, models.PropertyRecordDefinitionEvent, models.PaperHistoryEvent):
            result[model.__name__] = jsonable_encoder([
                {c.name: getattr(row, c.name) for c in row.__table__.columns}
                for row in session.scalars(select(model).where(model.paper_id == w.paper.id)
                                          .order_by(*model.__table__.primary_key.columns))])
        return result


@pytest.mark.parametrize('role', ['admin', 'superadmin'])
def test_pending_pressure_edit_preserves_graph_and_legal_definition_rollback(editing, role):
    w = editing
    with w.factory.begin() as session:
        session.get(models.User, w.other.id).role = role
    before = graph(w)
    draft = payload(w)
    draft['material_states'][0]['pressure_value_gpa'] = 2
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 200, response.text
    after = graph(w)
    old, new = before['StructureModel'], after['StructureModel']
    for left, right in zip(old, new):
        for key in ('structure_format', 'structure_text', 'structure_hash', 'space_group_symbol', 'space_group_number',
                    'cell_parameters', 'volume_angstrom3', 'atom_count', 'geometry_method', 'nuclear_treatment',
                    'exchange_correlation', 'calculation_code', 'method_parameters', 'source_locator'):
            assert right[key] == left[key], key
    assert new[1]['parent_structure_id'] == new[0]['id']
    assert after['StructureModelEvidence'][0]['structure_id'] == new[1]['id']
    record = after['PropertyRecord'][0]
    assert record['structure_key'] == f'structure-{new[1]["id"]}'
    assert after['PropertyRecordDefinitionEvent'][0]['id'] == w.event_id
    assert after['PropertyRecordDefinitionEvent'][0]['record_id'] == record['id']
    assert after['PaperHistoryEvent'][-1]['classification_snapshot']['previous_definition_events'] == [w.original_event]
    with w.factory.begin() as session:
        session.get(models.User, w.other.id).role = 'superadmin'
    response = w.client.post(f'/api/admin/papers/{w.paper.id}/property-records/tc-1/definition-upgrade/rollback', json={
        'event_id': w.event_id, 'expected_paper_revision': 1, 'expected_record_checksum': record['record_checksum']})
    assert response.status_code == 200, response.text
    rolled = graph(w)['PropertyRecord'][0]
    assert rolled['definition_version'] == 1
    assert rolled['structure_key'] == f'structure-{new[1]["id"]}'


@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_noop_repeat_and_coalesced_history_preserve_audit(editing, status):
    w = editing
    with w.factory.begin() as session:
        paper = session.get(models.Paper, w.paper.id)
        paper.review_status = status
        paper.approved_revision = 1 if status == 'approved' else None
    before = graph(w)
    response = w.client.put(w.save_url, json=payload(w))
    assert response.status_code == 200, response.text
    assert response.json()['data']['unchanged'] is True
    assert graph(w) == before
    operation = uuid.uuid4().hex
    with w.factory.begin() as session:
        # 快速审核的第一段 Go 元数据保存已写入同一操作的历史。
        session.add(models.PaperHistoryEvent(paper_id=w.paper.id, paper_revision=1, event_type='modified',
            actor_user_id=w.other.id, actor_username_snapshot=w.other.username, operation_id=operation))
    draft = payload(w)
    draft['history_operation_id'] = operation
    draft['material_states'][0]['pressure_value_gpa'] = 3
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 200, response.text
    assert response.json()['data']['revision_bumped'] is (status == 'approved')
    after = graph(w)
    assert len(after['PaperHistoryEvent']) == len(before['PaperHistoryEvent']) + 1
    assert after['PaperHistoryEvent'][-1]['classification_snapshot']['previous_definition_events'] == [w.original_event]
    assert bool(after['PropertyRecordDefinitionEvent']) is (status == 'pending')
    assert after['PaperHistoryEvent'][-1]['paper_revision'] == (2 if status == 'approved' else 1)
    assert w.client.put(w.save_url, json=payload(w)).json()['data']['unchanged'] is True
    assert graph(w) == after


def test_structure_only_deletion_is_saved_and_does_not_restore_deleted_parent(editing):
    w = editing
    draft = payload(w)
    draft['structure_candidates'][0]['confirmation'] = 'excluded'
    draft['structure_candidates'][0]['status'] = 'excluded'
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 200, response.text
    assert response.json()['data']['unchanged'] is False
    after = graph(w)
    assert len(after['StructureModel']) == 1
    assert after['StructureModel'][0]['parent_structure_id'] is None
    draft = payload(w)
    draft['structure_candidates'] = []
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 200, response.text
    assert graph(w)['StructureModel'] == []
    assert graph(w)['PropertyRecord'][0]['structure_key'] is None


@pytest.mark.parametrize('action', ['change', 'delete'])
def test_changed_or_deleted_records_archive_audit_without_restoring_rollback(editing, action):
    w = editing
    draft = payload(w)
    records = draft['material_states'][0]['property_modules'][0]['records']
    if action == 'change':
        records[0].update(value_number=12, value_raw='12 K')
    else:
        records.pop(0)
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 200, response.text
    after = graph(w)
    assert after['PropertyRecordDefinitionEvent'] == []
    assert after['PaperHistoryEvent'][-1]['classification_snapshot']['previous_definition_events'] == [w.original_event]


def test_foreign_structure_identity_is_rejected_atomically(editing):
    w = editing
    with w.factory.begin() as session:
        other = models.Paper(title='Other paper', year=2026, paper_type='experimental', review_status='pending', content_revision=1)
        session.add(other)
        session.flush()
        state = models.MaterialState(paper_id=other.id, paper_revision=1, state_key='other', material_dimensionality='unknown', state_kind='unknown', crystal_system='unknown')
        session.add(state)
        session.flush()
        source = session.get(models.StructureModel, w.structure_ids[0])
        foreign = models.StructureModel(paper_id=other.id, paper_revision=1, material_state_id=state.id,
            structure_format='cif', structure_text=source.structure_text, structure_hash=source.structure_hash, nuclear_treatment='unknown')
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id
    before = graph(w)
    draft = payload(w)
    draft['material_states'][0]['pressure_value_gpa'] = 2
    draft['structure_candidates'][0]['candidate_id'] = f'structure_{foreign_id}'
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 409, response.text
    assert graph(w) == before


@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_late_failure_rolls_back_all_scientific_entities(editing, monkeypatch, status):
    w = editing
    with w.factory.begin() as session:
        paper = session.get(models.Paper, w.paper.id)
        paper.review_status = status
        paper.approved_revision = 1 if status == 'approved' else None
    from backend.ingest import property_evidence
    async def fail(*args, **kwargs):
        raise ValueError('injected persistence failure')
    monkeypatch.setattr(property_evidence, 'persist_existing_paper_targets', fail)
    before = graph(w)
    draft = payload(w, native=False)
    draft['material_states'][0]['pressure_value_gpa'] = 2
    with pytest.raises(ValueError, match='injected persistence failure'):
        w.client.put(w.save_url, json=draft)
    assert graph(w) == before
    with w.factory() as session:
        paper = session.get(models.Paper, w.paper.id)
        assert (paper.review_status, paper.content_revision) == (status, 1)


def test_permissions_and_stale_evidence_preparation_do_not_rewrite(editing):
    w = editing
    before = graph(w)
    draft = payload(w)
    draft['material_states'][0]['pressure_value_gpa'] = 2
    w.client.headers['Authorization'] = 'Bearer ' + w.owner_token
    assert w.client.put(w.save_url, json=draft).status_code == 403
    w.client.headers['Authorization'] = 'Bearer ' + w.other_token
    draft['evidence_preparation_id'] = 'missing-preparation'
    assert w.client.put(w.save_url, json=draft).status_code == 409
    assert graph(w) == before


def test_edit_structure_does_not_inherit_original_metadata_or_sources(editing):
    w = editing
    draft = payload(w)
    candidate = draft['structure_candidates'][1]
    candidate['representations']['conventional']['poscar']['text'] = candidate['original_text'].replace('5.4307', '6.4307')
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200, result.text
    after = graph(w)
    assert after['StructureModel'][1]['structure_format'] == 'cif'
    assert after['StructureModel'][1]['source_locator'] != 'Table 2'
    assert after['StructureModelEvidence'] == []
    assert after['PropertyRecord'][0]['structure_key'] == f'structure-{after["StructureModel"][1]["id"]}'


def test_reordered_states_do_not_mix_identical_record_keys(editing):
    w = editing
    import asyncio
    from backend.ingest.scientific_drafts import persist_scientific_draft
    draft = payload(w)
    second = copy.deepcopy(draft['material_states'][0])
    second['state_key'] = 'sample-b'
    for record in second['property_modules'][0]['records']:
        record.update(structure_key=None, value_number=20, value_raw='20')
        record.pop('source_fingerprint', None)
        record['evidences'] = []
    async def seed():
        async with w.async_factory.begin() as session:
            paper = await session.get(models.Paper, w.paper.id)
            await persist_scientific_draft(session, paper, {'material_states': [second]})
    asyncio.run(seed())
    draft = payload(w)
    draft['material_states'].reverse()
    draft['material_states'][0]['pressure_value_gpa'] = 4
    for candidate in draft['structure_candidates']:
        candidate['material_state_ref'] = 'material_states[1]'
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200, result.text
    with w.factory() as session:
        event = session.get(models.PropertyRecordDefinitionEvent, w.event_id)
        record = session.get(models.PropertyRecord, event.record_id)
        state = session.get(models.MaterialState, record.material_state_id)
        assert state.state_key == 'sample-a' and record.value_number == 10
        others = list(session.scalars(select(models.PropertyRecord).join(models.MaterialState, models.MaterialState.id == models.PropertyRecord.material_state_id)
            .where(models.PropertyRecord.paper_id == w.paper.id, models.MaterialState.state_key == 'sample-b')))
        assert all(r.value_number == 20 and r.structure_key is None for r in others)


def test_retry_with_old_structure_ids_does_not_rebuild_or_add_history(editing):
    w = editing
    draft = payload(w)
    draft['material_states'][0]['pressure_value_gpa'] = 2
    assert w.client.put(w.save_url, json=draft).status_code == 200
    after = graph(w)
    response = w.client.put(w.save_url, json=draft)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'structure_reference_stale'
    assert graph(w) == after


def test_duplicate_structure_reference_is_rejected_before_writes(editing):
    w = editing
    draft = payload(w)
    draft['structure_candidates'].append(copy.deepcopy(draft['structure_candidates'][0]))
    before = graph(w)
    assert w.client.put(w.save_url, json=draft).status_code == 409
    assert graph(w) == before


def test_later_record_edit_blocks_definition_rollback_even_with_current_checksum(editing):
    w = editing
    with w.factory.begin() as session:
        event = session.get(models.PropertyRecordDefinitionEvent, w.event_id)
        record = session.get(models.PropertyRecord, event.record_id)
        record.value_number, record.value_raw = 12, '12'
        record.record_checksum = record_checksum(record_snapshot(record))
        checksum = record.record_checksum
    response = w.client.post(f'/api/admin/papers/{w.paper.id}/property-records/tc-1/definition-upgrade/rollback', json={
        'event_id': w.event_id, 'expected_paper_revision': 1, 'expected_record_checksum': checksum})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['issues'][0]['code'] == 'definition_rollback_stale'


def test_preview_representations_roundtrip_keeps_original_text_and_metadata(editing):
    w = editing
    before = graph(w)
    draft = payload(w)
    for candidate, structure_id in zip(draft['structure_candidates'], w.structure_ids):
        response = w.client.get(f'/api/rag/papers/{w.paper.id}/structures/{structure_id}/representations')
        assert response.status_code == 200, response.text
        candidate['representations'] = response.json()['data']['representations']
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200 and result.json()['data']['unchanged'] is True, result.text
    draft['material_states'][0]['pressure_value_gpa'] = 2
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200, result.text
    after = graph(w)
    assert after['StructureModel'][0]['exchange_correlation'] == 'PBE'
    assert [s['structure_text'] for s in after['StructureModel']] == [s['structure_text'] for s in before['StructureModel']]
    assert len(after['StructureModelEvidence']) == 1


def test_replacing_structure_with_same_text_keeps_new_source(editing):
    w = editing
    draft = payload(w)
    candidate = draft['structure_candidates'][0]
    candidate['candidate_id'] = 'new-attachment'
    candidate['sources'] = [{'filename': 'replacement.cif'}]
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200 and result.json()['data']['unchanged'] is False, result.text
    after = graph(w)
    assert after['StructureModel'][0]['source_locator'] == 'attachment: replacement.cif'
    assert after['StructureModel'][0]['exchange_correlation'] is None
    assert after['StructureModel'][1]['parent_structure_id'] is None
    assert result.json()['data']['structure_candidate_id_map']['new-attachment'] == f'structure_{after["StructureModel"][0]["id"]}'


def test_upgrade_without_definition_events_updates_shared_history_revision(editing):
    w = editing
    operation = uuid.uuid4().hex
    with w.factory.begin() as session:
        session.execute(delete(models.PropertyRecordDefinitionEvent).where(models.PropertyRecordDefinitionEvent.paper_id == w.paper.id))
        paper = session.get(models.Paper, w.paper.id)
        paper.review_status, paper.approved_revision = 'approved', 1
        session.add(models.PaperHistoryEvent(paper_id=paper.id, paper_revision=1, event_type='modified',
            actor_user_id=w.other.id, actor_username_snapshot=w.other.username, operation_id=operation))
    draft = payload(w)
    draft['history_operation_id'] = operation
    draft['material_states'][0]['pressure_value_gpa'] = 2
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200, result.text
    assert graph(w)['PaperHistoryEvent'][-1]['paper_revision'] == 2


def test_legacy_direct_structure_noop_and_pressure_edit_preserve_metadata(editing):
    w = editing
    before = graph(w)
    draft = payload(w)
    first = draft['structure_candidates'].pop(0)
    draft['material_states'][0]['structure'] = dict(structure_format='cif', structure_text=first['original_text'], nuclear_treatment='experimental')
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200 and result.json()['data']['unchanged'] is True, result.text
    assert graph(w) == before
    draft['material_states'][0]['pressure_value_gpa'] = 2
    result = w.client.put(w.save_url, json=draft)
    assert result.status_code == 200, result.text
    after = graph(w)
    assert after['StructureModel'][0]['exchange_correlation'] == 'PBE'
    assert after['StructureModel'][1]['parent_structure_id'] == after['StructureModel'][0]['id']
