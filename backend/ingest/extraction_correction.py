"""仅在解析自有草稿中纠正有唯一原文答案的候选；不写人工审核历史。"""
import copy


def human_protected_keys(session, snapshot):
    """只投影人工决定标记，不读取或复制完整旧来源与历史。"""
    from sqlalchemy import select
    from backend import models
    table = models.ScientificEvidenceCheck
    rows = session.execute(select(table.item_key, table.result['field_decision'],
        table.result['human_confirmed'], table.result['source_kind']).where(
        table.target == snapshot['target'], table.target_id == snapshot['target_id'],
        table.item_key.in_([r['item_key'] for r in snapshot['records']]))).all()
    return {key for key, decision, confirmed, source_kind in rows
            if decision or confirmed in (True, 1, 'true') or source_kind == 'human_review'}


def correct_extracted_fields(snapshot, draft, results, *, rebuild, evaluate, cancelled=lambda: False,
                             protected_keys=(), protected_fields=()):
    from backend.database import SessionLocal
    from . import property_evidence as ev
    from .field_candidates import patched_draft
    from .field_review import changed_keys
    from .evidence_proposals import checked_proposal, validate_domain_values
    protected = set(protected_keys) | changed_keys(snapshot) | {
        e['item_key'] for e in snapshot.get('_field_change_events') or [] if e.get('item_key')}
    def check_cancelled(*_args):
        if cancelled():
            raise InterruptedError('解析自纠已取消')
    current, output = copy.deepcopy(draft), dict(results)
    for record in snapshot['records']:
        if cancelled():
            raise InterruptedError('解析自纠已取消')
        previous = results.get(record['key']) or {}
        latest = next((r for r in snapshot['records'] if r['item_key'] == record['item_key']), None)
        if not latest or latest['key'] != record['key']:
            continue
        if (record['item_key'] in protected or record['field'] in protected_fields
                or record.get('paper_source_hash') or record.get('human_modified') or previous.get('human_confirmed')
                or previous.get('field_decision') or previous.get('source_kind') == 'human_review'
                or previous.get('status') not in {'unsupported', 'uncertain', 'missing'}):
            continue
        proposal = checked_proposal(record, previous.get('proposal'), snapshot['chunks'])
        if (not proposal or not proposal.get('unique') or not proposal.get('evidences')
                or proposal.get('basis_kind') not in {'paper_quote', 'paper_inference'}
                or proposal.get('basis_kind') == 'paper_quote' and not proposal['supported']):
            continue
        try:
            with SessionLocal() as session:
                validate_domain_values(session, record, proposal['values'])
            candidate = patched_draft(current, record, proposal['values'])
            updated = rebuild(candidate)
            row = next((r for r in updated['records'] if r['item_key'] == record['item_key']), None)
            if not row or row.get('current_value') == record.get('current_value'):
                continue
            windows = [evaluate([row], sources, 'check', source_catalog=updated['chunks'],
                                on_partial=check_cancelled)[0]
                       for sources in ev.source_batches(updated['chunks'])]
            check_cancelled()
            combined = ev.aggregate_candidates([row], {row['key']: windows}, {row['key']: []},
                next((r.get('model') for r in windows if r.get('model')), ''), updated['chunks'])
            verified = ev.checked_result(row, combined[row['key']], updated['chunks'])
            if verified.get('status') != 'supported' or verified.get('stale'):
                continue
        except InterruptedError:
            raise
        except Exception as exc:
            if cancelled() or type(exc).__name__ == 'UploadCancelled':
                raise
            continue
        current = candidate
        # 所有相关结论以最终草稿重新投影；不会把旧上下文的通过移给新条件。
        before_by_item = {r['item_key']: r for r in snapshot['records']}
        for target in updated['records']:
            old = before_by_item.get(target['item_key'])
            if old and old['key'] != target['key']:
                output.pop(old['key'], None)
        verified.pop('proposal', None)
        output[row['key']] = {**verified, 'auto_corrected': True}
        snapshot = updated
    return current, snapshot, output
