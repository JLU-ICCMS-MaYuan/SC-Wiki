"""从既有判断投影真正科学问题；不另调分类模型、不改变科学值。"""
from copy import deepcopy

SCIENTIFIC_REASONS = {'source_conflict', 'assignment_ambiguous', 'subject_ambiguous'}


def dependent_records(records, targets):
    """沿现有字段依赖图取闭包；同属一个状态本身不构成依赖。"""
    from .review_dependencies import record_inputs
    from .state_field_review import SCOPE_FIELDS
    selected = {t['item_key'] for t in targets}
    changed = True
    while changed:
        changed = False
        owners = [r for r in records if r['item_key'] in selected]
        for row in records:
            if row['item_key'] in selected:
                continue
            for owner in owners:
                field = owner['field'].split('.')[-1]
                same_state = bool(row.get('state_key') and row.get('state_key') == owner.get('state_key'))
                direct = same_state and not owner.get('record_key') and field in SCOPE_FIELDS and field in (
                    row.get('state_dependencies') or (row.get('state_review_context') or {}))
                record = row.get('scientific_record') or (row.get('claim') or {}).get('record') or {}
                same_record = same_state and row.get('record_key') and row.get('record_key') == owner.get('record_key')
                direct |= bool(same_record and owner.get('record_field') in record_inputs(record, row.get('record_field') or ''))
                direct |= bool(row.get('dependency') and row['dependency'] in {owner.get('key'), owner['item_key']})
                if direct:
                    selected.add(row['item_key']); changed = True
                    break
    return [row for row in records if row['item_key'] in selected and row['item_key'] not in {t['item_key'] for t in targets}]


def route_problem(record, fact, sources):
    if fact.get('review_error') or fact.get('technical_error'):
        return {'kind': 'technical_unfinished', 'requires_human': False, 'reason': fact.get('review_error') or fact['technical_error']}
    if fact.get('requires_human') and fact.get('reason_code') in SCIENTIFIC_REASONS:
        ids = fact.get('source_ids') or []
        import json
        distinct = {json.dumps({k: sources[i].get(k) for k in ('file_id', 'block_id', 'chunk_index', 'content', 'quote')},
                              sort_keys=True, ensure_ascii=False) for i in ids if i in sources}
        if (not ids or any(i not in sources for i in ids) or not str(fact.get('checked_context') or '').strip()
                or not str(fact.get('reason') or '').strip()
                or fact['reason_code'] == 'source_conflict' and len(distinct) < 2):
            return {'kind': 'technical_unfinished', 'requires_human': False, 'reason': '科学问题缺少实际已读依据或完整查证关系'}
        return {'kind': 'human_required', 'requires_human': True, 'reason_code': fact['reason_code'],
            'reason': fact['reason'], 'checked_context': fact['checked_context'],
            'target_refs': [{k: deepcopy(record[k]) for k in ('item_key', 'state_key', 'module_key', 'record_key',
                'candidate_id', 'reading_id', 'field', 'content_hash', 'source_hash') if k in record}],
            'source_refs': [deepcopy(sources[i]) for i in dict.fromkeys(ids)]}
    if fact.get('status') == 'supported' and fact.get('unique') is True:
        return {'kind': 'resolved', 'requires_human': False}
    if fact.get('status') == 'missing' and record.get('empty_allowed') and fact.get('sources_read_complete'):
        return {'kind': 'not_reported', 'requires_human': False}
    return None
