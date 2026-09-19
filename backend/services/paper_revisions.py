"""上传者返修：独立草稿、并发保护及原子重新送审（#108）。"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select

from backend import models
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.services.scientific_graph_preservation import preserve_structure_metadata, snapshot_structures

PAPER_FIELDS = (
    'title', 'doi', 'authors', 'journal', 'year', 'volume', 'issue_number', 'pages',
    'abstract', 'summary', 'paper_type', 'theoretical_subtype', 'superconductor_kind',
    'keywords_tags', 'methodology', 'knowledge_graph_title', 'key_finding',
    'research_motivation', 'research_materials', 'material_relations', 'builds_on',
)
LIST_FIELDS = {'authors', 'keywords_tags', 'methodology', 'research_materials', 'material_relations', 'builds_on'}
AUTHOR_ROLE_FIELDS = ('corresponding_authors', 'co_first_authors')
INTERNAL_COLUMNS = {'id', 'paper_id', 'paper_revision', 'created_at', 'updated_at'}


def error(status, code, message):
    raise HTTPException(status, detail={'code': code, 'message': message})


def require_owner(paper, user):
    if paper is None:
        error(404, 'paper_not_found', '论文不存在')
    if paper.uploaded_by_user_id != user.id:
        error(403, 'revision_forbidden', '只有原上传者可以返修这篇论文')


def require_rejected(paper):
    if paper.review_status != 'rejected':
        error(409, 'revision_status_changed', '论文已不处于拒绝状态，请返回详情查看最新审核结果')


def values(row, exclude=()):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns
            if c.name not in INTERNAL_COLUMNS and c.name not in exclude}


def rows(session, model, paper_id):
    return list(session.scalars(select(model).where(model.paper_id == paper_id).order_by(model.id)))


def term(row, **extra):
    return dict(id=row.id, name=row.name_zh, name_zh=row.name_zh, name_en=row.name_en,
                status='confirmed', **extra)


def current_draft(session, paper):
    """完整读取当前科学图，不借用已清理任务，也不暴露路径或管理员字段。"""
    data = {key: getattr(paper, key) for key in PAPER_FIELDS}
    for key in LIST_FIELDS:
        if isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except ValueError:
                data[key] = [data[key]] if data[key].strip() else []
        data[key] = data[key] or []
    last_submission = session.scalar(select(models.PaperHistoryEvent).where(
        models.PaperHistoryEvent.paper_id == paper.id, models.PaperHistoryEvent.operation_id.like('revision:%'))
        .order_by(models.PaperHistoryEvent.id.desc()).limit(1))
    saved_paper = ((last_submission.classification_snapshot or {}).get('revision_submission', {}).get('paper', {})
                   if last_submission else {})
    for key in AUTHOR_ROLE_FIELDS:
        data[key] = [author for author in saved_paper.get(key, []) if author in data['authors']]
    data['material_families'] = [term(f) for f in session.scalars(select(models.MaterialFamily)
        .join(models.PaperMaterialFamily, models.PaperMaterialFamily.material_family_id == models.MaterialFamily.id)
        .where(models.PaperMaterialFamily.paper_id == paper.id).order_by(models.MaterialFamily.id))]
    states, candidates = [], []
    source_evidence = {e.id: e for e in rows(session, models.PaperEvidence, paper.id)}
    chunks = {c.id: c for c in rows(session, models.PaperChunk, paper.id)}
    for index, state in enumerate(rows(session, models.MaterialState, paper.id)):
        item = values(state, {'superconductor_id'})
        material = session.get(models.Superconductor, state.superconductor_id) if state.superconductor_id else None
        item['material'] = material.chemical_formula if material else ''
        item['structure_families'] = [term(f, is_primary=link.is_primary)
            for link, f in session.execute(select(models.MaterialStateStructureFamily, models.StructureFamily)
                .join(models.StructureFamily, models.StructureFamily.id == models.MaterialStateStructureFamily.structure_family_id)
                .where(models.MaterialStateStructureFamily.material_state_id == state.id).order_by(models.StructureFamily.id))]
        item.update(schema_version=2, property_modules=[], deleted_record_keys=[], deleted_module_keys=[])
        for module in session.scalars(select(models.PropertyModule).where(models.PropertyModule.material_state_id == state.id)
                                      .order_by(models.PropertyModule.display_order, models.PropertyModule.id)):
            m = values(module, {'material_state_id', 'metadata_json'})
            m.update(metadata=module.metadata_json or {}, records=[])
            for record in session.scalars(select(models.PropertyRecord).where(models.PropertyRecord.module_id == module.id).order_by(models.PropertyRecord.id)):
                r = values(record, {'module_id', 'material_state_id', 'definition_id', 'payload_json'})
                r.update(payload=record.payload_json or {}, evidences=[])
                for link in session.scalars(select(models.PropertyRecordEvidence).where(models.PropertyRecordEvidence.record_id == record.id)):
                    e = source_evidence.get(link.paper_evidence_id)
                    c = chunks.get(e.paper_chunk_id) if e else None
                    if c:
                        r['evidences'].append(dict(file_id=str(c.paper_file_id), chunk_id=c.id,
                            chunk_index=c.chunk_index, quote=e.quote, page_start=e.page_start, page_end=e.page_end))
                m['records'].append(r)
            item['property_modules'].append(m)
        states.append(item)
        for structure in session.scalars(select(models.StructureModel).where(models.StructureModel.material_state_id == state.id).order_by(models.StructureModel.id)):
            text = structure.structure_text
            if structure.structure_format.lower() != 'cif':
                from backend.services.structure_candidates import read_atoms, export_representations
                text = export_representations(read_atoms(structure.structure_format, text))['conventional']['cif']['text']
            candidates.append(dict(candidate_id=f'structure_{structure.id}',
                material_state_ref=f'material_states[{index}]', status='confirmed', confirmation='confirmed',
                source_kind='attachment', original_format=structure.structure_format, original_text=structure.structure_text,
                representations={'conventional': {'cif': {'text': text, 'available': True}}},
                validation={'structure_format': 'cif', 'atom_count': structure.atom_count, 'cell_parameters': structure.cell_parameters},
                sources=[{'file_id': f'structure_{structure.id}', 'filename': f'structure_{structure.id}.cif', 'role': 'attachment'}]))
    return jsonable_encoder(dict(paper=data, material_states=states, structure_candidates=candidates))


def fingerprint(session, paper, draft=None):
    # 审核事件 ID 可检测同一秒内 rejected→pending→rejected 的往返。
    latest = session.scalar(select(models.PaperHistoryEvent.id).where(models.PaperHistoryEvent.paper_id == paper.id)
                            .order_by(models.PaperHistoryEvent.id.desc()).limit(1))
    return ev.digest([draft or current_draft(session, paper), paper.content_revision, paper.review_status,
        str(paper.reviewed_at), paper.review_comment, latest,
        [ev.row_dict(r) for r in rows(session, models.PaperFile, paper.id)],
        [ev.row_dict(r) for r in rows(session, models.PaperChunk, paper.id)],
        [ev.row_dict(r) for r in rows(session, models.StructureModel, paper.id)],
        [ev.row_dict(r) for r in rows(session, models.PaperEvidence, paper.id)],
        [ev.row_dict(r) for r in session.scalars(select(models.StructureModelEvidence)
            .where(models.StructureModelEvidence.paper_id == paper.id)
            .order_by(models.StructureModelEvidence.structure_id, models.StructureModelEvidence.paper_evidence_id))]])


def assert_current(session, paper, saved):
    require_rejected(paper)
    if saved.draft is None or saved.base_revision != paper.content_revision or saved.base_fingerprint != fingerprint(session, paper):
        error(409, 'revision_conflict', '论文内容或审核结果已变化；返修草稿已保留，请先核对最新论文')


def response(saved, paper, *, conflict=False):
    missing = not (saved.draft or {}).get('paper', {}).get('material_families')
    warnings = ['旧审核快照中的材料家族未保存在正式记录中，请重新选择后提交。'] if missing else []
    if not any((saved.draft or {}).get('paper', {}).get(key) for key in AUTHOR_ROLE_FIELDS):
        warnings.append('旧通讯作者和共同第一作者标记若未保存在历史中，无法恢复；请按原文补充。')
    return dict(ok=True, data=saved.draft, revision_id=saved.revision_id, draft_version=saved.draft_version,
        base_revision=saved.base_revision, review_comment=paper.review_comment, conflict=conflict,
        warnings=warnings)


async def locked_paper(session, paper_id, user):
    paper = await session.scalar(select(models.Paper).where(models.Paper.id == paper_id).with_for_update())
    require_owner(paper, user)
    return paper


async def open_draft(session, paper_id, user, *, create=False):
    paper = await locked_paper(session, paper_id, user)
    require_rejected(paper)
    saved = await session.get(models.PaperRevisionDraft, paper_id, with_for_update=True)
    if saved is None or saved.draft is None:
        if not create:
            error(404, 'revision_draft_missing', '尚未开始返修')
        draft = await session.run_sync(lambda s: current_draft(s, paper))
        baseline = await session.run_sync(lambda s: fingerprint(s, paper, draft))
        if saved is None:
            saved = models.PaperRevisionDraft(paper_id=paper_id, owner_id=user.id)
            session.add(saved)
        saved.revision_id, saved.base_revision, saved.base_fingerprint = uuid.uuid4().hex, paper.content_revision, baseline
        saved.draft, saved.draft_version, saved.submitted_revision = draft, 1, None
        saved.created_at = datetime.utcnow()
        for origin in (await session.scalars(select(models.ScientificStructureOrigin).where(
                models.ScientificStructureOrigin.target == 'paper', models.ScientificStructureOrigin.target_id == str(paper_id)))).all():
            session.add(models.ScientificStructureOrigin(target='revision', target_id=saved.revision_id,
                structure_hash=origin.structure_hash, provenance=copy.deepcopy(origin.provenance)))
        await session.flush()
    conflict = saved.base_revision != paper.content_revision or saved.base_fingerprint != await session.run_sync(lambda s: fingerprint(s, paper))
    return response(saved, paper, conflict=conflict)


async def load_for_write(session, paper_id, user, revision_id, version=None):
    paper = await locked_paper(session, paper_id, user)
    saved = await session.get(models.PaperRevisionDraft, paper_id, with_for_update=True)
    if saved is None or saved.revision_id != revision_id:
        error(409, 'revision_conflict', '返修草稿已变化，请重新打开')
    await session.run_sync(lambda s: assert_current(s, paper, saved))
    if version is not None and saved.draft_version != version:
        error(409, 'revision_draft_conflict', '草稿已在其他窗口保存，请先重新打开；当前输入未覆盖已保存内容')
    return paper, saved


def revision_snapshot(session, revision_id, owner):
    # 锁顺序始终为论文→草稿，与提交及审核一致。
    paper_id = session.scalar(select(models.PaperRevisionDraft.paper_id).where(models.PaperRevisionDraft.revision_id == revision_id))
    if paper_id is None:
        error(404, 'revision_draft_missing', '返修草稿不存在')
    paper = session.get(models.Paper, paper_id)
    require_owner(paper, models.User(id=owner))
    saved = session.get(models.PaperRevisionDraft, paper_id)
    assert_current(session, paper, saved)
    files = {f.id: f.original_filename for f in rows(session, models.PaperFile, paper.id)}
    chunks = [dict(chunk_id=c.id, file_id=str(c.paper_file_id), source_name=files.get(c.paper_file_id),
        chunk_index=c.chunk_index, content=c.content, page_start=c.page_start, page_end=c.page_end, section=c.section_name)
        for c in rows(session, models.PaperChunk, paper.id)]
    records = ev.draft_records(saved.draft, science.origins_for(session, 'revision', revision_id))
    snapshot = ev.complete_snapshot('revision', revision_id, records, chunks, saved.draft)
    snapshot['draft_version'] = saved.draft_version
    return snapshot


async def save_draft(session, paper_id, user, payload):
    from backend.api.rag import _validate_draft, _reject_legacy_classification_contract, _resolve_draft_classifications, _derived_research_materials
    from backend.ingest.upload_jobs import _normalize_draft
    paper, saved = await load_for_write(session, paper_id, user, payload.revision_id, payload.draft_version)
    if payload.evidence_preparation_id:
        from backend.ingest.evidence_proposals import validate_save
        await session.run_sync(lambda s: validate_save(s, revision_snapshot(s, saved.revision_id, user.id), user.id, payload.evidence_preparation_id, 'upload'))
    _reject_legacy_classification_contract(payload.draft)
    draft = _normalize_draft(copy.deepcopy(payload.draft))
    draft['paper'] = {k: v for k, v in draft['paper'].items() if k in {*PAPER_FIELDS, 'material_families', 'corresponding_authors', 'co_first_authors'}}
    draft['paper']['research_materials'] = _derived_research_materials(draft['material_states'])
    # 来源解析信息由服务端持有，客户端不能替换正文或引用解析。
    draft.pop('citation_extraction', None)
    await _resolve_draft_classifications(session, draft)
    _validate_draft(draft, partial=True)
    if draft != saved.draft:
        saved.draft, saved.draft_version = draft, saved.draft_version + 1
    await session.flush()
    return response(saved, paper)


async def submit_draft(session, paper_id, user, payload):
    from backend.api.rag import _validate_draft, _resolve_draft_classifications
    from backend.ingest.scientific_drafts import persist_scientific_draft
    from backend.services.scientific_draft_rewrite import delete_scientific_entities, bump_paper_revision
    from backend.services.paper_history import append_paper_history_event
    paper = await locked_paper(session, paper_id, user)
    operation_id = 'revision:' + payload.revision_id
    done = await session.scalar(select(models.PaperHistoryEvent).where(
        models.PaperHistoryEvent.operation_id == operation_id, models.PaperHistoryEvent.paper_id == paper_id,
        models.PaperHistoryEvent.actor_user_id == user.id))
    if done is not None:
        return dict(ok=True, paper_id=paper_id, content_revision=done.paper_revision, review_status=paper.review_status)
    paper, saved = await load_for_write(session, paper_id, user, payload.revision_id, payload.draft_version)
    draft = copy.deepcopy(saved.draft)
    await _resolve_draft_classifications(session, draft)
    data, _ = _validate_draft(draft)
    from backend.ingest.upload_jobs import normalize_doi
    doi = normalize_doi(data.get('doi')) or None
    if doi and await session.scalar(select(models.Paper.id).where(models.Paper.doi == doi, models.Paper.id != paper_id)):
        error(409, 'duplicate_doi', '该 DOI 已属于另一篇论文，请核对后提交')
    snapshot = await session.run_sync(lambda s: revision_snapshot(s, saved.revision_id, user.id))
    cached = await session.run_sync(lambda s: science.load_results(s, snapshot, user.id))
    checks = ev.resolve_results(snapshot, cached, user.id, payload.evidence_job_id, payload.expected_evidence_version)
    for result in checks:
        if result.get('kind') == 'property':
            state = draft['material_states'][result['state_index']]
            module = next(m for m in state['property_modules'] if m['module_key'] == result['module_key'])
            record = next(r for r in module['records'] if r['record_key'] == result['record_key'])
            record.pop('evidence', None)
            record['evidences'] = result['evidences']
    old_structures = await snapshot_structures(session, paper.id)
    old_structure_evidence = [ev.row_dict(r) for r in (await session.scalars(select(models.StructureModelEvidence)
        .where(models.StructureModelEvidence.paper_id == paper.id))).all()]
    # 整体重建会删除记录级定义迁移事件；在论文历史中保存原始事件，包含被主动删除的记录。
    definition_history = await session.run_sync(lambda s: [ev.row_dict(r) for r in rows(s, models.PropertyRecordDefinitionEvent, paper.id)])
    await delete_scientific_entities(session, paper.id)
    await session.execute(delete(models.PaperMaterialFamily).where(models.PaperMaterialFamily.paper_id == paper.id))
    await bump_paper_revision(session, paper)
    for key in PAPER_FIELDS:
        value = data.get(key)
        if key in {'keywords_tags', 'methodology'}:
            value = json.dumps(value or [], ensure_ascii=False)
        setattr(paper, key, value)
    paper.doi = doi
    paper.reviewed_at = paper.reviewed_by_user_id = paper.review_comment = None
    targets = await persist_scientific_draft(session, paper, draft)
    await ev.persist_existing_paper_targets(session, paper, targets)
    await preserve_structure_metadata(session, paper, draft, old_structures, old_structure_evidence)
    # 本轮模型结果只按内容和来源完全一致的项目转给待审论文；没有人工管理员裁决继承。
    for origin in (await session.scalars(select(models.ScientificStructureOrigin).where(
            models.ScientificStructureOrigin.target == 'revision', models.ScientificStructureOrigin.target_id == saved.revision_id))).all():
        existing = await session.scalar(select(models.ScientificStructureOrigin.id).where(
            models.ScientificStructureOrigin.target == 'paper', models.ScientificStructureOrigin.target_id == str(paper.id),
            models.ScientificStructureOrigin.structure_hash == origin.structure_hash))
        if existing is None:
            session.add(models.ScientificStructureOrigin(target='paper', target_id=str(paper.id),
                structure_hash=origin.structure_hash, provenance=copy.deepcopy(origin.provenance)))
    await session.flush()
    persisted = await session.run_sync(lambda s: ev.paper_snapshot(s, paper.id, 0, '', check_access=False))
    by_item = {r['item_key']: r for r in checks}
    transferred = {}
    for record in persisted['records']:
        old = by_item.get(record['item_key'])
        if old and old['content_hash'] == record['content_hash'] and old['source_hash'] == record['source_hash']:
            transferred[record['key']] = {**old, **record, 'decision': None, 'proposal_draft': None}
    # 新轮次不继承待审目标上的旧管理员草稿，永久来源与审核历史仍保留。
    await session.execute(delete(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == 'paper', models.ScientificEvidenceCheck.target_id == str(paper.id)))
    await session.run_sync(lambda s: science.save_results(s, persisted, transferred, user.id))
    classifications = dict(paper={k: data.get(k) for k in ('material_families', 'superconductor_kind', *AUTHOR_ROLE_FIELDS)},
        material_states=[{k: s.get(k) for k in ('state_key', 'element_count', 'material_dimensionality', 'structure_families')} for s in draft['material_states']])
    await append_paper_history_event(session, paper_id=paper.id, paper_revision=paper.content_revision,
        event_type='modified', actor_user_id=user.id, actor_username_snapshot=user.username,
        operation_id=operation_id, classification_snapshot=jsonable_encoder({
            'revision_submission': classifications, 'previous_definition_events': definition_history}))
    saved.draft, saved.submitted_revision = None, paper.content_revision
    await session.run_sync(lambda s: science.delete_target(s, 'revision', saved.revision_id))
    await session.flush()
    return dict(ok=True, paper_id=paper.id, content_revision=paper.content_revision, review_status='pending')
