"""字段级来源绑定与重新核对；科学值不在本模块修改。"""
from copy import deepcopy


def _path(record, association):
    from .property_field_review import read_path
    path = str(association.get('target_path') or '').strip('/').replace('/', '.')
    binding = association.get('field_binding') or {}
    identity = binding.get('field_key')
    if '.extensions.' in path and identity:
        root, tail = path.split('.extensions.', 1)
        entries = read_path(record, root + '.extensions') or []
        matches = [i for i, entry in enumerate(entries)
                   if (entry.get('field_key') or entry.get('key')) == identity]
        if len(matches) != 1:
            return None
        suffix = tail.split('.', 1)
        path = root + '.extensions.' + str(matches[0]) + ('.' + suffix[1] if len(suffix) > 1 else '')
    return path


def field_binding(record, state, association):
    from .property_field_review import read_path, review_context
    from .scientific_context import fingerprint, state_fingerprint
    from .scientific_evidence import canonical
    path = _path(record, association)
    if not path:
        return None
    value = read_path(record, path)
    if value is None:
        return None
    identity = path
    field_key = None
    if '.extensions.' in path:
        root, tail = path.split('.extensions.', 1)
        entry = read_path(record, root + '.extensions.' + tail.split('.')[0])
        field_key = (entry or {}).get('field_key') or (entry or {}).get('key')
        if not field_key or sum((e.get('field_key') or e.get('key')) == field_key
                                for e in read_path(record, root + '.extensions') or []) != 1:
            return None
        identity = root + '.extensions.' + field_key
        if '.' in tail:
            identity += '.' + tail.split('.', 1)[1]
    context = review_context(record, {}, path)
    # 网格/截断能的含义依赖本阶段软件、理论和泛函，不能继承到另一套计算。
    conditions = (record.get('payload') or {}).get('calculation_conditions') or {}
    stage = association.get('stage')
    stage_settings = {key: conditions.get(key) for key in
                      ('calculation_code', 'electronic_method', 'exchange_correlation_functional')}
    if stage not in {'electron_phonon', 'superconductivity'}:
        stage_settings = {e.get('field_key') or e.get('key'): e for e in conditions.get('extensions') or []
                          if str(e.get('key') or '').startswith(str(stage) + '.')
                          and str(e.get('key')).rsplit('.', 1)[-1] in stage_settings}
    return {'version': 1, 'field_key': field_key, 'fingerprint': fingerprint(canonical({
        'field': identity, 'value': value, 'context': context, 'stage': stage,
        'stage_settings': stage_settings, 'state': state_fingerprint(state)}))}


def bind_field(record, state, association):
    binding = field_binding(record, state, association)
    if binding:
        association['field_binding'] = binding


def snapshot_association(record, state, association, chunks=None):
    from .scientific_context import scientific_fingerprint, state_fingerprint
    result = deepcopy(association)
    binding = association.get('field_binding')
    if binding is not None:
        result['stale'] = binding.get('version') != 1 or binding != field_binding(record, state, association)
        path = _path(record, association)
        if path:
            result['target_path'] = '/' + path.replace('.', '/')
    else:
        result['stale'] = association.get('target_fingerprint') != scientific_fingerprint(record)
    if association.get('target_state_fingerprint') is not None:
        result['stale'] |= association['target_state_fingerprint'] != state_fingerprint(state)
    if chunks is not None:
        from .property_evidence import locate
        result['stale'] |= not all(locate(e, chunks) for e in
                                  [*association.get('fact_evidences', []), *association.get('scope_evidences', [])])
    return result


def association_id(association):
    from .property_evidence import digest
    return digest({k: v for k, v in association.items() if k not in {'stale'}})


def review_inputs(record):
    return [{'association_id': association_id(a), **without_source_ids(a)} for a in record.get('source_associations') or []]


def without_source_ids(value):
    """解析器旧段落编号与本次核对窗口编号不是同一个命名空间。"""
    if isinstance(value, dict):
        return {k: without_source_ids(v) for k, v in value.items() if k != 'source_id'}
    if isinstance(value, list):
        return [without_source_ids(v) for v in value]
    return value


