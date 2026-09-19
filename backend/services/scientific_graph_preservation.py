"""科学图整体重建时，保留既有结构和仍有效的定义审计链。"""
from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import insert, select

from backend import models
from backend.ingest.scientific_drafts import _candidate_state_index, _candidate_conventional_representation
from backend.services.property_record_upgrade_service import record_snapshot


STRUCTURE_METADATA = (
    'structure_format', 'structure_text', 'structure_hash', 'space_group_symbol', 'space_group_number',
    'cell_parameters', 'volume_angstrom3', 'atom_count', 'geometry_method', 'nuclear_treatment',
    'exchange_correlation', 'calculation_code', 'method_parameters', 'source_locator',
)


async def snapshot_rows(session, model, paper_id):
    """读取独立列快照，避免删除后 ORM 仍持有旧主键对象。"""
    result = await session.execute(select(model.__table__).where(model.paper_id == paper_id))
    return [deepcopy(dict(row)) for row in result.mappings()]


async def snapshot_structures(session, paper_id):
    result = await session.execute(select(models.StructureModel.__table__, models.MaterialState.state_key)
        .join(models.MaterialState, models.MaterialState.id == models.StructureModel.material_state_id)
        .where(models.StructureModel.paper_id == paper_id))
    return [deepcopy(dict(row)) for row in result.mappings()]


def conventional_cif(structure_format, structure_text):
    if structure_format.lower() == 'cif':
        return structure_text
    from backend.services.structure_candidates import read_atoms, export_representations
    return export_representations(read_atoms(structure_format, structure_text))['conventional']['cif']['text']


def unchanged_structure_text(old, text):
    if old['structure_format'].lower() == 'cif' and text == old['structure_text']:
        return True
    # 编辑页会异步加载标准化表示；同一原结构的导出 CIF 仍视为未编辑。
    from backend.services.structure_candidates import read_atoms, export_representations
    exported = export_representations(read_atoms(old['structure_format'], old['structure_text']))
    return text == exported['conventional']['cif']['text']


def confirmed_candidates(draft):
    return [c for c in draft.get('structure_candidates') or [] if isinstance(c, dict)
            and c.get('confirmation') == 'confirmed' and c.get('status') == 'confirmed']


def direct_structure_original(state, index, originals, state_keys, consumed=()):
    direct = state.get('structure')
    if not isinstance(direct, dict) or not str(direct.get('structure_text') or '').strip():
        return None
    return next((s for s in originals if s['id'] not in consumed
        and state_keys.get(s['material_state_id']) == str(state.get('state_key') or f'state-{index + 1}')
        and s['structure_format'] == (direct.get('structure_format') or 'unknown')
        and s['structure_text'] == direct['structure_text']
        and s['nuclear_treatment'] == (direct.get('nuclear_treatment') or 'unknown')
        and s['space_group_symbol'] == (direct.get('space_group_symbol') or state.get('reported_space_group_symbol'))
        and s['space_group_number'] == (direct.get('space_group_number') or state.get('reported_space_group_number'))), None)


def prepare_existing_structure_candidates(draft, originals):
    """既有候选只能引用当前论文；POSCAR 在服务端转成校验所需的 CIF。"""
    old_by_id = {f'structure_{s["id"]}': s for s in originals}
    seen = set()
    for candidate in confirmed_candidates(draft):
        identity = str(candidate.get('candidate_id') or '')
        if not identity.startswith('structure_'):
            continue
        if identity not in old_by_id or identity in seen:
            raise HTTPException(409, detail={'code': 'structure_reference_stale', 'message': '既有结构不属于当前论文、已变化或被重复引用，请刷新后重试'})
        seen.add(identity)
        conventional = (candidate.get('representations') or {}).get('conventional') or {}
        poscar = conventional.get('poscar') or {}
        if not _candidate_conventional_representation(candidate) and str(poscar.get('text') or '').strip():
            try:
                conventional['cif'] = {'text': conventional_cif('poscar', poscar['text']), 'available': True}
                candidate['representations']['conventional'] = conventional
            except Exception as exc:
                raise HTTPException(400, detail={'code': 'structure_validation_failed', 'message': '既有 POSCAR 未通过服务端校验'}) from exc


async def structures_match_current(session, paper, draft):
    originals = await snapshot_rows(session, models.StructureModel, paper.id)
    state_keys = dict((await session.execute(select(models.MaterialState.id, models.MaterialState.state_key)
        .where(models.MaterialState.paper_id == paper.id))).all())
    old_by_id = {f'structure_{s["id"]}': s for s in originals}
    requested = []
    states = draft.get('material_states') or []
    consumed = set()
    for index, state in enumerate(states):
        direct = state.get('structure')
        if isinstance(direct, dict) and str(direct.get('structure_text') or '').strip():
            state_key = str(state.get('state_key') or f'state-{index + 1}')
            old = direct_structure_original(state, index, originals, state_keys, consumed)
            if old:
                consumed.add(old['id'])
            requested.append((state_key, direct.get('structure_format') or 'unknown', direct['structure_text'], old['id'] if old else 0))
    for candidate in confirmed_candidates(draft):
        index = _candidate_state_index(candidate)
        representation = _candidate_conventional_representation(candidate)
        if index is None or index >= len(states) or not representation:
            return False
        old = old_by_id.get(candidate.get('candidate_id'))
        text, fmt = representation[0], 'cif'
        if old and unchanged_structure_text(old, text):
            text, fmt = old['structure_text'], old['structure_format']
        requested.append((str(states[index].get('state_key') or f'state-{index + 1}'), fmt, text, old['id'] if old else 0))
    stored = [(state_keys[s['material_state_id']], s['structure_format'], s['structure_text'], s['id']) for s in originals]
    return sorted(requested) == sorted(stored)


