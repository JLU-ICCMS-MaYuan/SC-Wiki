"""逐字段人工决定。保存说明与认可现有内容使用不同契约。"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from . import property_evidence as ev, scientific_evidence as science
from .field_review import changed_keys, field_version, reusable, valid_field_decision


def display_reason(value):
    return str(value or '').removeprefix('已纠正角色；只保存新候选供人工比较；')


def review_token(snapshot, record, result):
    return ev.digest([snapshot['target'], snapshot['target_id'], field_version(record), {key: result.get(key) for key in
        ('status', 'reason', 'ai_reason', 'evidences', 'supplemental_evidences', 'source_associations',
         'proposal', 'provenance', 'field_decision', 'review_started_at')}])


def modification_requires_model(snapshot, record, result):
    modified = record['item_key'] in changed_keys(snapshot) or bool(record.get('paper_source_hash'))
    return modified and not (reusable(record, result) and result.get('status') == 'supported')


def detail(snapshot, cached):
    from .state_field_review import initial_state_value, scope_matches
    if len(snapshot['records']) != 1:
        ev.fail('evidence_field_missing', '字段已删除或无法唯一定位，请重新打开')
    record = snapshot['records'][0]
    previous = cached.get(record['key']) or {}
    exact = reusable(record, previous)
    same_value = science.canonical(previous.get('current_value')) == science.canonical(record.get('current_value'))
    modified = modification_requires_model(snapshot, record, previous)
    # 历史引句仍可阅读，但不能冒充当前内容已核对；依据不可读取与没有依据分开。
    displayed = {**record, **previous, 'key': record['key'], 'item_key': record['item_key'],
                 'field': record['field'], 'fields': record['fields'], 'current_value': record.get('current_value'),
                 'status': previous.get('status', 'unchecked'), 'pending_review': modified or not same_value,
                 'human_modified': record['item_key'] in changed_keys(snapshot) or bool(record.get('paper_source_hash')),
                 'stale': bool(previous) and not exact,
                 'evidences': deepcopy(previous.get('evidences') or record.get('evidences') or []),
                 'reason': previous.get('reason') or '', 'ai_reason': previous.get('ai_reason') or previous.get('reason') or ''}
    displayed['human_confirmed'] = valid_field_decision(record, previous, 'approve')
    displayed['automatic_source_lookup'] = initial_state_value(snapshot, record)
    if displayed['automatic_source_lookup']:
        displayed['human_modified'] = False  # 原值与创建归因仍在审计中；不展示逐项人工补证门。
    if not valid_field_decision(record, previous):
        displayed.pop('field_decision', None)
    # 处理日志不作为科学解释；原始文字仍留在数据库与历史。
    displayed['ai_reason'] = display_reason(displayed['ai_reason'])
    displayed['reason'] = display_reason(displayed['reason'])
    invalid_derived = record.get('kind') == 'derived' and not (record.get('provenance') or {}).get('verified')
    unresolved = (not displayed['pending_review'] and not displayed['stale']
                  and (record.get('required', True) or displayed['human_modified']
                       or (displayed.get('field_decision') or {}).get('action') == 'reject')
                  and displayed['status'] in {'unsupported', 'uncertain', 'missing'})
    return {'record': displayed, 'review_token': review_token(snapshot, record, previous),
            'can_approve': unresolved and not modified and not invalid_derived and previous.get('source_kind') != 'program'
                           and scope_matches(record, previous),
            'source_state': 'historical' if previous and not exact else 'available' if displayed['evidences'] else 'empty'}


def decide(session, snapshot, cached, actor, action, expected_token):
    view = detail(snapshot, cached)
    record = snapshot['records'][0]
    previous = cached.get(record['key']) or {}
    if valid_field_decision(record, previous, action):
        return view  # 同一版本重复点击不追加决定、不重新保存科学数据。
    if expected_token != view['review_token']:
        ev.fail('evidence_stale', '当前字段或依据已变化，请重新打开后审核；输入已保留')
    if action == 'approve' and not view['can_approve']:
        ev.fail('evidence_review_required', '人工修改尚未通过模型核对，或存在程序输入错误；请保存后提交或主动核对')
    if action == 'approve':
        from .evidence_proposals import valid_value
        if record.get('field_schema') and not valid_value(record.get('current_value'), record['field_schema']):
            ev.fail('evidence_invalid_value', '程序检查：当前字段格式不合法，请先修正输入')
    now = datetime.now(timezone.utc).isoformat()
    decision = {'contract': 'field-review-v2', 'action': action, 'actor_user_id': actor.id,
                'actor_name': getattr(actor, 'username', ''), 'occurred_at': now,
                'content_hash': record['content_hash'], 'source_hash': record['source_hash']}
    result = {**previous, 'status': 'supported' if action == 'approve' else 'uncertain',
              'stale': False, 'pending_review': False, 'field_decision': decision,
              'human_confirmed': action == 'approve', 'check_method': 'human',
              'state_review_context': record.get('state_review_context'),
              'machine_status': previous.get('machine_status', previous.get('status', 'unchecked')),
              'reason': previous.get('reason') or '', 'ai_reason': view['record']['ai_reason'],
              'evidences': view['record']['evidences'],
              'source_kind': previous.get('source_kind') or 'unknown',
              'resolved_generation_issue': deepcopy(record.get('generation_issue')) if action == 'approve' else None}
    result['audit_events'] = [*previous.get('audit_events', []), {
        'id': uuid4().hex, 'kind': 'human_review', 'occurred_at': now,
        'actor': {'kind': 'human', 'user_id': actor.id, 'name': getattr(actor, 'username', '')},
        'summary': '人工审核通过，保留现有值及依据' if action == 'approve' else '人工审核不通过，待修改',
        'content_hash': record['content_hash'], 'source_hash': record['source_hash'], 'decision': decision}]
    science.save_results(session, snapshot, {record['key']: result}, actor.id, update_decision=True)
    return detail(snapshot, {record['key']: {**record, **result, 'stored_result': True}})
