"""新审核事件的真实归因；不由存储行创建时间猜测旧事件。"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


def field_change_events(before, after, user):
    """只比较字段自身的值与标注；依赖失效不冒充用户修改。"""
    from .scientific_evidence import canonical
    previous = {r['item_key']: r for r in before['records'] if r.get('kind') == 'field'}
    current = {r['item_key']: r for r in after['records'] if r.get('kind') == 'field'}
    events, operation = [], uuid4().hex
    occurred_at = datetime.now(timezone.utc).isoformat()
    for key in previous.keys() | current.keys():
        old, new = previous.get(key), current.get(key)
        def value(record):
            if record is None:
                return None
            annotation = (record.get('claim', {}).get('context') or {}).get('field_settings')
            return {'value': record.get('current_value'), 'field_settings': annotation}
        if old is not None and new is not None and canonical(value(old)) == canonical(value(new)):
            continue
        record = new or old
        summary = '修改并保存字段' if old and new else '新增字段' if new else '删除字段'
        annotations_changed = old and new and canonical(value(old)['field_settings']) != canonical(value(new)['field_settings'])
        events.append({'id': operation + ':' + key, 'item_key': key, 'field': record['field'], 'label': record['label'],
                       'actor': {'kind': 'human', 'user_id': user.id, 'name': user.username},
                       'occurred_at': occurred_at, 'kind': 'field_change', 'summary': summary,
                       'before_value': deepcopy(old.get('current_value')) if old else None,
                       'after_value': deepcopy(new.get('current_value')) if new else None,
                       **({'before_settings': deepcopy(value(old)['field_settings']),
                           'after_settings': deepcopy(value(new)['field_settings']), 'summary': '修改并保存字段设置'} if annotations_changed else {})})
    return events


def draft_change_events(before, after, user):
    from .property_evidence import complete_snapshot, draft_records
    from .upload_contracts import convert_legacy_scientific_draft
    def snapshot(draft):
        draft = convert_legacy_scientific_draft(deepcopy(draft or {}))
        return complete_snapshot('upload', 'field-diff', draft_records(draft or {}, {}), [], draft or {})
    return field_change_events(snapshot(before), snapshot(after), user)


def merge_events(*groups):
    """服务端事件按ID去重，保留最初记录的归因与时刻。"""
    events = {}
    for group in groups:
        for event in group or []:
            if event.get('id'):
                events.setdefault(event['id'], deepcopy(event))
    return list(events.values())


def append_review_event(session, record, result, previous, actor_id, *, human=False):
    from backend import models
    from .scientific_evidence import canonical
    events = merge_events((previous or {}).get('audit_events'), record.get('audit_events'))
    for event in result.get('audit_events') or []:
        if event.get('id') and not any(e.get('id') == event['id'] for e in events):
            events.append(deepcopy(event))
    action = result.pop('_audit_action', None)
    nonce = result.pop('_audit_event_id', None)
    decision = result.get('decision') or {}
    if human:
        nonce = decision.get('preparation_id')
        user = session.get(models.User, actor_id)
        actor = {'kind': 'human', 'user_id': actor_id,
                 'name': (getattr(user, 'real_name', None) or getattr(user, 'username', None)) if user else None}
        before, after = decision.get('original_value'), record.get('current_value')
        changed = canonical(before) != canonical(after)
        kind, summary = ('change', '修改并保存字段值') if changed else ('human_review', '核对当前字段，保留当前值')
    elif action in {'ai_review', 'auto_fill'} and nonce and result.get('model'):
        actor = {'kind': 'ai', 'model': result['model'], 'requested_by_user_id': actor_id}
        if action == 'auto_fill':
            kind, summary, changed, before, after = 'auto_fill', '从原文关联补入空字段', True, None, record.get('current_value')
        else:
            kind, summary, changed, before, after = 'ai_review', 'AI 核对当前字段，未改值', False, None, None
    else:
        if events:
            result['audit_events'] = events
        return
    if nonce and not any(e.get('id') == nonce for e in events):
        events.append({'id': nonce, 'item_key': record['item_key'], 'field': record['field'], 'label': record['label'],
                       'actor': actor, 'occurred_at': datetime.now(timezone.utc).isoformat(), 'kind': kind,
                       'summary': summary, 'reason': decision.get('reason') if human else result.get('reason'),
                       'content_hash': record.get('content_hash'), 'source_hash': record.get('source_hash'),
                       **({'before_value': deepcopy(before), 'after_value': deepcopy(after)} if changed else {})})
    result['audit_events'] = events
