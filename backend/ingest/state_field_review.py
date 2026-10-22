"""状态基本字段的适用范围与首次新增查证；不修改科学值或人工决定。"""
from copy import deepcopy
from datetime import datetime, timezone


SCOPE_FIELDS = ('material', 'material_name', 'pressure_value_gpa', 'pressure_min_gpa',
                'pressure_max_gpa', 'reported_space_group_symbol', 'state_kind',
                'structure_optimization', 'temperature_value_k', 'magnetic_field_t')


def context(state):
    return {key: deepcopy(state.get(key)) for key in SCOPE_FIELDS}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def bind_scope_events(snapshot):
    from .scientific_evidence import item_identity
    events = snapshot.get('_field_change_events') or []
    for record in snapshot['records']:
        if not record.get('state_review_context'):
            continue
        identity = item_identity('state', record['state_key'])
        keys = {item_identity(identity, field) for field in SCOPE_FIELDS}
        changed = [e.get('occurred_at') for e in events if e.get('item_key') in keys
                   and e.get('before_value') != e.get('after_value')]
        record['_state_scope_changed_at'] = max(changed, key=timestamp) if changed else None


def scope_matches(record, result):
    scope = record.get('state_review_context')
    if not scope:
        return True
    if result.get('state_review_context') is not None:
        return result['state_review_context'] == scope
    # 有界兼容：不跨字段/状态继承；旧摘要匹配之外，较晚的范围编辑必须使旧结果失效。
    if result.get('state_key') not in (None, record.get('state_key')):
        return False
    changed = record.get('_state_scope_changed_at')
    reviewed = result.get('review_started_at') or (result.get('field_decision') or {}).get('occurred_at')
    return not changed or bool(reviewed and timestamp(reviewed) >= timestamp(changed))


def initial_state_value(snapshot, record):
    """仅有已证明的整行创建事件且值仍相同时，免除首次查证的人工材料前置门。"""
    from .scientific_evidence import canonical, populated
    if not record.get('state_key') or not populated(record.get('current_value')) or record.get('paper_source_hash'):
        return False
    events = [e for e in snapshot.get('_field_change_events') or [] if e.get('item_key') == record['item_key']]
    if not events:
        return False
    first = events[0]
    creation = first.get('state_creation')
    if not creation:
        # 历史修复只追加有备份证明的来源说明；不根据 null→值自行推断。
        proof = next((e for e in snapshot.get('_field_change_events') or []
                      if e.get('kind') == 'state_creation_provenance'
                      and e.get('state_key') == record['state_key']
                      and first.get('id') in (e.get('creation_event_ids') or [])
                      and e.get('backup_sha256')), None)
        creation = proof
    return bool(creation and creation.get('state_key') == record['state_key']
                and canonical(first.get('after_value')) == canonical(record.get('current_value'))
                and not any(e.get('kind') == 'field_change'
                            and canonical(e.get('after_value')) != canonical(first.get('after_value'))
                            for e in events[1:]))