REVIEW_PROMPT = '''
记录含 source_associations 时，必须重新核对参数值及其对当前材料/压力/近似/计算阶段的适用范围。
旧说明和旧 stale 标记只是历史线索，不能作为本次支持证据。不能因旧关联过期直接判科学值错误。
每个 results[i] 对象内部同时返回 association_reviews 数组（不是顶层数组），格式为
{"results":[{"key":"字段key","status":"...","evidences":[],"association_reviews":[...]}]}。
association_reviews 每项包含 association_id（复制输入）、
verdict=applicable|conflict|uncertain、basis_kind=paper_quote|paper_inference、explanation（简短中文），
fact_evidences（参数值逐字引句）和 scope_evidences（当前适用范围逐字引句）。
引用优先使用 {"source_id":"review-source-N"}，只复制本次sources中的编号，服务端直接取回原始段落；
不要自行重打含软连字符、上标、数学符号的原文。也可使用原有file_id/chunk_index/quote精确引句。
只有数值和适用范围均有本批可定位依据且无局部例外才选 applicable；矛盾选 conflict，
缺证/不确定选 uncertain。作者未明确范围、需要论文推断时仍标 paper_inference；
原有关联为 paper_inference 或带 inference_rule 时不得升级为 paper_quote。
即使重新核对确认推断合理，也不表示人工批准。不得改当前科学值或复制旧理由冒充本次核对。
'''


def checked_review(record, raw, chunks):
    """只接收模型的语义候选；版本、关联身份和引句由服务端验证。"""
    from .property_evidence import locate
    associations = record.get('source_associations') or []
    if not associations or not isinstance(raw, list):
        return None
    expected = {association_id(a): a for a in associations}
    seen, renewed = set(), {}
    for item in raw:
        if not isinstance(item, dict):
            return None
        key = item.get('association_id')
        if key not in expected or key in seen or item.get('verdict') != 'applicable':
            return None
        seen.add(key)
        basis = item.get('basis_kind')
        explanation = item.get('explanation')
        if basis not in {'paper_quote', 'paper_inference'} or not isinstance(explanation, str) or not explanation.strip():
            return None
        original = expected[key]
        if original.get('basis_kind') == 'paper_inference' or original.get('inference_rule'):
            basis = 'paper_inference'
        sources = {}
        for name in ('fact_evidences', 'scope_evidences'):
            entries = item.get(name)
            if not isinstance(entries, list) or not entries or not all(isinstance(e, dict) for e in entries):
                return None
            resolved = []
            for evidence in entries:
                if str(evidence.get('source_id') or '').startswith('review-source-'):
                    matches = [c for i, c in enumerate(chunks) if evidence['source_id'] == f'review-source-{i}']
                    if len(matches) != 1:
                        return None
                    chunk = matches[0]
                    # 段落编号是定位依据；忽略模型附带的转述，只保存服务端原文。
                    evidence = {**chunk, 'quote': chunk['content']}
                resolved.append(locate(evidence, chunks))
            sources[name] = resolved
            if not all(sources[name]):
                return None
        context = (record.get('claim') or {}).get('context') or {}
        scope = {k: deepcopy(context[k]) for k in ('material', 'material_name', 'pressure_value_gpa',
            'pressure_min_gpa', 'pressure_max_gpa', 'reported_space_group_symbol', 'approximation', 'method_code') if k in context}
        renewed[key] = {**deepcopy(original), **sources, 'scope': scope, 'basis_kind': basis,
                        'explanation': explanation.strip(), 'stale': False}
    if seen != set(expected):
        return None
    return {'version': 1, 'content_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'inputs': sorted(expected), 'associations': [renewed[key] for key in expected],
            'previous_associations': deepcopy(associations)}


def effective_associations(record, result, chunks):
    original = record.get('source_associations') or []
    review = result.get('association_review') or {}
    if (result.get('stale') or review.get('version') != 1
        or review.get('content_hash') != record.get('content_hash')
        or review.get('source_hash') != record.get('source_hash')
        or review.get('inputs') != sorted(association_id(a) for a in original)):
        return original
    # 重读仍定位全部证据，不把存储字段当作无条件通过标志。
    raw = [{'association_id': association_id(old), 'verdict': 'applicable',
            **{k: new.get(k) for k in ('basis_kind', 'explanation', 'fact_evidences', 'scope_evidences')}}
           for old, new in zip(original, review.get('associations') or [])]
    checked = checked_review(record, raw, chunks)
    return checked['associations'] if checked else original


def aggregate_reviews(record, candidates):
    """明确冲突和相互矛盾的判断不由其他窗口的通过结论覆盖。"""
    if any(item.get('association_conflict') or item.get('status') == 'unsupported' for item in candidates):
        return None
    reviews = [item['association_review'] for item in candidates if item.get('association_review')]
    if not reviews:
        return None
    result = deepcopy(reviews[0])
    for index, association in enumerate(result['associations']):
        if any(r['associations'][index]['basis_kind'] == 'paper_inference' for r in reviews):
            association['basis_kind'] = 'paper_inference'
    return result
