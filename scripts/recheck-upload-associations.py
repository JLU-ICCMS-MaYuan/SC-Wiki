"""备份后定向核查上传草稿；只更新核对与证据，不采纳科学值建议。"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from sqlalchemy import select
from backend import models
from backend.database import SessionLocal
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.upload_tasks import redis_client, upload_task_lock, get_draft
from backend.rag.llm_context import get_llm_config


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def problem(row):
    return row.get('required') is not False and bool(row.get('stale') or (
        row.get('status') != 'supported' and not (row.get('proposal_draft') or {}).get('accepted')
        and not row.get('human_confirmed') and not (row.get('resolution') or '').strip()))


def scientific_values(draft):
    value = deepcopy(draft)
    def clean(item):
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items() if k not in {'evidence', 'evidences', 'record_checksum'}}
        if isinstance(item, list):
            return [clean(v) for v in item]
        return item
    return ev.digest(clean(value))


def public(snapshot, owner):
    from backend.ingest.pdf_source_pages import current_pdf_results
    with SessionLocal() as db:
        cached = current_pdf_results(db, snapshot, science.load_results(db, snapshot, owner, include_stale=True))
    return ev.public_snapshot(snapshot, cached), cached


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('--apply', action='store_true', help='执行真实模型核对并保存；默认只盘点')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 20:
        parser.error('batch-size 必须在 1～20 之间')
    args.output.mkdir(parents=True, exist_ok=False)
    client = redis_client()
    with upload_task_lock(args.task_id):
        state_raw = client.get(f'upload:{args.task_id}:state')
        draft_raw = client.get(f'upload:{args.task_id}:draft')
        if not state_raw or not draft_raw:
            raise ValueError('只处理当前已存在的草稿，不恢复或重建任务')
        state = json.loads(state_raw)
        owner = int(state['user_id'])
        snap = ev.upload_snapshot(args.task_id, owner)
        before, prior = public(snap, owner)
        original_values = scientific_values(get_draft(args.task_id))
        if args.apply:
            (args.output / 'redis-state.json').write_text(state_raw)
            (args.output / 'redis-draft.json').write_text(draft_raw)
            with SessionLocal() as db:
                saved = db.get(models.ScientificUploadDraft, args.task_id)
                write(args.output / 'mysql-draft.json', ev.row_dict(saved) if saved else None)
                checks = db.scalars(select(models.ScientificEvidenceCheck).where(
                    models.ScientificEvidenceCheck.target == 'upload',
                    models.ScientificEvidenceCheck.target_id == args.task_id)).all()
                write(args.output / 'mysql-checks.json', [ev.row_dict(row) for row in checks])
    selected = {r['key'] for r in before['records'] if problem(r) and r.get('kind') != 'derived'}
    records = [r for r in snap['records'] if r['key'] in selected]
    write(args.output / 'before.json', before)
    write(args.output / 'snapshot.json', snap)
    write(args.output / 'manifest.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in args.output.iterdir() if p.is_file()})
    print(json.dumps({'selected': len(records), 'red_before': sum(problem(r) for r in before['records']),
                      'version': snap['version'], 'output': str(args.output), 'apply': args.apply}), flush=True)
    if not args.apply:
        return
    failures = []
    source_batches = ev.source_batches(snap['chunks'])
    if not source_batches:
        raise ValueError('缺少当前有效来源')
    model = get_llm_config().model
    for start in range(0, len(records), args.batch_size):
        batch = records[start:start + args.batch_size]
        number = start // args.batch_size + 1
        candidates = {r['key']: [] for r in batch}
        errors = {r['key']: [] for r in batch}
        try:
            for window, chunks in enumerate(source_batches):
                evaluated = ev.evaluate_batch(batch, chunks, prior=prior, source_catalog=snap['chunks'],
                    on_response=lambda raw: write(args.output / f'batch-{number:02d}-window-{window:02d}-raw.json', raw))
                write(args.output / f'batch-{number:02d}-window-{window:02d}.json', evaluated)
                for row, result in zip(batch, evaluated):
                    # 不通过脚本替用户采用模型建议。
                    result['proposal'] = None
                    candidates[row['key']].append(result)
                    errors[row['key']].extend(result.get('location_errors') or [])
            results = ev.aggregate_candidates(batch, candidates, errors, model)
            ev.persist_completed_results({**snap, 'records': batch}, results, owner)
            write(args.output / f'batch-{number:02d}-saved.json', results)
            if scientific_values(get_draft(args.task_id)) != original_values:
                raise ValueError('科学值已发生变化，停止后续核对')
            print(json.dumps({'batch': number, 'completed': start + len(batch), 'total': len(records),
                              'statuses': dict(Counter(r['status'] for r in results.values()))}), flush=True)
        except Exception as exc:
            failure = {'batch': number, 'fields': [r['field'] for r in batch], 'error': type(exc).__name__,
                       'detail': str(getattr(exc, 'detail', str(exc)))[:1500]}
            failures.append(failure)
            write(args.output / 'failures.json', failures)
            print(json.dumps(failure, ensure_ascii=False), flush=True)
            current = ev.upload_snapshot(args.task_id, owner)
            if current['version'] != snap['version'] or scientific_values(get_draft(args.task_id)) != original_values:
                break
    after_snapshot = ev.upload_snapshot(args.task_id, owner)
    after, _ = public(after_snapshot, owner)
    write(args.output / 'after.json', after)
    remaining = [{'field': r['field'], 'label': r['label'], 'owner_label': r.get('owner_label'),
                  'status': r['status'], 'stale': r.get('stale'), 'reason': r.get('reason'),
                  'adopted_basis': r.get('adopted_basis'), 'evidences': r.get('evidences'),
                  'source_associations': r.get('source_associations')} for r in after['records'] if problem(r)]
    write(args.output / 'remaining.json', remaining)
    report = {'completed_at': datetime.now(timezone.utc).isoformat(), 'model': model,
              'red_before': sum(problem(r) for r in before['records']), 'red_after': len(remaining),
              'failed_batches': len(failures), 'scientific_values_unchanged': scientific_values(get_draft(args.task_id)) == original_values,
              'association_stale_after': sum(any(a.get('stale') for a in r.get('source_associations') or []) for r in after['records'])}
    write(args.output / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
