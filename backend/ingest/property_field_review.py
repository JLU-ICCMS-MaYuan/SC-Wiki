"""预测记录按科学子项构造断言；旧整条结论不向子项授信。"""
from copy import deepcopy

LABELS = {'method_code': '预测方法', 'lambda_ep': '电声耦合强度 λ', 'omega_log': 'ωlog', 'mu_star': 'μ*',
          'calculation_code': '计算软件', 'electronic_method': '电子结构方法', 'exchange_correlation_functional': '交换关联泛函',
          'k_grid': 'k 网格', 'q_grid': 'q 网格', 'k_broadening': 'k 展宽', 'q_broadening': 'q 展宽'}
CONDITIONS = tuple(key for key in LABELS if key not in {'method_code', 'lambda_ep', 'omega_log', 'mu_star'})
METHODS = {'isotropic_eliashberg': '各向同性 Eliashberg', 'anisotropic_eliashberg': '各向异性 Eliashberg',
           'allen_dynes': 'Allen–Dynes', 'mcmillan': 'McMillan', 'scdft': 'SCDFT', 'unknown': '未说明'}


def read_path(value, path):
    for key in path.split('.'):
        if isinstance(value, list) and key.isdigit():
            value = value[int(key)] if int(key) < len(value) else None
        else:
            value = value.get(key) if isinstance(value, dict) else None
    return value


def write_path(value, path, replacement):
    keys = path.split('.')
    for index, key in enumerate(keys[:-1]):
        if isinstance(value, list):
            value = value[int(key)]
        else:
            value = value.setdefault(key, [] if keys[index + 1].isdigit() else {})
    if isinstance(value, list):
        value[int(keys[-1])] = deepcopy(replacement)
    else:
        value[keys[-1]] = deepcopy(replacement)


def review_context(record, state, path):
    """仅真实上下文进入版本；修改别的结果值不使本字段失效。"""
    context = deepcopy(state)
    payload = record.get('payload') or {}
    is_mu = path.startswith('payload.parameters.mu_star') or path.startswith('payload.parameters.extensions.')
    if path == 'method_code' or path.startswith('value_') or is_mu:
        context['definition'] = [record.get('definition_key'), record.get('definition_version')]
    if payload.get('approximation'):
        context['approximation'] = payload['approximation']
    annotations = None
    if path.startswith('payload.parameters.'):
        name = path.split('.')[2].replace('omega_log_k', 'omega_log')
        annotations = ((payload.get('field_settings') or {}).get('mu_star') if is_mu else
                       (payload.get('parameters', {}).get('field_settings') or {}).get(name))
    elif path.startswith('payload.calculation_conditions.') and '.extensions.' not in path:
        annotations = (payload.get('calculation_conditions', {}).get('field_settings') or {}).get(path.split('.')[2])
    elif path.startswith('value_'):
        annotations = (payload.get('field_settings') or {}).get('tc')
    if annotations:
        context['field_settings'] = deepcopy(annotations)
    if path.startswith('value_') and record.get('value_kind') in {'number', 'range'} or 'omega_log' in path:
        context['unit'] = 'K'
    elif 'lambda_ep' in path or is_mu:
        context['unit'] = '1'
    if path.startswith('value_'):
        parameters = payload.get('parameters') or {}
        mu = parameters.get('mu_star')
        if isinstance(mu, dict):
            mu = mu.get('value_number')
        for i, extension in enumerate(parameters.get('extensions') or []):
            if extension.get('key') == 'mu_star' and extension.get('value_kind') == 'range' and path in {'value_min', 'value_max'}:
                mu = extension.get('value_max' if path == 'value_min' else 'value_min')
        context['paired_mu_star'] = mu
    elif is_mu:
        context['paired_tc'] = (record.get('value_number') if record.get('value_kind') == 'number' else
                                record.get('value_min' if path.endswith('.value_max') else 'value_max') if '.extensions.' in path else
                                [record.get('value_min'), record.get('value_max')])
    if path.startswith(('value_', 'payload.parameters.mu_star')) or '.extensions.' in path and path.startswith('payload.parameters.'):
        context['method_code'] = record.get('method_code')
    if path.startswith(('value_', 'payload.parameters.')):
        conditions = deepcopy(payload.get('calculation_conditions') or {})
        conditions['extensions'] = [e for e in conditions.get('extensions') or []
                                    if not str(e.get('key') or '').startswith(('structural_relaxation.', 'aimd.'))]
        context['calculation_conditions'] = conditions
        context['approximation'] = payload.get('approximation')
    if '.sscha.' in path:
        context['approximation'] = payload.get('approximation')
    return context