def remap_structure_key(key, id_map):
    if key and key.startswith('structure-'):
        suffix = key.removeprefix('structure-')
        mapped = id_map.get(int(suffix)) if suffix.isdigit() else None
        return f'structure-{mapped}' if mapped else None
    return key


async def preserve_structure_metadata(session, paper, draft, originals, evidence_links, *, candidate_id_map=None):
    """按候选身份重新绑定结构；只有原文未编辑时才恢复原物理元数据和来源。"""
    states = (await session.scalars(select(models.MaterialState).where(models.MaterialState.paper_id == paper.id)
        .order_by(models.MaterialState.id))).all()
    new_structures = (await session.scalars(select(models.StructureModel).where(models.StructureModel.paper_id == paper.id)
        .order_by(models.StructureModel.id))).all()
    old_by_id = {f'structure_{s["id"]}': s for s in originals}
    id_map, unchanged, used_ids = {}, set(), set()
    # 旧契约的 state.structure 没有候选 ID；仅在同一状态原文及可写字段完全相同时恢复。
    old_state_keys = {s['material_state_id']: s.get('state_key') for s in originals}
    for index, state in enumerate(draft.get('material_states') or []):
        old = direct_structure_original(state, index, originals, old_state_keys, id_map)
        if old is None:
            continue
        new = next((s for s in new_structures if s.material_state_id == states[index].id
                    and s.structure_text == old['structure_text'] and s.id not in used_ids), None)
        if new:
            id_map[old['id']] = new.id
            used_ids.add(new.id)
            unchanged.add(old['id'])
            for key in STRUCTURE_METADATA:
                setattr(new, key, old[key])
    for candidate in confirmed_candidates(draft):
        old = old_by_id.get(candidate.get('candidate_id'))
        index = _candidate_state_index(candidate)
        representation = _candidate_conventional_representation(candidate)
        if index is None or index >= len(states) or not representation:
            continue
        new = next((s for s in new_structures if s.material_state_id == states[index].id
                    and s.structure_text == representation[0] and s.id not in used_ids), None)
        if new is None:
            continue
        used_ids.add(new.id)
        if candidate_id_map is not None:
            candidate_id_map[candidate['candidate_id']] = f'structure_{new.id}'
        if not old:
            continue
        id_map[old['id']] = new.id
        if unchanged_structure_text(old, representation[0]):
            unchanged.add(old['id'])
            for key in STRUCTURE_METADATA:
                setattr(new, key, old[key])
    by_id = {s.id: s for s in new_structures}
    for old in originals:
        if old['id'] in id_map and old['parent_structure_id'] in id_map:
            by_id[id_map[old['id']]].parent_structure_id = id_map[old['parent_structure_id']]
    for record in (await session.scalars(select(models.PropertyRecord).where(models.PropertyRecord.paper_id == paper.id))).all():
        if record.structure_key and record.structure_key.startswith('structure-'):
            record.structure_key = remap_structure_key(record.structure_key, id_map)
            from backend.ingest.property_modules import validate_record
            snapshot = await session.run_sync(lambda s: record_snapshot(record))
            record.record_checksum = validate_record(snapshot)['record_checksum']
    for link in evidence_links:
        if link['structure_id'] in unchanged:
            identity = (id_map[link['structure_id']], link['paper_evidence_id'])
            if await session.get(models.StructureModelEvidence, identity) is None:
                session.add(models.StructureModelEvidence(structure_id=identity[0], paper_evidence_id=identity[1],
                    paper_id=paper.id, paper_revision=paper.content_revision, evidence_role=link['evidence_role']))
    return id_map


async def snapshot_records(session, paper_id):
    rows = (await session.execute(select(models.PropertyRecord, models.MaterialState.state_key, models.PropertyModule.module_key)
        .join(models.MaterialState, models.MaterialState.id == models.PropertyRecord.material_state_id)
        .join(models.PropertyModule, models.PropertyModule.id == models.PropertyRecord.module_id)
        .where(models.PropertyRecord.paper_id == paper_id))).all()
    return {record.id: {'identity': (state_key, module_key, record.record_key),
            'snapshot': await session.run_sync(lambda s: record_snapshot(record))}
            for record, state_key, module_key in rows}


async def restore_definition_events(session, paper, events, old_records, structure_id_map):
    """同版本且记录未编辑才恢复活动事件；原始事件始终另存论文历史。"""
    new_records = {item['identity']: (record_id, item['snapshot'])
                   for record_id, item in (await snapshot_records(session, paper.id)).items()}
    for event in events:
        old = old_records.get(event['record_id'])
        new = new_records.get(old['identity']) if old else None
        if event['paper_revision'] != paper.content_revision or new is None:
            continue
        before = deepcopy(old['snapshot'])
        before['structure_key'] = remap_structure_key(before.get('structure_key'), structure_id_map)
        if before != new[1]:
            continue
        restored = deepcopy(event)
        restored['record_id'] = new[0]
        for key in ('before_snapshot', 'after_snapshot'):
            restored[key]['structure_key'] = remap_structure_key(restored[key].get('structure_key'), structure_id_map)
        # 原事件 ID 与前序 ID 保持不变，已打开的合法回滚请求仍能找到事件。
        await session.execute(insert(models.PropertyRecordDefinitionEvent).values(**restored))
