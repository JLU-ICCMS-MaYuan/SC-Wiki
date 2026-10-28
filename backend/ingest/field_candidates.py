"""字段候选与人工采纳。仅消费已有模型结果，绝不调用模型。"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from . import property_evidence as ev, scientific_evidence as science
from . import evidence_proposals as proposals
from .field_review import field_version, reusable

PREFIX = 'field-candidate:'


def capture(record, result, started_at):
    """只由主动单字段任务调用；聚合后的候选已完成类型与出处定位。"""
    proposal = result.get('proposal')
    if not proposal or not str(proposal.get('explanation') or '').strip():
        return None
    candidate = {**deepcopy(proposal), 'content_hash': record['content_hash'],
                 'source_hash': record['source_hash'], 'review_started_at': started_at,
                 'model': result.get('model'), 'origin': 'field'}
    candidate['id'] = ev.digest(candidate)
    return candidate


def preserve_candidate(previous, incoming):
    """保留人工通过时也保存本次主动产生的候选，较早任务不能倒盖。"""
    candidate = incoming.get('field_candidate')
    if not candidate or candidate.get('origin') != 'field':
        return deepcopy(previous)
    from .scientific_evidence import _review_time
    decision = previous.get('field_decision') or {}
    if decision and _review_time(candidate.get('review_started_at')) <= _review_time(decision.get('occurred_at')):
        return deepcopy(previous)
    old = previous.get('field_candidate') or {}
    if _review_time(candidate.get('review_started_at')) < _review_time(old.get('review_started_at')):
        return deepcopy(previous)
    result = deepcopy(previous)
    result['field_candidate'] = deepcopy(candidate)
    event_id = 'candidate:' + candidate['id']
    events = result.setdefault('audit_events', [])
    if not any(e.get('id') == event_id for e in events):
        events.append({'id': event_id, 'kind': 'ai_review', 'occurred_at': candidate.get('review_started_at'),
                       'actor': {'kind': 'ai', 'model': candidate.get('model')},
                       'summary': '主动模型核对生成候选，保留当前值及审核决定', 'proposal': deepcopy(candidate)})
    return result


def candidate_view(snapshot, record, result, draft):
    candidate = result.get('field_candidate')
    if candidate and (result.get('applied_candidate') or {}).get('id') != candidate.get('id'):
        valid = (not result.get('stale') and all(candidate.get(k) == record.get(k)
                 for k in ('content_hash', 'source_hash')))
        return {**deepcopy(candidate), 'can_apply': valid, 'historical': not valid,
                'token': ev.digest([snapshot['target'], snapshot['target_id'], field_version(record), candidate])}
    legacy = next((i for i in draft.get('generation_issues') or []
                   if i.get('field') == record['field'] and i.get('candidate') is not None), None)
    if legacy and not result.get('resolved_generation_issue'):
        return {'values': {'': deepcopy(legacy['candidate'])}, 'historical': True, 'can_apply': False,
                'explanation': '', 'evidences': [], 'origin': 'legacy'}
    return None


def pending_application(session, snapshot, user, current):
    """重开页面也可恢复已保存但尚未确认的应用；只读取当前字段准备记录。"""
    from sqlalchemy import select
    from backend import models
    record = snapshot['records'][0]
    table = models.ScientificEvidenceCheck
    rows = session.scalars(select(table).where(table.target == snapshot['target'],
        table.target_id == snapshot['target_id'], table.item_key == record['item_key']).order_by(table.id.desc()))
    for row in rows:
        prepared = (row.resolutions or {}).get(PREFIX + str(user.id)) or {}
        if not prepared or (current.get('applied_candidate') or {}).get('preparation_id') == prepared.get('id'):
            continue
        from .scientific_evidence import _review_time
        if (reusable(record, current) and current.get('field_decision')
                and _review_time(current['field_decision'].get('occurred_at')) > _review_time(prepared.get('created_at'))):
            continue
        if (prepared.get('expected_version') == list(field_version(record))
                and prepared.get('expected_claim') == science.canonical(record['claim'])
                and (row.result.get('field_candidate') or {}).get('id') == prepared['candidate']['id']):
            return {**deepcopy(prepared['candidate']), 'can_apply': True, 'historical': False,
                    'preparation_id': prepared['id']}
    return None


def patched_draft(draft, record, values):
    """与宿主 EvidencePatch 同语义，按稳定身份投影预期内容，不写存储。"""
    updated = deepcopy(draft)
    target = updated.get('paper', {})
    targets = None
    if record.get('state_key'):
        target = next((s for s in updated.get('material_states', []) if s.get('state_key') == record['state_key']), None)
        if target is None:
            ev.fail('evidence_stale', '候选对应的材料状态已变化')
        if record.get('record_key'):
            module = next((m for m in target.get('property_modules', []) if m.get('module_key') == record.get('module_key')), {})
            target = next((r for r in module.get('records', []) if r.get('record_key') == record['record_key']), None)
            if target is None:
                ev.fail('evidence_stale', '候选对应的科学记录已变化')
            if record.get('record_group_key'):
                targets = [r for r in module['records'] if (r.get('payload', {}).get('tc_group') or {}).get('group_key') == record['record_group_key']]
    for path, value in values.items():
        if record.get('record_field') and path == '':
            from .property_field_review import write_path
            for member in targets or [target]:
                write_path(member, record['record_field'], deepcopy(value))
        else:
            name = path or record['field'].rsplit('.', 1)[-1]
            if name in {'material_families', 'structure_families'}:
                old = target.get(name) or []
                target[name] = [next((f for f in old if (f.get('name') or f.get('name_zh')) == v),
                                    {'name': v, 'name_zh': v, 'status': 'pending',
                                     **({'is_primary': False} if name == 'structure_families' else {})}) for v in value]
            else:
                target[name] = deepcopy(value)
    if record.get('record_key'):
        from .property_modules import normalize_current_tc_value
        target.update(normalize_current_tc_value(target))
    return updated


def prepare(session, snapshot, cached, draft, user, token, project):
    record = snapshot['records'][0]
    previous = cached.get(record['key']) or {}
    view = candidate_view(snapshot, record, previous, draft)
    if not view or not view.get('can_apply') or view.get('token') != token:
        ev.fail('evidence_stale', '候选或当前内容已变化，请重新打开字段')
    candidate = previous['field_candidate']
    proposals.validate_values(record, candidate['values'])
    proposals.validate_domain_values(session, record, candidate['values'])
    projected = project(patched_draft(draft, record, candidate['values']))
    if len(projected['records']) != 1:
        ev.fail('evidence_stale', '候选无法唯一对应保存后的字段')
    expected = projected['records'][0]
    rows = proposals.rows_for(session, snapshot, True)
    row = next((r for r in reversed(rows) if proposals.row_matches(r, record)), None)
    if row is None:
        ev.fail('evidence_stale', '候选的原始核对记录已失效')
    stored = (row.resolutions or {}).get(PREFIX + str(user.id)) or {}
    if stored.get('candidate_token') == token:
        return stored['response']
    preparation_id = uuid4().hex
    patch = {k: record.get(k) for k in ('key', 'item_key', 'field', 'state_key', 'module_key',
                                      'record_key', 'record_field', 'record_field_key', 'record_group_key')}
    response = {'preparation_id': preparation_id, 'patches': [{**patch, 'values': candidate['values']}]}
    preparation = {'id': preparation_id, 'candidate_token': token, 'candidate': deepcopy(candidate),
                   'created_at': datetime.now(timezone.utc).isoformat(),
                   'expected_version': list(field_version(expected)), 'expected_claim': science.canonical(expected['claim']),
                   'original_value': record.get('current_value'), 'response': response}
    row.resolutions = {**(row.resolutions or {}), PREFIX + str(user.id): preparation}
    return response


def finalize(session, snapshot, user, preparation_id):
    record = snapshot['records'][0]
    cached = science.load_results(session, snapshot, user.id, include_stale=True)
    current = cached.get(record['key']) or {}
    if ((current.get('applied_candidate') or {}).get('preparation_id') == preparation_id
            and (current.get('field_decision') or {}).get('actor_user_id') == user.id and reusable(record, current)):
        return current
    rows = proposals.rows_for(session, snapshot, True)
    original = next((r for r in rows
                        if r.item_key == record['item_key'] and
                        ((r.resolutions or {}).get(PREFIX + str(user.id)) or {}).get('id') == preparation_id), None)
    preparation = (original.resolutions or {}).get(PREFIX + str(user.id)) if original else None
    if (not preparation or list(field_version(record)) != preparation['expected_version']
            or science.canonical(record['claim']) != preparation['expected_claim']):
        ev.fail('evidence_stale', '保存内容或来源与候选不一致，未确认通过；请重新打开字段')
    candidate = preparation['candidate']
    from .scientific_evidence import _review_time
    if ((original.result.get('field_candidate') or {}).get('id') != candidate['id']
            or reusable(record, current) and current.get('field_decision')
            and _review_time(current['field_decision'].get('occurred_at')) > _review_time(preparation['created_at'])):
        ev.fail('evidence_stale', '候选或人工决定已更新，未覆盖最新决定')
    now = datetime.now(timezone.utc).isoformat()
    decision = {'contract': 'field-review-v2', 'action': 'approve', 'actor_user_id': user.id,
                'actor_name': getattr(user, 'username', ''), 'occurred_at': now,
                'content_hash': record['content_hash'], 'source_hash': record['source_hash']}
    result = {**record, 'status': 'supported', 'reason': candidate['explanation'], 'ai_reason': candidate['explanation'],
              'evidences': deepcopy(candidate.get('evidences') or []), 'field_decision': decision,
              'human_confirmed': True, 'source_kind': 'human_review', 'check_method': 'human',
              'adopted_basis': candidate.get('basis_kind'), 'pending_review': False, 'stale': False,
              'state_review_context': record.get('state_review_context'),
              'resolved_generation_issue': deepcopy(record.get('generation_issue')),
              'applied_candidate': {**deepcopy(candidate), 'preparation_id': preparation_id},
              'decision': {'actor_user_id': user.id, 'accepted': True, 'human_confirmed': True,
                           'original_value': preparation['original_value'], 'preparation_id': preparation_id},
              'history': [*deepcopy(original.result.get('history') or []),
                          {k: deepcopy(original.result.get(k)) for k in ('current_value', 'status', 'reason',
                           'ai_reason', 'evidences', 'field_decision', 'content_hash', 'source_hash')}],
              'audit_events': [{'id': preparation_id, 'kind': 'human_review', 'occurred_at': now,
                                'actor': {'kind': 'human', 'user_id': user.id, 'name': getattr(user, 'username', '')},
                                'summary': '应用 AI 候选值并认可 AI 理由与依据',
                                'before_value': preparation['original_value'], 'after_value': record.get('current_value'),
                                'proposal': deepcopy(candidate), 'decision': decision}]}
    science.save_results(session, snapshot, {record['key']: result}, user.id, update_decision=True)
    return result