def expand_property_fields(records):
    from .scientific_evidence import item_identity, populated
    result, shared = [], set()
    for parent in records:
        original = (parent.get('claim') or {}).get('record') or {}
        if parent.get('kind') != 'property' or original.get('record_type') != 'predicted_tc':
            result.append(parent)
            continue
        source = deepcopy(original)
        validation = deepcopy(source)
        if parent.get('tc_group_meta'):
            validation.setdefault('payload', {})['tc_group'] = deepcopy(parent['tc_group_meta'])
        payload = source.get('payload') or {}
        parameters = payload.get('parameters') or {}
        conditions = payload.get('calculation_conditions') or {}
        group = (payload.get('tc_group') or {}).get('group_key')  # snapshot通常已去除UI身份，调用者可显式提供。
        group = parent.get('tc_group_key') or group
        meta = parent.get('tc_group_meta') or {}
        specifications = [('method_code', LABELS['method_code'], 'text', 'method_code', True)]
        for key in ('lambda_ep', 'omega_log'):
            actual = 'omega_log_k' if key == 'omega_log' and key not in parameters and 'omega_log_k' in parameters else key
            value = parameters.get(actual)
            path = 'payload.parameters.' + actual + ('.value_number' if isinstance(value, dict) else '')
            specifications.append((path, LABELS[key], 'number', 'parameters.' + key, True))
        if source.get('value_kind') == 'range':
            specifications.extend((name, 'Tc · ' + label, 'number', name, False) for name, label in [('value_min', '第1组'), ('value_max', '第2组')])
        elif source.get('value_kind') == 'number':
            specifications.append(('value_number', 'Tc', 'number', 'value_number', False))
        else:
            name = 'value_boolean' if source.get('value_kind') == 'boolean' else 'value_text'
            specifications.append((name, 'Tc', source.get('value_kind') or 'text', name, False))
        mu = parameters.get('mu_star')
        if mu is not None or not any(e.get('key') == 'mu_star' and e.get('value_kind') == 'range' for e in parameters.get('extensions') or []):
            specifications.append(('payload.parameters.mu_star' + ('.value_number' if isinstance(mu, dict) else ''), 'μ*', 'number', 'parameters.mu_star', False))
        for i, extension in enumerate(parameters.get('extensions') or []):
            if extension.get('key') == 'mu_star' and extension.get('value_kind') == 'range':
                for key, name in [('value_max', 'μ* · 第1组'), ('value_min', 'μ* · 第2组')]:
                    specifications.append((f'payload.parameters.extensions.{i}.{key}', name, 'number', 'parameters.mu_star.' + key, False))
        specifications.extend(('payload.calculation_conditions.' + key, LABELS[key], 'number' if key.endswith('broadening') else 'text', 'conditions.' + key, True) for key in CONDITIONS)
        for i, extension in enumerate(conditions.get('extensions') or []):
            identity = extension.get('field_key') or extension.get('key')
            identity = identity if isinstance(identity, str) and identity else None
            # 无稳定key的历史扩展不能依重排后的数组位置继承审核资格。
            identity = identity or item_identity('legacy-extension', extension)
            specifications.append((f'payload.calculation_conditions.extensions.{i}', extension.get('name_raw') or extension.get('name') or extension.get('key') or '补充计算条件', 'object', 'conditions.extension.' + identity, True))
        for path, label, kind, identity, common in specifications:
            prior_owner = item_identity('tc-group', parent.get('state_key'), parent.get('module_key'), group,
                                       parent.get('tc_method_key') if path == 'method_code' else '') if group and common else parent['item_key']
            prior_field = item_identity(prior_owner, 'field', identity)
            owner = item_identity('tc-group', parent.get('state_key'), parent.get('module_key'), group or parent['record_key'],
                                  parent.get('tc_method_key') or parent['record_key'] if path == 'method_code' else '') if common else parent['item_key']
            semantic = identity
            point = None
            if path in {'value_min', 'value_max'}:
                point = parent['record_key'] + (':0' if path == 'value_min' else ':1')
                semantic = 'tc'
            elif path == 'value_number':
                point = meta.get('point_key') or parent['record_key']; semantic = 'tc'
            elif identity.startswith('parameters.mu_star') and ('.extensions.' in path or source.get('value_kind') != 'range'):
                point = (parent['record_key'] + (':0' if path.endswith('.value_max') else ':1')) if '.extensions.' in path else meta.get('point_key') or parent['record_key']
                semantic = 'mu_star'
            if point:
                owner = item_identity('tc-point', parent.get('state_key'), parent.get('module_key'), point)
            legacy_parent = parent['item_key']
            if parent.get('tc_range_origin_kind') == 'range' and str(meta.get('point_key') or '').rsplit(':', 1)[-1] in {'0', '1'}:
                from .scientific_evidence import record_identity
                legacy_parent = record_identity(parent.get('state_key'), parent.get('module_key'), meta['point_key'].rsplit(':', 1)[0])
            identity_for_review = semantic
            unique = (owner, identity_for_review)
            if unique in shared:
                continue
            shared.add(unique)
            value = read_path(source, path)
            key = item_identity(owner, 'field', identity_for_review)
            field = parent['field'] + '.' + path
            evs = [deepcopy(e) for e in parent.get('evidences') or [] if e.get('field_path') in {path, field}]
            associations = []
            for association in payload.get('source_associations') or []:
                pointer = str(association.get('target_path') or '').strip('/').replace('/', '.')
                if pointer == path or pointer.startswith(path + '.') or path.startswith(pointer + '.'):
                    evs.extend(deepcopy(association.get('fact_evidences') or []))
                    from .scientific_context import scientific_fingerprint
                    associations.append({**deepcopy(association), 'stale': association.get('target_fingerprint') != scientific_fingerprint(source)})
            context = review_context(source, parent['claim'].get('state') or {}, path)
            extension_value = read_path(source, '.'.join(path.split('.')[:4])) if '.extensions.' in path else None
            dependencies = (['method_code'] if path.startswith('value_') or identity.startswith('parameters.mu_star') else []) + (['payload.calculation_conditions'] if path.startswith(('value_', 'payload.parameters.')) else [])
            if path.startswith('value_'):
                mu_extension = next((i for i, e in enumerate(parameters.get('extensions') or []) if e.get('key') == 'mu_star' and e.get('value_kind') == 'range'), None)
                dependencies.append(f'payload.parameters.extensions.{mu_extension}.' + ('value_max' if path == 'value_min' else 'value_min') if mu_extension is not None and path in {'value_min', 'value_max'} else 'payload.parameters.mu_star')
            if identity.startswith('parameters.mu_star'):
                dependencies.extend(['value_number'] if source.get('value_kind') == 'number' else ['value_min' if path.endswith('.value_max') else 'value_max'] if '.extensions.' in path else ['value_min', 'value_max'])
            result.append({k: deepcopy(v) for k, v in parent.items() if k not in {'key', 'item_key', 'claim', 'evidences', 'current_value', 'fields', 'field', 'kind', 'label'}} | {
                'key': key, 'item_key': key, 'kind': 'field', 'record_field': path,
                'record_group_key': group if common and path != 'method_code' else None,
                'record_dependencies': dependencies,
                'legacy_item_key': legacy_parent, 'previous_field_item_key': prior_field if prior_field != key else None,
                'validation_record': validation, 'field': field,
                'record_field_key': (extension_value.get('field_key') or extension_value.get('key')) if isinstance(extension_value, dict) else None,
                'owner_label': ' · '.join(str(x) for x in [context.get('material_name') or context.get('material') or '材料',
                    str(context.get('pressure_value_gpa')) + ' GPa' if context.get('pressure_value_gpa') is not None else '',
                    METHODS.get(source.get('method_code'), source.get('method_code')), source.get('value_raw')] if x),
                'fields': [field + '.value_raw' if kind == 'object' else field], 'label': (context.get('field_settings') or {}).get('name_raw') or label,
                'current_value': deepcopy(value), 'required': populated(value), 'evidences': evs,
                'source_associations': associations,
                'claim': {'value': deepcopy(value), 'field': 'Tc' if semantic == 'tc' else 'μ*' if semantic == 'mu_star' else label, 'context': context},
                'field_schema': {'type': 'array' if isinstance(value, list) else kind if kind in {'number', 'boolean', 'object'} else 'string', 'nullable': True},
                'legacy_evidences': deepcopy(parent.get('evidences') or [])})
    return result
