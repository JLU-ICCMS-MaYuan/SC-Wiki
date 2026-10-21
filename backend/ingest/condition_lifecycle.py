"""在当前事实和原文上重验条件结论；不改写历史行，不让尝试失败替代反证。"""
from copy import deepcopy

from . import condition_rules as rules


def equivalent_claim(record, previous):
    from .scientific_evidence import canonical, STATE_FIELDS
    from .review_dependencies import legacy_leaf_claim
    old = deepcopy(previous.get('claim') or {})
    current = deepcopy(record.get('claim') or {})
    if not old or canonical(old.get('value')) != canonical(current.get('value')):
        return False
    old_context, context = old.get('context') or {}, current.get('context') or {}
    old_policy, policy = old_context.pop('condition_policy', {}), context.pop('condition_policy', {})
    if old_policy.get('version') not in {'condition-rules-v1', rules.VERSION}:
        return False
    for candidate in (old_policy, policy):
        candidate.pop('version', None)
        candidate.pop('result_numbers', None)
        if 'structure_optimization' not in (record.get('state_dependencies') or []):
            candidate.pop('structure_optimization', None)
    if canonical(old_policy) != canonical(policy):
        return False
    if canonical(old) == canonical(current):
        return True
    if 'direct_inputs' in old_context and 'direct_inputs' in context:
        # 组内承载结果切换后，新点未复制旧关联；条件事实仍以同一组身份与原文重验。
        if record.get('record_group_key') and not record.get('source_associations') and record.get('item_key') == previous.get('item_key'):
            old_context.pop('association_dependencies', None)
            context.pop('association_dependencies', None)
        # 扩展数组索引是存储位置，依赖的字段身份由扩展自身的稳定键表达。
        for candidate in (old_context, context):
            inputs = candidate.get('direct_inputs') or {}
            stable = {}
            for path, value in inputs.items():
                if '.extensions.' in path and isinstance(value, dict) and (value.get('field_key') or value.get('key')):
                    path = path.split('.extensions.')[0] + '.extensions.' + str(value.get('field_key') or value['key'])
                if path in stable:
                    return False
                stable[path] = value
            candidate['direct_inputs'] = stable
        if canonical(old) == canonical(current):
            return True
    # v1 -> v2字段依赖变化：重建旧断言，不能只删除旧指纹后比较。
    if not record.get('validation_record') or 'direct_inputs' in old_context:
        return False
    if any(canonical(old_context.get(k)) != canonical(context.get(k))
           for k in record.get('state_dependencies') or []):
        return False
    state = {k: v for k, v in old_context.items() if k in STATE_FIELDS}
    rebuilt = legacy_leaf_claim(record['validation_record'], state, record['record_field'], old.get('field'))
    return canonical(rebuilt) == canonical(old)


def recover(record, previous, chunks):
    """只重验已保存的完整规则证据；输出新投影，旧claim/hash原样留档。"""
    from .property_evidence import digest, source_batches
    from .scientific_evidence import canonical
    review = previous.get('rule_review') or {}
    if (not rules.is_condition(record) or record.get('item_key') != previous.get('item_key') or not record.get('condition_sources_complete')
        or blocks_reuse(previous) or previous.get('status') != 'supported'
        or previous.get('source_hash') != record.get('source_hash')
        or review.get('source_hash') != record.get('source_hash')
        or review.get('content_hash') != previous.get('content_hash')
        or digest(canonical(previous.get('claim'))) != previous.get('content_hash')
        or review.get('version') not in {'condition-rules-v1', rules.VERSION}
        or review.get('coverage') != sorted({rules.window_hash(b) for b in source_batches(chunks)})
        or not equivalent_claim(record, previous)):
        return None
    assessments = [rules.validate_assessment(record, a, chunks) for a in review.get('assessments') or []]
    if not assessments or not all(assessments):
        return None
    rule_id = 'dfpt_to_dft' if any(a['value_origin'] == 'dfpt_definition' for a in assessments) else 'reported_condition_scope'
    if review.get('rule_id') != rule_id:
        return None
    renewed = {**deepcopy(review), 'version': rules.VERSION, 'content_hash': record['content_hash'],
               'assessments': assessments}
    result = {**deepcopy(previous), **{k: deepcopy(record[k]) for k in
              ('claim', 'content_hash', 'source_hash', 'current_value', 'condition_context') if k in record},
              'rule_review': renewed, 'stale': False}
    if previous.get('content_hash') != record['content_hash'] or review.get('version') != rules.VERSION:
        result.update(decision=None, proposal=None, proposal_draft=None)
        result['review_revalidation'] = {'policy': 'condition-lifecycle-v1',
            'previous_content_hash': previous['content_hash'], 'previous_rule_version': review['version'],
            'reason': '字段事实及必要依赖等价，已按当前规则重新定位并验证历史原文；历史记录保留'}
    return result


