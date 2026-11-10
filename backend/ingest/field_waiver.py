"""人工免证放行是当前版本的人工决定，不是模型科学结论。"""

MODE = 'without_evidence'


def allowed(record):
    from .empty_field_review import is_empty, allowed as empty_allowed
    from .evidence_proposals import valid_value
    if record.get('kind') in {'structure', 'structure_issue'}:
        return False
    if record.get('kind') == 'derived' and not (record.get('provenance') or {}).get('verified'):
        return False
    if is_empty(record.get('current_value')) and not empty_allowed(record):
        return False
    schema = record.get('field_schema') or next(
        (x['schema'] for x in record.get('editable_fields') or [] if x.get('path') == ''), None)
    return not schema or valid_value(record.get('current_value'), schema)


def active(record, result):
    from .field_review import valid_field_decision
    return ((result or {}).get('field_decision') or {}).get('mode') == MODE and valid_field_decision(record, result, 'approve')


def keys(session, snapshot):
    from .scientific_evidence import load_results
    cached = load_results(session, snapshot, include_stale=True)
    return {r['key'] for r in snapshot['records'] if active(r, cached.get(r['key']))}


def project(record, result):
    if ((result or {}).get('field_decision') or {}).get('mode') != MODE:
        return None
    from .state_field_review import scope_matches
    decision=result['field_decision']
    if (record.get('manual_evidence_provided') or not allowed(record)
            or decision.get('content_hash') != record.get('content_hash')
            or decision.get('waiver_source_hash', decision.get('source_hash')) != record.get('paper_source_hash',record.get('source_hash'))
            or not scope_matches(record,result)):
        return None
    return {**result,'content_hash':record['content_hash'],'source_hash':record['source_hash'],
        'manual_evidence_provided':False,'stale':False,'pending_review':False,
        'field_decision':{**decision,'source_hash':record['source_hash']}}
