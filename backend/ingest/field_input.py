"""侧栏单字段输入契约；背景保留为审计，不作为整篇草稿锁。"""
from copy import deepcopy
from sqlalchemy import select

CONTRACT = 'field-input-v1'


def rows_for(session, snapshot, *, for_update=False):
    from .manual_evidence import ScientificManualEvidence, table_available
    if not table_available(session):
        return []
    query = select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == snapshot['target'],
        ScientificManualEvidence.target_id == str(snapshot['target_id']),
        ScientificManualEvidence.item_key.in_([r['item_key'] for r in snapshot['records']]),
        ScientificManualEvidence.status != 'historical').order_by(
            ScientificManualEvidence.created_at, ScientificManualEvidence.id)
    if snapshot['target'] == 'paper':
        query = query.where(ScientificManualEvidence.paper_revision == int(snapshot.get('review_state', [None, None, 1])[2] or 1))
    return list(session.scalars(query.with_for_update() if for_update else query))


def matching_rows(record, rows, *, working=False):
    from .scientific_evidence import canonical
    from .manual_evidence import _semantic_value
    source = record.get('paper_source_hash', record['source_hash'])
    matched=[r for r in rows if r.item_key == record['item_key'] and r.source_hash == source
            and (working and r.status=='draft' or canonical(r.after_value) == canonical(_semantic_value(record)))]
    drafts=[r for r in matched if r.status=='draft']
    return drafts[-1:] if drafts else matched


def current_manual(session, snapshot, record, *, for_update=False):
    rows = matching_rows(record, rows_for(session, {**snapshot, 'records': [record]}, for_update=for_update),working=bool(snapshot.get('_workdraft_current')))
    drafts = [r for r in rows if r.status == 'draft']
    return (drafts or rows)[-1] if rows else None


def bind(snapshot, session):
    from .property_evidence import digest
    from .scientific_evidence import canonical
    rows = rows_for(session, snapshot)
    for record in snapshot['records']:
        manual = matching_rows(record, rows,working=bool(snapshot.get('_workdraft_current')))
        evidence = [(r.id, r.reason, r.no_evidence_reason,
                     [(i.get('id'), i.get('sha256'), i.get('kind'), i.get('source_description'), i.get('text')) for i in r.items or []])
                    for r in manual]
        inputs=[CONTRACT, snapshot['target'], snapshot['target_id'],record['item_key'],
            canonical(record.get('current_value')),record.get('paper_source_hash',record['source_hash']),evidence]
        context=(record.get('claim') or {}).get('context') or {}
        definition=context.get('definition') or []
        if record.get('record_field') == 'method_code':
            inputs.append(['tc-method-dependencies-v1', record['content_hash']])
        if (record.get('record_field') in {'value_number','payload.parameters.mu_star'} and
                definition and '.predicted_tc.' in str(definition[0])):
            if record['record_field']=='value_number':
                inputs.append(['tc-point-dependencies-v1',record['content_hash']])
            else:
                # μ* 本身沿用单字段背景合同，但不能借用另一 Tc／方法点的通过结论。
                inputs.append(['mu-point-dependencies-v1',canonical(context.get('paired_tc')),
                    context.get('method_code'),definition,context.get('method_identity')])
        record['field_input_token']=digest(inputs)
    return snapshot


def matches(record, result):
    binding = (result or {}).get('field_review_binding') or {}
    return bool(binding.get('contract') == CONTRACT and record.get('field_input_token')
                and binding.get('token') == record['field_input_token'])


def project(record, result):
    """只投影同一字段输入的版本；原任务实际背景仍完整保留在 binding 中。"""
    if not matches(record, result):
        return result
    return {**result, 'content_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'state_review_context': deepcopy(record.get('state_review_context')),
            'stale': False, 'pending_review': False}


def select_field(snapshot, item_key):
    from .property_evidence import fail
    records = [r for r in snapshot['records'] if r['item_key'] == item_key or r['key'] == item_key]
    if len(records) != 1:
        fail('evidence_field_missing', '当前字段已删除或身份不唯一，输入已保留')
    return {**snapshot, 'records': records}


def binding(snapshot):
    r = snapshot['records'][0]
    return {'workdraft_epoch': snapshot.get('_workdraft_epoch'), 'contract': CONTRACT, 'token': r['field_input_token'], 'item_key': r['item_key'],
            'background': deepcopy((r.get('claim') or {}).get('context')),
            'state_review_context': deepcopy(r.get('state_review_context'))}


def manual_version(snapshot):
    from .property_evidence import digest, fail
    from .scientific_evidence import canonical
    if len(snapshot['records']) != 1:
        fail('manual_field_not_found', '当前字段已删除或无法唯一定位，人工输入已保留')
    r = snapshot['records'][0]
    return 'manual-field-v1:' + digest([snapshot['target'], snapshot['target_id'], r['item_key'], snapshot.get('_workdraft_epoch'),
        canonical(r.get('current_value')), r.get('paper_source_hash', r['source_hash'])])


def check_manual_version(snapshot, expected):
    from .property_evidence import fail
    if expected.startswith('manual-field-v1:'):
        if manual_version(snapshot) != expected:
            fail('manual_evidence_stale', '当前字段或原文来源已变化，输入已保留')
        snapshot['_manual_field_scope'] = True
    elif snapshot['version'] != expected:
        fail('manual_evidence_stale', '字段或来源已变化，请刷新后重新填写')
