"""定向补齐已提交 La–Sc–H 的元数据、原审核决定及快照收尾；默认事务回滚。"""
from __future__ import annotations
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TASK = 'c16cc627a0c04dc8ad4289624d1da80a'
PAPER = 271
OPERATION = 'submission-completion:271:1'


def dump(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n')


def row_data(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


async def repair(output, apply):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from backend import models
    from backend.rag import database as adb
    from backend.ingest import upload_tasks as uploads, scientific_evidence as science, property_evidence as ev
    from backend.ingest.field_review import valid_field_decision, bind_support_versions
    from backend.ingest.field_source_metadata import remember
    from backend.manual_evidence_models import ScientificManualEvidence as Manual
    from backend.services.paper_history import append_paper_history_event
    from backend.services.classification_catalog import save_paper_material_families
    engine = create_async_engine(adb.database_url, poolclass=NullPool)
    output.mkdir(parents=True, exist_ok=True)
    report = {'task_id': TASK, 'paper_id': PAPER, 'applied': False}
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            try:
                async with factory() as db:
                    paper = await db.get(models.Paper, PAPER, with_for_update=True)
                    if not paper or paper.upload_task_id != TASK or paper.content_revision != 1 or paper.review_status != 'pending':
                        raise ValueError('目标或审核版本已变化，停止定向修正')
                    done = await db.scalar(select(models.PaperHistoryEvent.id).where(models.PaperHistoryEvent.operation_id == OPERATION))
                    if done:
                        report.update(status='already_repaired', applied=True)
                        return report
                    state, raw = uploads.get_state(TASK), uploads.get_draft(TASK)
                    if not state or raw is None or int(state['user_id']) != paper.uploaded_by_user_id:
                        raise ValueError('缺少原上传快照，拒绝猜测恢复')
                    source = ev.upload_snapshot(TASK, paper.uploaded_by_user_id)
                    original = {r['item_key']: r for r in source['records']}
                    check_rows = list((await db.scalars(select(models.ScientificEvidenceCheck).where(
                        models.ScientificEvidenceCheck.target == 'upload', models.ScientificEvidenceCheck.target_id == TASK))).all())
                    checks = {}
                    for row in sorted(check_rows, key=lambda r: r.id):
                        current = original.get(row.item_key)
                        result = {**deepcopy(row.result), 'content_hash': row.content_hash, 'source_hash': row.source_hash}
                        if current and row.content_hash == current['content_hash'] and result.get('field_decision'):
                            checks[row.item_key] = result
                    for key, current in original.items():
                        result = checks.get(key) or {}
                        if not valid_field_decision(result, result, 'approve') or result.get('status') != 'supported':
                            raise ValueError('字段缺少原有人工通过：' + current['field'])
                        if current.get('paper_source_hash', current['source_hash']) != result.get('paper_source_hash', result['source_hash']):
                            raise ValueError('原审核来源已变化：' + current['field'])
                    files = list((await db.scalars(select(models.PaperFile).where(models.PaperFile.paper_id == PAPER))).all())
                    mapping = {}
                    for file in state['files']:
                        matches = [f for f in files if f.sha256 == file['sha256'] and f.role == file['role']]
                        if len(matches) != 1:
                            raise ValueError('正式文件与原文件不能唯一对应')
                        mapping[file['file_id']] = matches[0].id
                    before_checks = list((await db.scalars(select(models.ScientificEvidenceCheck).where(
                        models.ScientificEvidenceCheck.target == 'paper', models.ScientificEvidenceCheck.target_id == str(PAPER)))).all())
                    notes = list((await db.scalars(select(Manual).where(Manual.target == 'paper', Manual.target_id == str(PAPER)))).all())
                    events = list((await db.scalars(select(models.PaperHistoryEvent).where(models.PaperHistoryEvent.paper_id == PAPER))).all())
                    if any(event.event_type != 'uploaded' for event in events):
                        raise ValueError('正式论文已有后续人工操作，停止覆盖')
                    before_values = {}
                    for name, model in [('states', models.MaterialState), ('records', models.PropertyRecord),
                                         ('structures', models.StructureModel), ('spectra', models.SpectrumCollection)]:
                        before_values[name] = [row_data(row) for row in (await db.scalars(select(model).where(model.paper_id == PAPER))).all()]
                    if apply:
                        backup = output / 'before.json'
                        if backup.exists():
                            raise ValueError('修正备份已存在，请检查上次执行结果')
                        dump(backup, {'paper': row_data(paper), 'state': state, 'draft': raw, 'values': before_values,
                                      'checks': [row_data(r) for r in before_checks], 'manual': [row_data(r) for r in notes],
                                      'events': [row_data(r) for r in events]})
                    metadata = {'paper': {k: raw['paper'].get(k) for k in ('material_families', 'co_first_authors', 'corresponding_authors')},
                                'material_states': [{k: st.get(k) for k in ('state_key', 'structure_families')} for st in raw['material_states']]}
                    await append_paper_history_event(db, paper_id=PAPER, paper_revision=1, event_type='modified',
                        actor_user_id=paper.uploaded_by_user_id, actor_username_snapshot='mayuan（授权系统修复）', operation_id=OPERATION,
                        classification_snapshot={'upload_submission': metadata,
                            'submission_repair': {'source_task': TASK, 'reason': '补齐提交时遗漏元数据并迁移原有审核决定；不重新人工审核'}})
                    await save_paper_material_families(db, paper, [x for x in raw['paper']['material_families'] if x.get('id') is not None])
                    formal = await db.run_sync(lambda s: ev.paper_snapshot(s, PAPER, 0, '', check_access=False))
                    if not science.source_transfer_matches(source['chunks'], formal['chunks'], mapping):
                        raise ValueError('正式原文与已审核原文不一致')
                    provenance = {row['field']: science.rebind_source_references(row.get('provenance'), formal['chunks'], mapping)
                                  for row in checks.values() if row['field'] in {'paper.theoretical_subtype', 'paper.keywords_tags'}}
                    formal = await db.run_sync(lambda s: ev.paper_snapshot(s, PAPER, 0, '', check_access=False, review_provenance=provenance))
                    current_fields = {r['item_key']: r for r in formal['records']}
                    for key, previous in checks.items():
                        current = current_fields.get(key)
                        if current is None or current['content_hash'] != previous['content_hash']:
                            raise ValueError('正式内容与原审核值不一致：' + previous['field'])
                        active = [note for note in notes if note.item_key == key and note.value_hash == previous['content_hash']
                                  and note.status != 'historical' and (note.items or note.reason or note.no_evidence_reason)]
                        if active:
                            versions = sorted((note.id, ev.digest([note.reason, note.no_evidence_reason,
                                [(i.get('sha256'), i.get('kind'), i.get('source_description')) for i in note.items or []]])) for note in active)
                            if not previous.get('paper_source_hash') or ev.digest([previous['paper_source_hash'], versions]) != previous['source_hash']:
                                raise ValueError('人工依据在通过后发生变化：' + previous['field'])
                            for note in active:
                                note.source_hash = current.get('paper_source_hash', current['source_hash'])
                    await db.flush()
                    await db.run_sync(lambda s: bind_support_versions(formal, s))
                    prior_by_item = {}
                    for row in sorted(before_checks, key=lambda r: r.id): prior_by_item[row.item_key] = row.result
                    transferred = {}
                    for current in formal['records']:
                        old = checks[current['item_key']]
                        moved = science.transfer_result(current, old, formal['chunks'], mapping, source_transfer_verified=True)
                        history = moved.setdefault('history', [])
                        for entry in prior_by_item.get(current['item_key'], {}).get('history') or []:
                            if entry not in history: history.append(deepcopy(entry))
                        transferred[current['key']] = moved
                    await db.run_sync(lambda s: science.save_results(s, formal, transferred, paper.uploaded_by_user_id))
                    await db.run_sync(lambda s: remember(s, formal, paper.uploaded_by_user_id))
                    await db.flush()
                    reread = await db.run_sync(lambda s: ev.paper_snapshot(s, PAPER, 0, '', check_access=False))
                    restored = await db.run_sync(lambda s: science.load_results(s, reread, paper.uploaded_by_user_id))
                    confirmed = sum(valid_field_decision(r, restored.get(r['key']), 'approve') for r in reread['records'])
                    if confirmed != len(checks):
                        raise ValueError(f'正式审核回读不完整：{confirmed}/{len(checks)}')
                    for name, model in [('states', models.MaterialState), ('records', models.PropertyRecord),
                                         ('structures', models.StructureModel), ('spectra', models.SpectrumCollection)]:
                        values = [row_data(row) for row in (await db.scalars(select(model).where(model.paper_id == PAPER))).all()]
                        if values != before_values[name]:
                            raise ValueError('科学数据发生意外变化：' + name)
                    report.update(status='verified', fields=confirmed, scientific_values_unchanged=True,
                                  original_decisions_preserved=True, pending_classifications_preserved=True)
                    await db.commit()
                if apply:
                    await outer.commit(); report['applied'] = True
                else:
                    await outer.rollback()
            except Exception:
                await outer.rollback()
                raise
        dump(output / ('repair-result.json' if apply else 'dry-run.json'), report)
        return report
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    values = read_config(ROOT); validate_local(values, ROOT); os.environ.update(values)
    from backend.ingest.upload_tasks import upload_task_lock
    with upload_task_lock(TASK):
        report = asyncio.run(repair(args.output.resolve(), args.apply))
        if args.apply:
            from backend.api.rag import _recover_submitted_upload, _artifact_by_paper_id, _validate_review_snapshot
            from backend.ingest.upload_tasks import get_state
            _recover_submitted_upload(TASK, {'paper_id': PAPER, 'paper_revision': 1, 'review_status': 'pending', 'uploaded_by_user_id': 2})
            artifact = _artifact_by_paper_id(PAPER, TASK, 1)
            if not artifact:
                raise RuntimeError('正式快照尚未完成归档，不能报告提交收尾完成')
            _validate_review_snapshot({'task_id': TASK, 'paper_id': PAPER, 'paper_revision': 1}, TASK, artifact[2])
            state = get_state(TASK)
            if state and (state.get('paper_id') != PAPER or state.get('status') != 'submitted'):
                raise RuntimeError('任务仍处于未完成状态')
            report.update(artifact_reader_verified=True, task_finalized=True)
            dump(args.output / 'completed.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
