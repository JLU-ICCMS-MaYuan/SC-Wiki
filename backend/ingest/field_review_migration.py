"""旧字段结论的一次性迁移；只写审核记录，不改变科学值、来源或旧历史。"""
from copy import deepcopy
from sqlalchemy import select
from backend import models
from . import scientific_evidence as science, property_evidence as ev

MARKER = science.item_identity('field-review-independent-v1-migration')


def migrated(session, snapshot):
    return session.scalar(select(models.ScientificEvidenceCheck.id).where(
        models.ScientificEvidenceCheck.target == snapshot['target'],
        models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
        models.ScientificEvidenceCheck.item_key == MARKER).limit(1)) is not None


def migrate(session, snapshot, legacy, actor):
    if migrated(session, snapshot):
        return 0
    existing = science.load_results(session, snapshot, actor)
    historical = science.load_result_history(session, legacy, actor, include_stale=True)
    prior = {}
    for record in legacy['records']:
        old = historical.get(record['key'])
        if not old:
            continue
        checked = ev.checked_result(record, old, legacy['chunks'])
        if checked.get('status') == 'supported' and not checked.get('stale') and checked.get('source_kind') != 'human_review':
            prior[record['item_key']] = checked
    inherited = {}
    for record in snapshot['records']:
        if record['key'] in existing and not existing[record['key']].get('stale'):
            continue
        old = prior.get(record['item_key']) or prior.get(record.get('legacy_item_key'))
        if not old or old['source_hash'] != record['source_hash']:
            continue
        own = old['item_key'] == record['item_key'] and science.canonical(old.get('current_value')) == science.canonical(record.get('current_value'))
        split = record.get('legacy_content_hash') == old['content_hash']
        if not own and not split:
            continue
        inherited[record['key']] = {**deepcopy(old), **record, 'status': 'supported',
            'stored_result': True, 'stale': False, 'evidences': deepcopy(old.get('evidences') or []),
            'reason': old.get('reason') or '', 'ai_reason': old.get('ai_reason'),
            'inherited_from': {'item_key': old['item_key'], 'content_hash': old['content_hash'],
                               'source_hash': old['source_hash'], 'migration': 1}}
    science.save_results(session, snapshot, inherited, actor)
    marker = {'key': MARKER, 'item_key': MARKER, 'content_hash': MARKER, 'source_hash': MARKER,
              'field': '_field_review_migration', 'label': '旧结论迁移', 'current_value': 1}
    science.save_results(session, {**snapshot, 'records': [marker]},
        {MARKER: {'status': 'supported', 'migrated_count': len(inherited)}}, actor)
    return len(inherited)