def invalidation_details(record, previous):
    from .scientific_evidence import canonical
    details = []
    if previous.get('source_hash') != record.get('source_hash'):
        details.append('正文/补充材料、来源角色或来源完整性版本变化')
    old, new = previous.get('claim') or {}, record.get('claim') or {}
    if canonical(old.get('value')) != canonical(new.get('value')):
        details.append('当前计算条件值或字段标注已改变')
    old_context, context = old.get('context') or {}, new.get('context') or {}
    names = {'material':'材料', 'pressure_value_gpa':'压力', 'reported_space_group_symbol':'物相',
             'approximation':'近似类型', 'direct_inputs':'本阶段依赖条件', 'field_settings':'字段设置'}
    for key, label in names.items():
        if canonical(old_context.get(key)) != canonical(context.get(key)):
            details.append(label + '发生变化')
    a, b = old_context.get('condition_policy') or {}, context.get('condition_policy') or {}
    for key, label in {'software':'计算软件', 'stage':'计算阶段', 'parameter':'参数用途'}.items():
        if a.get(key) != b.get(key):
            details.append(label + '发生变化')
    return details or ['旧证据尚未通过当前规则的完整性与适用范围重验']


def blocks_reuse(result):
    return (result.get('association_conflict') or result.get('status') in {'unsupported', 'missing'}
            or result.get('condition_conflict') or
            (result.get('condition_window') or {}).get('verdict') == 'conflict')


def effective_result(record, latest, history, chunks):
    """按时间遍历同一字段；有效反证形成边界，失败尝试单独保留。"""
    if not rules.is_condition(record):
        return latest
    supported = None
    for candidate in history:
        if candidate.get('source_hash') != record.get('source_hash'):
            continue
        if not equivalent_claim(record, candidate):
            continue
        if blocks_reuse(candidate):
            supported = None
        else:
            supported = recover(record, candidate, chunks) or supported
    if not supported:
        if latest and latest.get('stale'):
            return {**latest, 'invalidation_details': invalidation_details(record, latest)}
        return latest
    if latest and not latest.get('stale') and blocks_reuse(latest):
        return latest
    if latest and (latest.get('status') != 'supported' or latest.get('content_hash') != supported['content_hash']):
        supported['review_attempt'] = {k: deepcopy(latest.get(k)) for k in
            ('status', 'reason', 'review_started_at', 'content_hash', 'condition_window_errors')}
    if latest:
        supported['history'] = deepcopy(latest.get('history') or [])
        if latest.get('content_hash') == record['content_hash']:
            for key in ('resolution', 'proposal_draft', 'decision'):
                if key in latest:
                    supported[key] = deepcopy(latest[key])
    return supported


def result_scope_issue(record, chunks):
    """SSCHA结果归属在Tc结果上判定，不能连带撤销同组条件。"""
    if not str(record.get('record_field') or '').startswith('value_') or not record.get('required'):
        return None
    source = record.get('validation_record') or {}
    payload = source.get('payload') or {}
    if not any(str(e.get('key', '')).startswith('sscha.') for e in
               (payload.get('calculation_conditions') or {}).get('extensions') or []):
        return None
    context = rules.result_context(record)
    # 不同结果仍须各自引用表行；只有Methods不能证明新增Tc/μ*属于非谐流程。
    if payload.get('approximation') == 'harmonic' or not any(
            rules.anharmonic_result_matches(context, c['content']) for c in chunks):
        return '当前Tc结果尚未对应原表的SSCHA非谐分组；只需核对本结果的流程归属，已有共用条件保持独立'
    return None
